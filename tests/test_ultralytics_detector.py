import sys
import types

from detection.detector import Detector


class FakeTensor:
    def __init__(self, values):
        self.values = values

    def tolist(self):
        return self.values


class FakeBoxes:
    cls = FakeTensor([0])
    conf = FakeTensor([0.91])
    xyxy = FakeTensor([[10.2, 20.8, 110.9, 220.1]])


class FakeResult:
    names = {0: "baget box"}
    boxes = FakeBoxes()


class FakeYOLOE:
    def __init__(self, model_path):
        self.model_path = model_path
        self.prompts = []
        self.predict_kwargs = None

    def set_classes(self, prompts):
        self.prompts = list(prompts)

    def predict(self, **kwargs):
        self.predict_kwargs = kwargs
        return [FakeResult()]


def test_detector_uses_ultralytics_yoloe_prompts_and_current_predict_options(monkeypatch):
    module = types.ModuleType("ultralytics")
    module.YOLOE = FakeYOLOE
    module.YOLOWorld = FakeYOLOE
    module.YOLO = FakeYOLOE
    monkeypatch.setitem(sys.modules, "ultralytics", module)

    detector = Detector(
        model_path="yoloe-26s-seg.pt",
        class_prompts=["baget box", "cardboard box", "baget box"],
        confidence_threshold=0.18,
        image_size=640,
        iou_threshold=0.55,
        max_detections=200,
    )
    detections = detector.detect(object())

    assert detector.model.prompts == ["baget box", "cardboard box"]
    assert detector.model.predict_kwargs["imgsz"] == 640
    assert detector.model.predict_kwargs["iou"] == 0.55
    assert detector.model.predict_kwargs["max_det"] == 200
    assert detections[0].class_name == "baget box"
    assert detections[0].confidence == 0.91
    assert detections[0].box == (10, 20, 110, 220)
    assert detections[0].method == "ultralytics:yoloe-26s-seg.pt"


def test_detector_falls_back_to_world_model(monkeypatch):
    module = types.ModuleType("ultralytics")

    class FailingYOLOE:
        def __init__(self, _model_path):
            raise RuntimeError("primary unavailable")

    module.YOLOE = FailingYOLOE
    module.YOLOWorld = FakeYOLOE
    module.YOLO = FakeYOLOE
    monkeypatch.setitem(sys.modules, "ultralytics", module)

    detector = Detector(
        model_path="yoloe-26s-seg.pt",
        fallback_model_path="yolov8s-worldv2.pt",
        class_prompts=["box"],
    )

    assert detector.model is not None
    assert detector.model_path == "yolov8s-worldv2.pt"
    assert detector.health()["fallback_used"] is True
