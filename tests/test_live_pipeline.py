from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from events import EventEngine
from pipeline import LiveVisionPipeline
from rules import CountingRuleEngine, Line, RuleConfig
from stream import LiveFrame


class MemoryDB:
    def __init__(self):
        self.detections = []
        self.counts = []

    def record_detection(self, scan_run_id, record):
        self.detections.append(record)
        return len(self.detections)

    def record_count(self, scan_run_id, detection_id, event, block_id):
        self.counts.append((detection_id, event, block_id))
        return len(self.counts)


class FakeTracker:
    def __init__(self, positions):
        self.positions = iter(positions)

    def update(self, image):
        y = next(self.positions)
        return [SimpleNamespace(track_id=4, class_name="baget_box", confidence=.95,
                                box=(40, y - 5, 60, y + 5))]


def build_pipeline(db):
    rules = RuleConfig(frozenset({0}), ((0, 10), (100, 10), (100, 90), (0, 90)),
                       Line((0, 10), (100, 10)), Line((0, 90), (100, 90)),
                       minimum_track_age=1)
    events = EventEngine(db, scan_run_id=3, block_id="block-a")
    return LiveVisionPipeline(tracker=FakeTracker((0, 20, 80, 100)),
        rule_engine=CountingRuleEngine(rules), event_engine=events, database=db,
        pipeline_version="1", detector_version="yolo-baget", class_ids={"baget_box": 0})


def live_frame():
    return LiveFrame("camera-1", "stream-1", uuid4(), datetime.now(timezone.utc), object())


def test_canonical_pipeline_persists_every_detection_and_counts_once():
    db = MemoryDB()
    pipeline = build_pipeline(db)
    for _ in range(4):
        pipeline.process(live_frame())
    assert len(db.detections) == 4
    assert len(db.counts) == 1
    assert db.counts[0][1]["frame_uuid"] == db.detections[-1]["frame_uuid"]


def test_non_live_sources_are_rejected():
    try:
        LiveFrame("camera-1", "stream-1", uuid4(), datetime.now(timezone.utc), object(), "snapshot")
    except ValueError as exc:
        assert "live RTSP" in str(exc)
    else:
        raise AssertionError("snapshot inference source accepted")
