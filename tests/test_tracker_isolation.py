import sys
import types
from pathlib import Path

import numpy as np

from detection.detector import Detection
from tracking.bytetrack_adapter import ByteTrackAdapter


class FakeBoxes:
    def __init__(self, rows, _shape):
        self.rows = np.asarray(rows)


class FakeSTrack:
    _count = 0

    @classmethod
    def next_id(cls):
        cls._count += 1
        return cls._count

    @classmethod
    def reset_id(cls):
        cls._count = 0


class FakeBYTETracker:
    track_class = FakeSTrack

    def __init__(self, args):
        self.args = args
        self.frame_id = 0
        self.reset_calls = 0
        self.reset_id()

    def update(self, boxes):
        self.frame_id += 1
        return np.asarray([
            [*row[:4], self.track_class.next_id(), row[4], row[5], index]
            for index, row in enumerate(boxes.rows)
        ], dtype=float).reshape((-1, 8))

    def reset(self):
        self.frame_id = 0
        self.reset_calls += 1
        self.reset_id()

    def reset_id(self):
        self.track_class.reset_id()


def _install_fake_ultralytics(monkeypatch):
    trackers = types.ModuleType("ultralytics.trackers")
    byte_tracker = types.ModuleType("ultralytics.trackers.byte_tracker")
    byte_tracker.BYTETracker = FakeBYTETracker
    byte_tracker.STrack = FakeSTrack
    engine = types.ModuleType("ultralytics.engine")
    results = types.ModuleType("ultralytics.engine.results")
    results.Boxes = FakeBoxes
    for name, module in {
        "ultralytics": types.ModuleType("ultralytics"),
        "ultralytics.trackers": trackers,
        "ultralytics.trackers.byte_tracker": byte_tracker,
        "ultralytics.engine": engine,
        "ultralytics.engine.results": results,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)


def _config():
    return str(Path(__file__).resolve().parents[1] / "config" / "warehouse_bytetrack.yaml")


def _detection(confidence=0.9):
    return Detection("baget box", confidence, (10, 20, 50, 80), class_id=7)


def test_trackers_are_isolated_and_preserve_detection_fields(monkeypatch):
    _install_fake_ultralytics(monkeypatch)
    first = ByteTrackAdapter("one", _config())
    second = ByteTrackAdapter("two", _config())

    a = first.update([_detection()], (100, 100, 3), 1, 10.0)[0]
    b = second.update([_detection()], (100, 100, 3), 1, 10.0)[0]
    assert a.track_id == 1
    assert b.track_id == 1
    assert a.class_name == "baget box"
    assert a.class_id == 7
    assert a.camera_name == "one"
    assert a.frame_sequence == 1


def test_empty_detections_age_tracker_and_out_of_order_is_rejected(monkeypatch):
    _install_fake_ultralytics(monkeypatch)
    tracker = ByteTrackAdapter("one", _config())
    assert tracker.update([], (100, 100, 3), 2, 10.0) == []
    assert tracker._tracker.frame_id == 1
    assert tracker.update([_detection()], (100, 100, 3), 1, 11.0) == []
    health = tracker.health()
    assert health["empty_updates"] == 1
    assert health["out_of_order_skips"] == 1


def test_resolution_change_resets_only_that_tracker(monkeypatch):
    _install_fake_ultralytics(monkeypatch)
    tracker = ByteTrackAdapter("one", _config())
    tracker.update([_detection()], (100, 100, 3), 1, 10.0)
    tracker.update([_detection()], (200, 100, 3), 2, 11.0)
    assert tracker.health()["last_reset_reason"] == "resolution_change"
    assert tracker.health()["last_sequence"] == 2


def test_main_has_no_tracker_inference_or_custom_iou_fallback():
    root = Path(__file__).resolve().parents[1]
    tracker_source = (root / "tracking" / "tracker.py").read_text(encoding="utf-8")
    adapter_source = (root / "tracking" / "bytetrack_adapter.py").read_text(encoding="utf-8")
    main_source = (root / "main.py").read_text(encoding="utf-8")
    combined = tracker_source + adapter_source
    assert ".predict(" not in combined
    assert ".track(" not in combined
    assert "_box_iou" not in combined
    assert "object_proposal_boxes" not in combined
    assert "CameraVisionProcessor" in main_source
