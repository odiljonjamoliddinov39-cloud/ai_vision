"""
tracking/tracker.py

Phase 3: Per-camera object tracking with persistent IDs.

Design
------
Detection and tracking are decoupled. The shared YOLO model runs ONCE per frame
(in the detection scheduler) and produces plain detections; each camera owns an
ObjectTracker that turns those detections into stable track IDs. Tracker state
therefore lives on the main loop, isolated per camera, and is never touched by
the detector's worker threads.

The association is a ByteTrack-style algorithm driven by the tracker config
(config/warehouse_bytetrack.yaml):

  * two-stage matching - high-confidence detections are matched to existing
    tracks first, then low-confidence detections recover tracks that would
    otherwise be dropped (ByteTrack's key idea);
  * a track buffer (`track_buffer`) keeps a briefly-missed object alive for N
    frames so it keeps its ID instead of fragmenting into a new one;
  * IoU thresholds derive from `match_thresh`; new tracks need `new_track_thresh`.

There is no Kalman motion model: warehouse stock is near-static, so association
uses the last box directly, which is robust and jitter-free for this domain.

update_with_detections(detections) is the decoupled entry point. update(frame)
is kept for back-compat: it runs the model itself (predict, or track for model
doubles that supply IDs) and then feeds the same association.

FR-Phase3: Object Tracking
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from detection.proposals import object_proposal_boxes


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
        model=None,
        confidence_threshold: float = 0.5,
        device: str = "cpu",
        classes: list[str] | None = None,
        tracker_config: str = "bytetrack.yaml",
        image_size: int = 640,
        class_agnostic_nms: bool = False,
        iou_threshold: float = 0.55,
        max_detections: int = 300,
        match_iou_threshold: float = 0.25,
        max_missed_updates: int = 30,
    ):
        """
        Args:
            model: an already-loaded ultralytics.YOLO instance (only used by the
                back-compat update(frame) path). The decoupled
                update_with_detections() path needs no model.
            tracker_config: path to a ByteTrack yaml (e.g.
                config/warehouse_bytetrack.yaml). Its thresholds drive the
                association; missing keys fall back to the constructor defaults.
        """
        self.model = model
        self.confidence_threshold = confidence_threshold
        self.device = device
        self.classes_filter = set(classes) if classes else None
        self.tracker_config = tracker_config
        self.image_size = image_size
        self.class_agnostic_nms = class_agnostic_nms
        self.iou_threshold = float(iou_threshold)
        self.max_detections = int(max_detections)

        # Thresholds: config file wins, else the constructor defaults.
        cfg = _load_tracker_thresholds(tracker_config)
        self.track_high_thresh = float(cfg.get("track_high_thresh", 0.5))
        self.track_low_thresh = float(cfg.get("track_low_thresh", 0.1))
        self.new_track_thresh = float(cfg.get("new_track_thresh", 0.5))
        self.max_missed_updates = int(cfg.get("track_buffer", max_missed_updates))
        match_thresh = cfg.get("match_thresh")
        # ByteTrack's match_thresh is a distance cap (1 - IoU); convert to a
        # minimum IoU for the first (high-confidence) stage.
        self._iou_min_high = (
            max(0.1, 1.0 - float(match_thresh)) if match_thresh is not None else float(match_iou_threshold)
        )
        # Second (low-confidence recovery) stage stays strict to avoid false
        # matches, per ByteTrack.
        self._iou_min_low = max(self._iou_min_high, 0.5)
        # Kept for backward compatibility / introspection.
        self.match_iou_threshold = self._iou_min_high

        self._tracks: dict[int, _TrackState] = {}
        self._next_track_id = 1

    # ------------------------------------------------------------------ #
    # Decoupled entry point: association only, no model inference.
    # ------------------------------------------------------------------ #
    def update_with_detections(self, detections) -> list[TrackedObject]:
        """Assign stable track IDs to already-computed detections.

        `detections` is any iterable of objects exposing .box (x1,y1,x2,y2),
        .class_name and .confidence (e.g. detection.detector.Detection). All
        other fields are carried through onto the returned TrackedObjects.
        """
        candidates = []
        for det in detections or []:
            box = getattr(det, "box", None)
            if not box or len(box) < 4:
                continue
            class_name = str(
                getattr(det, "class_name", None) or getattr(det, "object_type", None) or "object"
            )
            if self.classes_filter and class_name not in self.classes_filter:
                continue
            confidence = float(getattr(det, "confidence", 0.0) or 0.0)
            candidates.append(
                (
                    confidence,
                    class_name,
                    (int(box[0]), int(box[1]), int(box[2]), int(box[3])),
                    None,
                    det,
                )
            )
        return self._associate(candidates)

    # ------------------------------------------------------------------ #
    # Back-compat entry point: run the model, then associate.
    # ------------------------------------------------------------------ #
    def update(self, frame) -> list[TrackedObject]:
        """Runs detection + tracking on a single BGR frame. Prefer the decoupled
        update_with_detections() in the main pipeline; this remains for callers
        (and tests) that hand the tracker a model + frame directly."""
        predict = getattr(self.model, "predict", None)
        if callable(predict):
            results = predict(
                source=frame,
                conf=self.confidence_threshold,
                device=self.device,
                imgsz=self.image_size,
                agnostic_nms=self.class_agnostic_nms,
                iou=self.iou_threshold,
                max_det=self.max_detections,
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

        candidates = []
        if results:
            result = results[0]
            names = result.names
            boxes = result.boxes
            if boxes is not None:
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
                            None,
                        )
                    )
        if not candidates:
            candidates.extend(
                (0.65, "object proposal", box, None, None)
                for box in object_proposal_boxes(frame)
            )
        return self._associate(candidates)

    def reset(self) -> None:
        """Clear only this camera's association state."""
        self._tracks.clear()
        self._next_track_id = 1

    # ------------------------------------------------------------------ #
    # ByteTrack-style association.
    # ------------------------------------------------------------------ #
    def _associate(self, candidates) -> list[TrackedObject]:
        """candidates: list of (confidence, class_name, box, supplied_id, source)."""
        tracked: list[TrackedObject] = []
        matched_ids: set[int] = set()

        auto: list[tuple] = []
        for confidence, class_name, box, supplied_id, source in candidates:
            if supplied_id is not None:
                # An upstream tracker (e.g. ultralytics track()) already owns the
                # identity - honour it verbatim.
                track_id = int(supplied_id)
                self._commit(track_id, class_name, box, matched_ids)
                tracked.append(self._make_tracked(track_id, confidence, class_name, box, source))
            else:
                auto.append((confidence, class_name, box, source))

        if auto:
            high = [c for c in auto if c[0] >= self.track_high_thresh]
            low = [c for c in auto if self.track_low_thresh <= c[0] < self.track_high_thresh]

            # Stage 1: high-confidence detections against all live tracks.
            stage1, unmatched_high = self._match(high, self._iou_min_high, matched_ids)
            for track_id, confidence, class_name, box, source in stage1:
                self._commit(track_id, class_name, box, matched_ids)
                tracked.append(self._make_tracked(track_id, confidence, class_name, box, source))

            # Stage 2: recover remaining tracks with low-confidence detections.
            stage2, _ = self._match(low, self._iou_min_low, matched_ids)
            for track_id, confidence, class_name, box, source in stage2:
                self._commit(track_id, class_name, box, matched_ids)
                tracked.append(self._make_tracked(track_id, confidence, class_name, box, source))

            # New tracks: only confident, unmatched detections start an identity.
            for confidence, class_name, box, source in unmatched_high:
                if confidence < self.new_track_thresh:
                    continue
                track_id = self._next_track_id
                self._next_track_id += 1
                self._commit(track_id, class_name, box, matched_ids)
                tracked.append(self._make_tracked(track_id, confidence, class_name, box, source))

        self._age_unmatched_tracks(matched_ids)
        return tracked

    def _match(self, dets, iou_min, matched_ids):
        """Greedy IoU matching of `dets` to unmatched, same-class live tracks.

        Returns (matched, unmatched) where matched is a list of
        (track_id, confidence, class_name, box, source)."""
        matched = []
        unmatched = []
        for confidence, class_name, box, source in sorted(dets, key=lambda d: d[0], reverse=True):
            best_id = None
            best_iou = iou_min
            for track_id, state in self._tracks.items():
                if track_id in matched_ids or state.class_name != class_name:
                    continue
                iou = _box_iou(state.box, box)
                if iou >= best_iou:
                    best_iou = iou
                    best_id = track_id
            if best_id is not None:
                matched_ids.add(best_id)
                matched.append((best_id, confidence, class_name, box, source))
            else:
                unmatched.append((confidence, class_name, box, source))
        return matched, unmatched

    def _commit(self, track_id: int, class_name: str, box, matched_ids: set[int]) -> None:
        self._tracks[track_id] = _TrackState(class_name=class_name, box=box)
        matched_ids.add(track_id)

    def _make_tracked(self, track_id, confidence, class_name, box, source) -> TrackedObject:
        obj = TrackedObject(
            track_id=int(track_id),
            class_name=class_name,
            confidence=float(confidence),
            box=box,
        )
        if source is not None:
            obj.object_type = getattr(source, "object_type", None) or class_name
            obj.inventory_name = getattr(source, "inventory_name", None)
            obj.quantity = getattr(source, "quantity", 1)
            obj.quantity_grid = getattr(source, "quantity_grid", (1, 1, 1))
            obj.width_m = getattr(source, "width_m", None)
            obj.height_m = getattr(source, "height_m", None)
            obj.depth_m = getattr(source, "depth_m", None)
            obj.distance_m = getattr(source, "distance_m", None)
            obj.method = getattr(source, "method", None)
        return obj

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


def _load_tracker_thresholds(tracker_config) -> dict:
    """Read ByteTrack thresholds from a yaml path. Never raises; a missing file
    or parse error yields {} so the constructor defaults apply."""
    try:
        if not tracker_config or not str(tracker_config).endswith((".yaml", ".yml")):
            return {}
        path = Path(tracker_config)
        if not path.exists():
            return {}
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001 - tracking must degrade gracefully
        return {}


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
