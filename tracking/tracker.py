"""
tracking/tracker.py

Phase 3: Per-camera object tracking with persistent IDs.

Ultralytics stores persistent tracker state on the model predictor itself.
Sharing one model.track(..., persist=True) call across cameras therefore mixes
unrelated timelines. This adapter keeps association state inside each
ObjectTracker instance while using the shared model only for stateless predict.

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


@dataclass
class _TrackState:
    class_name: str
    box: tuple[int, int, int, int]
    missed_updates: int = 0


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
        match_iou_threshold: float = 0.25,
        max_missed_updates: int = 30,
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
        self.match_iou_threshold = float(match_iou_threshold)
        self.max_missed_updates = int(max_missed_updates)
        self._tracks: dict[int, _TrackState] = {}
        self._next_track_id = 1

    def update(self, frame) -> list[TrackedObject]:
        """
        Runs detection + tracking on a single BGR frame and returns the
        currently visible TrackedObjects, each carrying a track_id that
        stays stable across frames for as long as the object is visible.
        """
        predict = getattr(self.model, "predict", None)
        if callable(predict):
            results = predict(
                source=frame,
                conf=self.confidence_threshold,
                device=self.device,
                imgsz=self.image_size,
                agnostic_nms=self.class_agnostic_nms,
                verbose=False,
            )
        else:  # compatibility for lightweight model doubles and older runtimes
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

        if boxes is None:
            self._age_unmatched_tracks(set())
            return tracked

        candidates = []
        supplied_ids = boxes.id.tolist() if getattr(boxes, "id", None) is not None else None
        for i in range(len(boxes.cls.tolist())):
            class_id = int(boxes.cls[i])
            class_name = names.get(class_id, str(class_id))
            if self.classes_filter and class_name not in self.classes_filter:
                continue
            confidence = float(boxes.conf[i])
            x1, y1, x2, y2 = boxes.xyxy[i].tolist()
            candidates.append(
                (
                    confidence,
                    class_name,
                    (int(x1), int(y1), int(x2), int(y2)),
                    int(supplied_ids[i]) if supplied_ids is not None else None,
                )
            )

        matched_ids: set[int] = set()
        for confidence, class_name, box, supplied_id in sorted(
            candidates, key=lambda candidate: candidate[0], reverse=True
        ):
            track_id = supplied_id
            if track_id is None:
                track_id = self._match_track(class_name, box, matched_ids)
            if track_id is None:
                track_id = self._next_track_id
                self._next_track_id += 1
            self._tracks[track_id] = _TrackState(class_name=class_name, box=box)
            matched_ids.add(track_id)
            tracked.append(
                TrackedObject(
                    track_id=int(track_id),
                    class_name=class_name,
                    confidence=confidence,
                    box=box,
                )
            )

        self._age_unmatched_tracks(matched_ids)
        return tracked

    def reset(self) -> None:
        """Clear only this camera's association state."""
        self._tracks.clear()
        self._next_track_id = 1

    def _match_track(
        self,
        class_name: str,
        box: tuple[int, int, int, int],
        matched_ids: set[int],
    ) -> int | None:
        matches = [
            (_box_iou(state.box, box), track_id)
            for track_id, state in self._tracks.items()
            if track_id not in matched_ids and state.class_name == class_name
        ]
        if not matches:
            return None
        score, track_id = max(matches)
        return track_id if score >= self.match_iou_threshold else None

    def _age_unmatched_tracks(self, matched_ids: set[int]) -> None:
        expired = []
        for track_id, state in self._tracks.items():
            if track_id in matched_ids:
                continue
            state.missed_updates += 1
            if state.missed_updates > self.max_missed_updates:
                expired.append(track_id)
        for track_id in expired:
            self._tracks.pop(track_id, None)


def _box_iou(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
) -> float:
    x1 = max(first[0], second[0])
    y1 = max(first[1], second[1])
    x2 = min(first[2], second[2])
    y2 = min(first[3], second[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    if intersection <= 0:
        return 0.0
    first_area = max(0, first[2] - first[0]) * max(0, first[3] - first[1])
    second_area = max(0, second[2] - second[0]) * max(0, second[3] - second[1])
    union = first_area + second_area - intersection
    return intersection / union if union > 0 else 0.0
