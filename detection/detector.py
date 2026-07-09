"""
detection/detector.py

Wraps an Ultralytics YOLO model to detect objects in a frame.

FR-2: Object Detection
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Detection:
    class_name: str
    confidence: float
    box: tuple  # (x1, y1, x2, y2)
    object_type: str | None = None
    inventory_name: str | None = None
    quantity: int = 1
    quantity_grid: tuple[int, int, int] = (1, 1, 1)
    width_m: float | None = None
    height_m: float | None = None
    depth_m: float | None = None
    distance_m: float | None = None
    method: str | None = None


class Detector:
    def __init__(
        self,
        model_path: str = "models/yolov8n.pt",
        confidence_threshold: float = 0.5,
        device: str = "cpu",
        classes: list[str] | None = None,
        class_prompts: list[str] | None = None,
        image_size: int = 640,
        class_agnostic_nms: bool = False,
    ):
        if model_path == "dummy":
            self.model = None
            self.confidence_threshold = confidence_threshold
            self.device = device
            self.classes_filter = set(classes) if classes else None
            self.class_prompts = class_prompts or []
            self.image_size = image_size
            self.class_agnostic_nms = class_agnostic_nms
            return

        # Imported lazily so the rest of the project can be explored/tested
        # without requiring ultralytics/torch to be installed.
        from ultralytics import YOLO

        if not Path(model_path).exists() and Path(model_path).parent.name == "models":
            model_path = Path(model_path).name

        self.model = YOLO(model_path)
        self.confidence_threshold = confidence_threshold
        self.device = device
        self.classes_filter = set(classes) if classes else None
        self.class_prompts = class_prompts or []
        self.image_size = image_size
        self.class_agnostic_nms = class_agnostic_nms

        if self.class_prompts:
            set_classes = getattr(self.model, "set_classes", None)
            if set_classes is None:
                raise ValueError(
                    "detection.class_prompts requires an open-vocabulary YOLO model."
                )
            set_classes(self.class_prompts)

    def detect(self, frame) -> list[Detection]:
        """
        Run detection on a single BGR frame.
        Returns a list of Detection objects.
        """
        if self.model is None:
            return [Detection(class_name="box", confidence=0.95, box=(430, 260, 530, 340))]

        results = self.model.predict(
            source=frame,
            conf=self.confidence_threshold,
            device=self.device,
            imgsz=self.image_size,
            agnostic_nms=self.class_agnostic_nms,
            verbose=False,
        )

        detections: list[Detection] = []
        if not results:
            return detections

        result = results[0]
        names = result.names  # {class_id: class_name}

        for box in result.boxes:
            class_id = int(box.cls[0])
            class_name = names.get(class_id, str(class_id))

            if self.classes_filter and class_name not in self.classes_filter:
                continue

            confidence = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()

            detections.append(
                Detection(
                    class_name=class_name,
                    confidence=confidence,
                    box=(int(x1), int(y1), int(x2), int(y2)),
                )
            )

        return detections
