"""
detection/detector.py

Wraps an Ultralytics YOLO model to detect objects in a frame.

FR-2: Object Detection
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Detection:
    class_name: str
    confidence: float
    box: tuple  # (x1, y1, x2, y2)


class Detector:
    def __init__(
        self,
        model_path: str = "models/yolov8n.pt",
        confidence_threshold: float = 0.5,
        device: str = "cpu",
        classes: list[str] | None = None,
    ):
        if model_path == "dummy":
            self.model = None
            self.confidence_threshold = confidence_threshold
            self.device = device
            self.classes_filter = set(classes) if classes else None
            return

        # Imported lazily so the rest of the project can be explored/tested
        # without requiring ultralytics/torch to be installed.
        from ultralytics import YOLO

        if model_path == "models/yolov8n.pt":
            from pathlib import Path

            if not Path(model_path).exists():
                model_path = "yolov8n.pt"

        self.model = YOLO(model_path)
        self.confidence_threshold = confidence_threshold
        self.device = device
        self.classes_filter = set(classes) if classes else None

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
