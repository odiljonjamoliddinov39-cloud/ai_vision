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
