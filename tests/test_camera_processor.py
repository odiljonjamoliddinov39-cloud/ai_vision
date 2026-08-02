from detection.camera_processor import CameraVisionProcessor
from detection.detector import Detection


class DetectorDouble:
    def __init__(self):
        self.calls = 0

    def detect(self, frame):
        self.calls += 1
        return [Detection("baget box", 0.9, (1, 2, 3, 4), class_id=0)]


class TrackerDouble:
    def __init__(self):
        self.calls = []

    def update(self, **kwargs):
        self.calls.append(kwargs)
        return ["tracked"]

    def reset(self, reason):
        self.reset_reason = reason


class Frame:
    shape = (720, 1280, 3)


def test_processor_runs_detector_and_tracker_once_with_same_metadata():
    detector = DetectorDouble()
    tracker = TrackerDouble()
    processor = CameraVisionProcessor("camera", detector, tracker)
    assert processor.process(Frame(), 42, 123.5) == ["tracked"]
    assert detector.calls == 1
    assert len(tracker.calls) == 1
    assert tracker.calls[0]["frame_sequence"] == 42
    assert tracker.calls[0]["observed_at"] == 123.5
    assert tracker.calls[0]["frame_shape"] == (720, 1280, 3)
