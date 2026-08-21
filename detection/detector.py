"""Production Ultralytics detector adapter.

Supports current Ultralytics YOLO, YOLO-World and YOLOE checkpoints while
preserving AI Vision's existing Detection interface.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import threading
from typing import Any


@dataclass
class Detection:
    class_name: str
    confidence: float
    box: tuple[int, int, int, int]
    class_id: int = 0
    object_type: str | None = None
    inventory_name: str | None = None
    quantity: int = 1
    quantity_grid: tuple[int, int, int] = (1, 1, 1)
    width_m: float | None = None
    height_m: float | None = None
    depth_m: float | None = None
    distance_m: float | None = None
    method: str | None = "ultralytics"


class Detector:
    def __init__(
        self,
        model_path: str = "yoloe-26s-seg.pt",
        confidence_threshold: float = 0.25,
        device: str = "cpu",
        classes: list[str] | None = None,
        class_prompts: list[str] | None = None,
        image_size: int = 640,
        class_agnostic_nms: bool = False,
        iou_threshold: float = 0.55,
        max_detections: int = 300,
        compile_model: bool | str = False,
        fallback_model_path: str | None = None,
        allow_fallback: bool = True,
        detector_mode: str = "universal",
    ):
        self.confidence_threshold = float(confidence_threshold)
        self.device = _resolve_device(device)
        # Retained only as configuration metadata. Detection never applies a
        # business allow-list; every valid model observation is forwarded.
        self.configured_classes = tuple(classes or ())
        self.class_prompts = _clean_prompts(class_prompts or classes or [])
        self.image_size = int(image_size)
        self.class_agnostic_nms = bool(class_agnostic_nms)
        self.iou_threshold = float(iou_threshold)
        self.max_detections = int(max_detections)
        self.compile_model = compile_model
        self.requested_model_path = str(model_path)
        self.model_path = str(model_path)
        self.fallback_model_path = (
            fallback_model_path
            or os.getenv("ULTRALYTICS_FALLBACK_MODEL", "yolov8s-worldv2.pt")
        )
        self.allow_fallback = bool(allow_fallback)
        self.detector_mode = str(detector_mode)
        self.model = None
        self.load_error: str | None = None
        self._lock = threading.Lock()
        self._load_model()

    def _load_model(self) -> None:
        if self.requested_model_path.strip().lower() == "dummy":
            # Explicit no-model sentinel used by deterministic demo configs
            # (e.g. config/demo.yaml). Skip loading/downloading any weights
            # so main.py's dummy-detector branch (model is None) activates.
            self.model = None
            self.model_path = self.requested_model_path
            self.load_error = None
            print("Detector: model_path is 'dummy', running without a model.")
            return
        errors: list[str] = []
        # Ordered, de-duplicated candidate list. We try, in order:
        #   1. the requested model (config's model_path),
        #   2. the configured fallback (config's fallback_model_path),
        #   3. a known-good downloadable open-vocabulary model, so detection
        #      still RUNS with the configured class_prompts even when the
        #      custom weights were never provisioned on the server,
        #   4. a stock detector that ships with Ultralytics as a last resort,
        #      so the model is never silently None and the loop keeps running.
        # This never touches config.yaml; it only widens what the code can
        # recover from when a weights file is missing.
        candidates: list[str] = []
        model_candidates = ((self.requested_model_path,) if not self.allow_fallback else (
            self.requested_model_path, self.fallback_model_path,
            _DEFAULT_OPEN_VOCAB_MODEL, _DEFAULT_STOCK_MODEL,
        ))
        for candidate in model_candidates:
            if candidate and candidate not in candidates:
                candidates.append(candidate)
        for candidate in candidates:
            # If a weights file with this name exists in the mounted models
            # directory (or cwd), load it directly; otherwise hand the bare
            # name to Ultralytics so it can resolve/download a known asset.
            resolved = _resolve_model_path(candidate)
            try:
                self.model = _load_ultralytics_model(resolved)
                self.model_path = candidate
                self._apply_prompts()
                self.load_error = "; ".join(errors) if errors else None
                if candidate != self.requested_model_path:
                    print(
                        "Ultralytics detector: requested model "
                        f"'{self.requested_model_path}' unavailable, running "
                        f"with fallback '{candidate}'."
                    )
                return
            except Exception as exc:
                errors.append(f"{candidate}: {exc}")
        self.model = None
        self.load_error = "; ".join(errors) or "No Ultralytics model could be loaded."
        print(f"Ultralytics detector unavailable: {self.load_error}")

    def _apply_prompts(self) -> None:
        if not self.class_prompts or self.model is None:
            return
        set_classes = getattr(self.model, "set_classes", None)
        if callable(set_classes):
            set_classes(list(self.class_prompts))

    def detect(self, frame) -> list[Detection]:
        if self.model is None or frame is None:
            return []
        kwargs: dict[str, Any] = {
            "source": frame,
            "conf": self.confidence_threshold,
            "iou": self.iou_threshold,
            "max_det": self.max_detections,
            "device": self.device,
            "imgsz": self.image_size,
            "agnostic_nms": self.class_agnostic_nms,
            "verbose": False,
        }
        if self.compile_model:
            kwargs["compile"] = self.compile_model
        with self._lock:
            try:
                results = self.model.predict(**kwargs)
            except TypeError:
                # Compatibility with older Ultralytics builds that do not yet
                # expose torch.compile through predict().
                kwargs.pop("compile", None)
                results = self.model.predict(**kwargs)
        if not results:
            return []
        result = results[0]
        boxes = getattr(result, "boxes", None)
        # A frame with no detections yields an empty or non-Boxes value (some
        # builds hand back an empty list). Only a populated Ultralytics Boxes
        # exposes cls/conf/xyxy; anything else means "nothing detected", so
        # return [] instead of raising on a missing attribute.
        cls = getattr(boxes, "cls", None)
        conf = getattr(boxes, "conf", None)
        xyxy = getattr(boxes, "xyxy", None)
        if cls is None or conf is None or xyxy is None:
            return []
        names = getattr(result, "names", {}) or {}
        detections: list[Detection] = []
        class_values = cls.tolist()
        confidence_values = conf.tolist()
        coordinates = xyxy.tolist()
        for class_value, confidence, coordinates_xyxy in zip(
            class_values, confidence_values, coordinates
        ):
            class_id = int(class_value)
            class_name = (
                str(names.get(class_id, class_id))
                if isinstance(names, dict)
                else str(names[class_id] if class_id < len(names) else class_id)
            )
            x1, y1, x2, y2 = coordinates_xyxy
            detections.append(
                Detection(
                    class_name=class_name,
                    confidence=float(confidence),
                    box=(int(x1), int(y1), int(x2), int(y2)),
                    class_id=class_id,
                    object_type=class_name,
                    method=f"ultralytics:{self.model_path}",
                )
            )
        return detections

    def health(self) -> dict[str, Any]:
        return {
            "provider": "ultralytics",
            "ready": self.model is not None,
            "requested_model": self.requested_model_path,
            "active_model": self.model_path if self.model is not None else None,
            "fallback_used": self.model is not None
            and self.model_path != self.requested_model_path,
            "detector_mode": self.detector_mode,
            "device": self.device,
            "image_size": self.image_size,
            "prompts": list(self.class_prompts),
            "error": self.load_error,
        }


# Last-resort models used only when the configured weights are missing. Both are
# standard Ultralytics assets that download on first use, so detection keeps
# working even if the custom checkpoint was never provisioned. The open-vocab
# model honours the configured class_prompts; the stock model is the final
# safety net so the detector is never silently disabled. Overridable via env.
_DEFAULT_OPEN_VOCAB_MODEL = os.getenv("AI_VISION_OPENVOCAB_MODEL", "yolov8s-worldv2.pt")
_DEFAULT_STOCK_MODEL = os.getenv("AI_VISION_STOCK_MODEL", "yolov8n.pt")


def _resolve_model_path(model_path: str) -> str:
    """Return a real filesystem path when the weights live in the mounted
    models directory (or cwd); otherwise return the bare name so Ultralytics
    can resolve/download a known asset. Absolute/existing paths pass through."""
    name = str(model_path)
    if os.path.isabs(name) or os.path.exists(name):
        return name
    search_dirs = [
        os.getenv("AI_VISION_MODELS_DIR", ""),
        "/app/models",
        "models",
        os.getcwd(),
    ]
    for directory in search_dirs:
        if not directory:
            continue
        candidate = os.path.join(directory, name)
        if os.path.exists(candidate):
            return candidate
    return name


def _load_ultralytics_model(model_path: str):
    normalized = os.path.basename(model_path).lower()
    if "yoloe" in normalized:
        from ultralytics import YOLOE

        return YOLOE(model_path)
    if "world" in normalized:
        try:
            from ultralytics import YOLOWorld

            return YOLOWorld(model_path)
        except ImportError:
            from ultralytics import YOLO

            return YOLO(model_path)
    from ultralytics import YOLO

    return YOLO(model_path)


def _clean_prompts(values: list[str]) -> list[str]:
    prompts: list[str] = []
    seen: set[str] = set()
    for value in values:
        prompt = " ".join(str(value).split()).strip()
        key = prompt.lower()
        if prompt and key not in seen:
            seen.add(key)
            prompts.append(prompt)
    return prompts


def _resolve_device(device: str | None) -> str:
    requested = str(device or "auto").strip().lower()
    if requested not in {"", "auto"}:
        return str(device)
    try:
        import torch

        if torch.cuda.is_available():
            return "0"
        if bool(getattr(torch.backends, "mps", None)) and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"
