"""
Tests for zone-based counting (tracking/zones.py) and warehouse event
recognition + theft-suspicion rules (tracking/warehouse.py). Pure
Python — no cv2/torch/YOLO weights needed.

Run with:
    pytest tests/
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dataclasses import dataclass
from datetime import datetime

from tracking.zones import Zone, ZoneEvent, ZoneMonitor, load_zones, point_in_polygon
from tracking.warehouse import WarehouseEventDetector
from database.tracking_db import TrackingDB


@dataclass
class _FakeTrack:
    track_id: int
    class_name: str
    box: tuple  # pixel (x1, y1, x2, y2)
    confidence: float = 0.9


FRAME = (100, 100)  # width, height

# Left half of the frame is "inside the warehouse".
LEFT_ZONE = Zone("Warehouse", "Camera 1", polygon=[(0.0, 0.0), (0.5, 0.0), (0.5, 1.0), (0.0, 1.0)])


def _box_at(x_center: float, y_bottom: float = 50, size: int = 10) -> tuple:
    half = size // 2
    return (x_center - half, y_bottom - size, x_center + half, y_bottom)


# ---------------------------------------------------------------------------
# point_in_polygon / Zone
# ---------------------------------------------------------------------------

def test_point_in_polygon_square():
    square = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    assert point_in_polygon(0.5, 0.5, square)
    assert not point_in_polygon(1.5, 0.5, square)


def test_full_frame_zone_contains_everything_visible():
    zone = Zone("All", "Camera 1", polygon=None)
    assert zone.contains(0.01, 0.99)
    assert zone.contains(0.99, 0.01)


def test_load_zones_defaults_to_full_frame():
    zones = load_zones([{"name": "Warehouse", "camera": "Camera 1"}])
    assert zones[0].polygon is None
    zones = load_zones([{"name": "W", "camera": "Cam", "polygon": [[0, 0], [1, 0], [1, 1]]}])
    assert zones[0].polygon == [(0, 0), (1, 0), (1, 1)]


# ---------------------------------------------------------------------------
# ZoneMonitor: enter/exit with hysteresis
# ---------------------------------------------------------------------------

def test_object_first_seen_inside_zone_fires_enter():
    monitor = ZoneMonitor([LEFT_ZONE], min_frames=3)
    events = monitor.update("Camera 1", [_FakeTrack(1, "suitcase", _box_at(25))], now=1.0, frame_size=FRAME)
    assert [e.event_type for e in events] == ["enter"]
    assert monitor.counts()["Warehouse"] == {"suitcase": 1}


def test_object_first_seen_outside_zone_fires_nothing():
    monitor = ZoneMonitor([LEFT_ZONE], min_frames=3)
    events = monitor.update("Camera 1", [_FakeTrack(1, "suitcase", _box_at(75))], now=1.0, frame_size=FRAME)
    assert events == []
    assert monitor.counts()["Warehouse"] == {}


def test_exit_requires_min_frames_hysteresis():
    monitor = ZoneMonitor([LEFT_ZONE], min_frames=3)
    monitor.update("Camera 1", [_FakeTrack(1, "suitcase", _box_at(25))], now=1.0, frame_size=FRAME)

    # 2 frames outside: not enough to flip
    for t in (2.0, 3.0):
        events = monitor.update("Camera 1", [_FakeTrack(1, "suitcase", _box_at(75))], now=t, frame_size=FRAME)
        assert events == []
    assert monitor.counts()["Warehouse"] == {"suitcase": 1}

    # 3rd consecutive frame outside: exit fires
    events = monitor.update("Camera 1", [_FakeTrack(1, "suitcase", _box_at(75))], now=4.0, frame_size=FRAME)
    assert [e.event_type for e in events] == ["exit"]
    assert monitor.counts()["Warehouse"] == {}


def test_flapping_on_zone_edge_does_not_fire():
    monitor = ZoneMonitor([LEFT_ZONE], min_frames=3)
    monitor.update("Camera 1", [_FakeTrack(1, "suitcase", _box_at(25))], now=1.0, frame_size=FRAME)

    # alternate inside/outside — streak keeps resetting, no events
    for i, x in enumerate([75, 25, 75, 25, 75, 25]):
        events = monitor.update(
            "Camera 1", [_FakeTrack(1, "suitcase", _box_at(x))], now=2.0 + i, frame_size=FRAME
        )
        assert events == []


def test_lost_track_inside_zone_expires_as_exit():
    monitor = ZoneMonitor([LEFT_ZONE], min_frames=3, lost_after_seconds=5.0)
    monitor.update("Camera 1", [_FakeTrack(1, "suitcase", _box_at(25))], now=1.0, frame_size=FRAME)

    assert monitor.expire(now=3.0) == []  # still within grace
    events = monitor.expire(now=7.0)
    assert [e.event_type for e in events] == ["exit"]
    assert monitor.counts()["Warehouse"] == {}


def test_counts_multiple_classes_and_objects():
    monitor = ZoneMonitor([LEFT_ZONE], min_frames=3)
    monitor.update(
        "Camera 1",
        [
            _FakeTrack(1, "suitcase", _box_at(25)),
            _FakeTrack(2, "suitcase", _box_at(30)),
            _FakeTrack(3, "person", _box_at(40)),
            _FakeTrack(4, "person", _box_at(80)),  # outside
        ],
        now=1.0,
        frame_size=FRAME,
    )
    assert monitor.counts()["Warehouse"] == {"suitcase": 2, "person": 1}


# ---------------------------------------------------------------------------
# WarehouseEventDetector: item events + theft rules
# ---------------------------------------------------------------------------

def _zone_event(event_type: str, track_id: int = 1, class_name: str = "box", at: float = 1000.0):
    return ZoneEvent("Warehouse", "Camera 1", track_id, class_name, event_type, at)


def _ts(hour: int, minute: int = 0) -> float:
    return datetime(2026, 7, 8, hour, minute).timestamp()


def test_item_enter_and_exit_become_item_in_out():
    detector = WarehouseEventDetector(item_classes=["box"], working_hours=None)
    events = detector.process([_zone_event("enter"), _zone_event("exit")])
    assert [e.event_type for e in events] == ["item_in", "item_out"]


def test_person_events_are_tracked_not_flagged():
    detector = WarehouseEventDetector(item_classes=["box"], working_hours=None)
    events = detector.process([_zone_event("enter", track_id=9, class_name="person")])
    assert [e.event_type for e in events] == ["person_in"]
    assert not events[0].suspicious


def test_unknown_classes_are_ignored():
    detector = WarehouseEventDetector(item_classes=["box"], working_hours=None)
    assert detector.process([_zone_event("enter", class_name="dog")]) == []


def test_item_out_during_working_hours_with_person_is_not_suspicious():
    detector = WarehouseEventDetector(
        item_classes=["box"], working_hours={"start": "08:00", "end": "18:00"}
    )
    events = detector.process(
        [
            _zone_event("enter", track_id=9, class_name="person", at=_ts(10)),
            _zone_event("exit", track_id=1, at=_ts(10, 30)),
        ]
    )
    item_out = events[-1]
    assert item_out.event_type == "item_out"
    assert not item_out.suspicious
    assert item_out.persons_in_zone == 1


def test_after_hours_removal_is_flagged():
    detector = WarehouseEventDetector(
        item_classes=["box"],
        working_hours={"start": "08:00", "end": "18:00"},
        flag_unattended=False,
    )
    events = detector.process([_zone_event("exit", at=_ts(23))])
    assert events[0].suspicious
    assert "after_hours" in events[0].reasons


def test_unattended_removal_is_flagged():
    detector = WarehouseEventDetector(item_classes=["box"], working_hours=None)
    events = detector.process([_zone_event("exit", at=_ts(12))])
    assert events[0].suspicious
    assert "unattended" in events[0].reasons


def test_bulk_removal_is_flagged():
    detector = WarehouseEventDetector(
        item_classes=["box"],
        working_hours=None,
        flag_unattended=False,
        bulk_removal_count=3,
        bulk_removal_window_seconds=60.0,
    )
    base = _ts(12)
    events = detector.process(
        [
            _zone_event("exit", track_id=1, at=base),
            _zone_event("exit", track_id=2, at=base + 10),
            _zone_event("exit", track_id=3, at=base + 20),
        ]
    )
    assert [e.suspicious for e in events] == [False, False, True]
    assert "bulk_removal" in events[2].reasons


def test_slow_removals_outside_window_not_bulk_flagged():
    detector = WarehouseEventDetector(
        item_classes=["box"],
        working_hours=None,
        flag_unattended=False,
        bulk_removal_count=3,
        bulk_removal_window_seconds=60.0,
    )
    base = _ts(12)
    events = detector.process(
        [
            _zone_event("exit", track_id=1, at=base),
            _zone_event("exit", track_id=2, at=base + 120),
            _zone_event("exit", track_id=3, at=base + 240),
        ]
    )
    assert all(not e.suspicious for e in events)


def test_overnight_working_hours():
    detector = WarehouseEventDetector(
        item_classes=["box"],
        working_hours={"start": "22:00", "end": "06:00"},
        flag_unattended=False,
    )
    # 23:00 is inside a 22:00-06:00 shift => not suspicious
    assert not detector.process([_zone_event("exit", at=_ts(23))])[0].suspicious
    # 12:00 is outside it => suspicious
    assert detector.process([_zone_event("exit", track_id=2, at=_ts(12))])[0].suspicious


# ---------------------------------------------------------------------------
# TrackingDB: zone_events persistence
# ---------------------------------------------------------------------------

def test_zone_events_roundtrip(tmp_path):
    db = TrackingDB(db_path=str(tmp_path / "t.db"))
    db.record_zone_event(
        "Warehouse", "Camera 1", 1, "box", "item_in", timestamp="2026-07-08T10:00:00"
    )
    db.record_zone_event(
        "Warehouse", "Camera 1", 1, "box", "item_out",
        suspicious=True, reasons=["after_hours", "unattended"], persons_in_zone=0,
        timestamp="2026-07-08T23:00:00",
    )

    events = db.recent_zone_events(limit=10)
    assert len(events) == 2
    assert events[0]["event_type"] == "item_out"
    assert events[0]["suspicious"] is True
    assert events[0]["reasons"] == ["after_hours", "unattended"]

    alerts = db.recent_zone_events(limit=10, suspicious_only=True)
    assert len(alerts) == 1

    totals = db.zone_event_totals()
    assert totals == {"item_in": 1, "item_out": 1, "suspicious": 1}
