from dataclasses import replace
from datetime import datetime, timezone

from rules import CountingRuleEngine, Line, RuleConfig, TrackObservation, TrackState

CONFIG = RuleConfig(
    package_class_ids=frozenset({0}),
    counting_zone=((0, 10), (100, 10), (100, 90), (0, 90)),
    entry_line=Line((0, 10), (100, 10)),
    exit_line=Line((0, 90), (100, 90)),
    minimum_confidence=0.6,
    minimum_track_age=2,
)

def observation(previous, current, **changes):
    now = datetime.now(timezone.utc)
    item = TrackObservation(
        camera_id="camera-1",
        stream_id="stream-1",
        frame_uuid="frame-1",
        frame_timestamp=now,
        detection_timestamp=now,
        track_id=7,
        class_id=0,
        confidence=0.9,
        center=current,
        previous_center=previous,
        track_age=3,
        pipeline_version="1",
        detector_version="yolo",
        recognition_source="detector",
        processing_latency_ms=12.5,
    )
    return replace(item, **changes)

def test_valid_track_counts_once_after_entry_zone_and_exit():
    engine = CountingRuleEngine(CONFIG)
    assert engine.evaluate(observation((50, 0), (50, 20))) is None
    assert engine.state_for(7) is TrackState.INSIDE

    event = engine.evaluate(
        observation((50, 80), (50, 100), frame_uuid="exit-frame")
    )
    assert event is not None
    assert event.frame_uuid == "exit-frame"
    assert event.camera_id == "camera-1"
    assert engine.state_for(7) is TrackState.FINISHED
    assert engine.evaluate(observation((50, 80), (50, 100))) is None

def test_rejects_wrong_class_low_confidence_and_young_tracks():
    cases = (
        {"class_id": 9},
        {"confidence": 0.59},
        {"track_age": 1},
    )
    for changes in cases:
        engine = CountingRuleEngine(CONFIG)
        assert engine.evaluate(observation((50, 0), (50, 20), **changes)) is None
        assert engine.state_for(7) is TrackState.OUTSIDE

def test_ignore_zone_prevents_transition():
    config = replace(CONFIG, ignore_zones=(((40, 15), (60, 15), (60, 25), (40, 25)),))
    engine = CountingRuleEngine(config)
    assert engine.evaluate(observation((50, 0), (50, 20))) is None
    assert engine.state_for(7) is TrackState.OUTSIDE

