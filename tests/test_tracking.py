"""
Tests for Phase 3/4 tracking + occupancy logic. These deliberately avoid
importing anything from `tracking.tracker` at module scope beyond the
plain dataclass, torch/ultralytics/cv2, or a camera/model, so they run
fast and don't require the YOLO weights to be downloaded.

Run with:
    pytest tests/
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dataclasses import dataclass

from tracking.presence import PresenceTracker
from tracking.tracker import ObjectTracker
from database.tracking_db import TrackingDB


@dataclass
class _FakeTrackedObject:
    track_id: int
    class_name: str
    confidence: float = 0.9
    box: tuple = (0, 0, 10, 10)


def test_presence_tracker_check_in_on_first_sight():
    tracker = PresenceTracker(grace_period_seconds=5.0)
    events = tracker.update("Camera 1", [_FakeTrackedObject(1, "person")], now=100.0)

    assert len(events) == 1
    assert events[0].event_type == "check_in"
    assert events[0].track_id == 1
    assert tracker.active_count() == 1


def test_presence_tracker_no_duplicate_check_in_while_present():
    tracker = PresenceTracker(grace_period_seconds=5.0)
    tracker.update("Camera 1", [_FakeTrackedObject(1, "person")], now=100.0)
    events = tracker.update("Camera 1", [_FakeTrackedObject(1, "person")], now=101.0)

    assert events == []
    assert tracker.active_count() == 1


def test_presence_tracker_check_out_after_grace_period():
    tracker = PresenceTracker(grace_period_seconds=5.0)
    tracker.update("Camera 1", [_FakeTrackedObject(1, "person")], now=100.0)

    # Object disappears; within the grace period, no check-out yet.
    events = tracker.expire(now=103.0)
    assert events == []
    assert tracker.active_count() == 1

    # Past the grace period, a check-out event fires and state is cleared.
    events = tracker.expire(now=106.0)
    assert len(events) == 1
    assert events[0].event_type == "check_out"
    assert events[0].track_id == 1
    assert tracker.active_count() == 0


def test_presence_tracker_tracks_multiple_cameras_independently():
    tracker = PresenceTracker(grace_period_seconds=5.0)
    tracker.update("Camera 1", [_FakeTrackedObject(1, "person")], now=100.0)
    tracker.update("Camera 2", [_FakeTrackedObject(1, "car")], now=100.0)

    assert tracker.active_count() == 2


def test_tracking_db_check_in_and_out_with_duration(tmp_path):
    db = TrackingDB(db_path=str(tmp_path / "tracking.db"))

    db.record_check_in(track_id=7, camera_name="Camera 1", class_name="person", timestamp="2026-01-01T10:00:00")
    current = db.current_occupancy()
    assert len(current) == 1
    assert current[0]["track_id"] == 7

    result = db.record_check_out(
        track_id=7, camera_name="Camera 1", class_name="person", timestamp="2026-01-01T10:05:00"
    )
    assert result.duration_seconds == 300.0

    # Once checked out, it should no longer appear in current occupancy.
    assert db.current_occupancy() == []


def test_tracking_db_occupancy_counts_by_class(tmp_path):
    db = TrackingDB(db_path=str(tmp_path / "tracking.db"))
    db.record_check_in(track_id=1, camera_name="Camera 1", class_name="person")
    db.record_check_in(track_id=2, camera_name="Camera 1", class_name="person")
    db.record_check_in(track_id=3, camera_name="Camera 1", class_name="car")

    counts = db.occupancy_counts()
    assert counts == {"person": 2, "car": 1}


def test_tracking_db_recent_events_most_recent_first(tmp_path):
    db = TrackingDB(db_path=str(tmp_path / "tracking.db"))
    db.record_check_in(track_id=1, camera_name="Camera 1", class_name="person", timestamp="2026-01-01T10:00:00")
    db.record_check_out(track_id=1, camera_name="Camera 1", class_name="person", timestamp="2026-01-01T10:01:00")

    events = db.recent_events(limit=10)
    assert len(events) == 2
    assert events[0]["event_type"] == "check_out"
    assert events[1]["event_type"] == "check_in"


def test_object_tracker_keeps_stationary_detection_and_image_size():
    class Values:
        def __init__(self, values):
            self.values = values

        def tolist(self):
            return self.values

        def __getitem__(self, index):
            value = self.values[index]
            return Values(value) if isinstance(value, list) else value

    class FakeBoxes:
        id = Values([17])
        cls = Values([0])
        conf = Values([0.2])
        xyxy = Values([[100, 100, 300, 300]])

    class FakeModel:
        def __init__(self):
            self.calls = []

        def track(self, **kwargs):
            self.calls.append(kwargs)
            return [
                type(
                    "Result",
                    (),
                    {"names": {0: "stack of sacks"}, "boxes": FakeBoxes()},
                )()
            ]

    model = FakeModel()
    tracker = ObjectTracker(
        model=model,
        confidence_threshold=0.08,
        tracker_config="config/warehouse_bytetrack.yaml",
        image_size=960,
        class_agnostic_nms=True,
    )

    first = tracker.update(object())
    second = tracker.update(object())

    assert first[0].track_id == second[0].track_id == 17
    assert first[0].class_name == "stack of sacks"
    assert model.calls[0]["persist"] is True
    assert model.calls[0]["imgsz"] == 960
    assert model.calls[0]["agnostic_nms"] is True


@dataclass
class _FakeDetection:
    class_name: str
    confidence: float
    box: tuple
    inventory_name: str | None = None
    quantity: int = 1


def _tracker():
    # No model needed for the decoupled path; use the warehouse config so the
    # ByteTrack thresholds (incl. track_buffer) drive behaviour.
    return ObjectTracker(model=None, tracker_config="config/warehouse_bytetrack.yaml")


def test_update_with_detections_keeps_stable_id_for_stationary_box():
    tracker = _tracker()
    det = _FakeDetection("baget box", 0.9, (100, 100, 200, 200))
    first = tracker.update_with_detections([det])
    # Same box, slightly nudged, next frame -> same ID.
    second = tracker.update_with_detections([_FakeDetection("baget box", 0.9, (102, 101, 202, 201))])
    assert first[0].track_id == second[0].track_id
    assert first[0].class_name == "baget box"


def test_track_buffer_survives_a_few_missed_frames():
    tracker = _tracker()
    first = tracker.update_with_detections([_FakeDetection("baget box", 0.9, (100, 100, 200, 200))])
    tid = first[0].track_id
    # Object missing for several frames (within track_buffer=60).
    for _ in range(5):
        tracker.update_with_detections([])
    # Reappears in roughly the same place -> keeps its original ID.
    again = tracker.update_with_detections([_FakeDetection("baget box", 0.9, (101, 100, 201, 201))])
    assert again[0].track_id == tid


def test_new_track_needs_new_track_thresh():
    tracker = _tracker()
    # warehouse_bytetrack.yaml: new_track_thresh 0.08, track_low_thresh 0.04.
    # A detection below the low threshold cannot start a track.
    out = tracker.update_with_detections([_FakeDetection("sack", 0.02, (10, 10, 40, 40))])
    assert out == []


def test_detection_fields_carry_through_tracking():
    tracker = _tracker()
    det = _FakeDetection("baget box", 0.9, (100, 100, 200, 200), inventory_name="Baget stack", quantity=7)
    out = tracker.update_with_detections([det])
    assert out[0].inventory_name == "Baget stack"
    assert out[0].quantity == 7


def test_distinct_boxes_get_distinct_ids():
    tracker = _tracker()
    out = tracker.update_with_detections(
        [
            _FakeDetection("baget box", 0.9, (0, 0, 50, 50)),
            _FakeDetection("baget box", 0.9, (300, 300, 360, 360)),
        ]
    )
    assert len({o.track_id for o in out}) == 2
