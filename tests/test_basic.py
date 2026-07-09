"""
Basic sanity tests that don't require a camera, GPU, or downloading
the YOLO model. Run with:

    pytest tests/
"""

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from detection.detector import Detection, Detector
from detection.snapshot import SnapshotSaver


def test_detection_dataclass():
    d = Detection(class_name="person", confidence=0.98, box=(10, 10, 50, 50))
    assert d.class_name == "person"
    assert 0.0 <= d.confidence <= 1.0
    assert len(d.box) == 4


def test_snapshot_cooldown(tmp_path):
    saver = SnapshotSaver(
        save_dir=str(tmp_path), trigger_classes=["person"], cooldown_seconds=100
    )
    frame = _fake_frame()
    detections = [Detection(class_name="person", confidence=0.9, box=(0, 0, 10, 10))]

    first = saver.maybe_save("Camera 1", frame, detections)
    assert len(first) == 1
    assert os.path.exists(first[0])

    # Second call within cooldown window should NOT save again.
    second = saver.maybe_save("Camera 1", frame, detections)
    assert len(second) == 0


def _fake_frame():
    import numpy as np

    return np.zeros((100, 100, 3), dtype="uint8")


def test_open_vocabulary_detector_sets_prompts_and_image_size(monkeypatch):
    class FakeModel:
        def __init__(self):
            self.prompts = None
            self.predict_kwargs = None

        def set_classes(self, prompts):
            self.prompts = prompts

        def predict(self, **kwargs):
            self.predict_kwargs = kwargs
            return [SimpleNamespace(names={}, boxes=[])]

    model = FakeModel()
    monkeypatch.setitem(
        sys.modules,
        "ultralytics",
        SimpleNamespace(YOLO=lambda _path: model),
    )

    detector = Detector(
        model_path="warehouse-world.pt",
        confidence_threshold=0.08,
        class_prompts=["cardboard box", "stack of sacks"],
        image_size=960,
        class_agnostic_nms=True,
    )

    assert detector.detect(object()) == []
    assert model.prompts == ["cardboard box", "stack of sacks"]
    assert model.predict_kwargs["conf"] == 0.08
    assert model.predict_kwargs["imgsz"] == 960
    assert model.predict_kwargs["agnostic_nms"] is True
