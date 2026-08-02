import time
from pathlib import Path

from detection.camera_processor import CameraVisionProcessor
from detection.detector import Detection
from detection.scheduler import LatestFrameInferenceScheduler
from main import _route_inference_objects
from tracking.presence import PresenceTracker
from tracking.tracker import TrackedObject


class Frame:
    shape = (720, 1280, 3)


class CountingDetector:
    def __init__(self):
        self.calls = 0

    def detect(self, frame):
        self.calls += 1
        return [Detection("baget box", 0.92, (10, 20, 100, 80), class_id=0)]


class CountingByteTrack:
    def __init__(self):
        self.calls = 0

    def update(self, detections, frame_shape, frame_sequence, observed_at):
        self.calls += 1
        source = detections[0]
        return [
            TrackedObject(
                track_id=17,
                class_name=source.class_name,
                confidence=source.confidence,
                box=source.box,
                class_id=source.class_id,
                camera_name="camera",
                frame_sequence=frame_sequence,
                observed_at=observed_at,
            )
        ]


def _take_result(scheduler, camera_name, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = scheduler.take_result(camera_name)
        if result is not None:
            return result
        time.sleep(0.01)
    raise AssertionError("scheduler did not produce an inference result")


def test_frame_is_detected_tracked_scheduled_and_routed_downstream_once():
    detector = CountingDetector()
    tracker = CountingByteTrack()
    processor = CameraVisionProcessor("camera", detector, tracker)
    scheduler = LatestFrameInferenceScheduler(
        {"camera": processor.process}, queue_size=1, workers=1
    )
    try:
        assert scheduler.submit("camera", Frame(), frame_at=123.5)
        inference_result = _take_result(scheduler, "camera")
    finally:
        scheduler.close()

    downstream_objects, tracked_objects = _route_inference_objects(
        inference_result, tracking_enabled=True
    )
    events = PresenceTracker().update(
        "camera", tracked_objects, inference_result.inference_at
    )

    assert detector.calls == 1
    assert tracker.calls == 1
    assert downstream_objects is inference_result.detections
    assert tracked_objects is inference_result.detections
    assert tracked_objects[0].track_id == 17
    assert [event.track_id for event in events] == [17]


def test_no_tracker_scheduler_result_remains_raw_detection_list():
    detector = CountingDetector()
    processor = CameraVisionProcessor("camera", detector, tracker=None)
    scheduler = LatestFrameInferenceScheduler(
        {"camera": processor.process}, queue_size=1, workers=1
    )
    try:
        assert scheduler.submit("camera", Frame(), frame_at=123.5)
        inference_result = _take_result(scheduler, "camera")
    finally:
        scheduler.close()

    downstream_objects, tracked_objects = _route_inference_objects(
        inference_result, tracking_enabled=False
    )
    assert detector.calls == 1
    assert tracked_objects is None
    assert downstream_objects is inference_result.detections
    assert isinstance(downstream_objects[0], Detection)


def test_main_never_invokes_a_second_detection_tracking_stage():
    main_source = (Path(__file__).resolve().parents[1] / "main.py").read_text(
        encoding="utf-8"
    )
    forbidden = "update_with_" + "detections"
    assert forbidden not in main_source
    assert "tracked_objects = inference_result.detections" in main_source

