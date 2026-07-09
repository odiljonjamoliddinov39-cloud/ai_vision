"""
tracking/tracker.py

Phase 3: Per-object tracking with persistent IDs, built on top of the
Detection objects already produced in Phase 1 (see detection/detector.py).

Rather than hand-rolling ByteTrack, this wraps Ultralytics' built-in
`model.track(...)`, which ships with a ByteTrack config (bytetrack.yaml)
and an optional BoT-SORT config (botsort.yaml). Ultralytics handles the
Kalman-filter/Hungarian-matching bookkeeping; this module just adapts
its output into the project's own TrackedObject shape and keeps it
duck-type compatible with detection.detector.Detection (same
class_name / confidence / box fields), so draw.py, snapshot.py and
event_log.py all keep working unmodified.

FR-Phase3: Object Tracking
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TrackedObject:
    track_id: int
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


class ObjectTracker:
    def __init__(
        self,
        model,
        confidence_threshold: float = 0.5,
        device: str = "cpu",
        classes: list[str] | None = None,
        tracker_config: str = "bytetrack.yaml",
        image_size: int = 640,
        class_agnostic_nms: bool = False,
    ):
        """
        Args:
            model: an already-loaded ultralytics.YOLO instance. Reusing the
                Detector's model avoids loading the weights twice.
            tracker_config: "bytetrack.yaml" (default, IoU-only, fast) or
                "botsort.yaml" (adds appearance re-identification, slower).
        """
        self.model = model
        self.confidence_threshold = confidence_threshold
        self.device = device
        self.classes_filter = set(classes) if classes else None
        self.tracker_config = tracker_config
        self.image_size = image_size
        self.class_agnostic_nms = class_agnostic_nms

    def update(self, frame) -> list[TrackedObject]:
        """
        Runs detection + tracking on a single BGR frame and returns the
        currently visible TrackedObjects, each carrying a track_id that
        stays stable across frames for as long as the object is visible.
        """
        results = self.model.track(
            source=frame,
            conf=self.confidence_threshold,
            device=self.device,
            tracker=self.tracker_config,
            imgsz=self.image_size,
            agnostic_nms=self.class_agnostic_nms,
            persist=True,
            verbose=False,
        )

        tracked: list[TrackedObject] = []
        if not results:
            return tracked

        result = results[0]
        names = result.names
        boxes = result.boxes

        if boxes is None or boxes.id is None:
            # Nothing matched a track this frame (e.g. first frame, or a
            # gap where the tracker's own internal buffer had nothing to
            # attach an ID to yet).
            return tracked

        ids = boxes.id.tolist()
        for i, track_id in enumerate(ids):
            class_id = int(boxes.cls[i])
            class_name = names.get(class_id, str(class_id))

            if self.classes_filter and class_name not in self.classes_filter:
                continue

            confidence = float(boxes.conf[i])
            x1, y1, x2, y2 = boxes.xyxy[i].tolist()

            tracked.append(
                TrackedObject(
                    track_id=int(track_id),
                    class_name=class_name,
                    confidence=confidence,
                    box=(int(x1), int(y1), int(x2), int(y2)),
                )
            )

        return tracked

    def reset(self) -> None:
        """Clears the underlying tracker's internal state (e.g. after a
        camera reconnect, so old track IDs aren't reused for new objects)."""
        if hasattr(self.model, "predictor") and self.model.predictor is not None:
            trackers = getattr(self.model.predictor, "trackers", None)
            if trackers:
                for t in trackers:
                    if hasattr(t, "reset"):
                        t.reset()
