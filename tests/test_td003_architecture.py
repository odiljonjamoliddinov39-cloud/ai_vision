from datetime import datetime, timezone
from types import SimpleNamespace
import threading

import numpy as np

from counting import CountingEngine
from database.vision_db import VisionDB
from detection.detector import Detector
from events import EventEngine
from pipeline import LiveVisionPipeline
from recognition import RecognitionEngine
from recognition.product_recognizer import ProductRecognition
from rules import Line, ObjectRuleEngine, RuleConfig


RULES = RuleConfig(
    package_class_ids=frozenset({0}),
    counting_zone=((0, 10), (100, 10), (100, 90), (0, 90)),
    entry_line=Line((0, 10), (100, 10)),
    exit_line=Line((0, 90), (100, 90)),
    minimum_confidence=0.5,
    minimum_track_age=1,
    target_products=frozenset({"Baget Box"}),
)


class LocalRecognizer:
    def poll(self):
        pass

    def get_track_result(self, camera, track_id):
        return None

    def recognize_local(self, crop):
        return ProductRecognition(name="Baget Box", confidence=0.97, source="local_embedding")


def test_recognition_engine_is_local_first_for_every_detection():
    detection = SimpleNamespace(
        track_id=4, class_name="box", confidence=0.8,
        box=(0, 0, 10, 10), inventory_name=None,
    )
    engine = RecognitionEngine(LocalRecognizer())

    result = engine.recognize("camera-1", np.zeros((20, 20, 3), dtype=np.uint8), [detection])[0]

    assert result.identity == "Baget Box"
    assert result.source == "local_embedding"
    assert detection.inventory_name == "Baget Box"


def test_detector_forwards_all_model_observations_without_business_filter():
    boxes = SimpleNamespace(
        cls=SimpleNamespace(tolist=lambda: [0, 1]),
        conf=SimpleNamespace(tolist=lambda: [0.9, 0.8]),
        xyxy=SimpleNamespace(tolist=lambda: [[1, 2, 10, 12], [4, 5, 14, 18]]),
    )
    model = SimpleNamespace(
        predict=lambda **kwargs: [SimpleNamespace(boxes=boxes, names={0: "box", 1: "forklift"})]
    )
    detector = Detector.__new__(Detector)
    detector.model = model
    detector.confidence_threshold = 0.25
    detector.iou_threshold = 0.55
    detector.max_detections = 300
    detector.device = "cpu"
    detector.image_size = 640
    detector.class_agnostic_nms = False
    detector.compile_model = False
    detector.model_path = "test"
    detector.configured_classes = ("box",)
    detector._lock = threading.Lock()

    detections = detector.detect(np.zeros((20, 20, 3), dtype=np.uint8))

    assert [item.class_name for item in detections] == ["box", "forklift"]


class MemoryDB:
    def __init__(self):
        self.detections = []
        self.recognitions = []
        self.decisions = []
        self.counts = []

    def record_detection(self, scan_id, record):
        self.detections.append(record)
        return len(self.detections)

    def record_recognition(self, scan_id, detection_id, recognition):
        self.recognitions.append(recognition)
        return len(self.recognitions)

    def record_rule_decision(self, scan_id, detection_id, decision):
        self.decisions.append(decision)
        return len(self.decisions)

    def record_count(self, scan_id, detection_id, event, block_id):
        self.counts.append(event)
        return len(self.counts)


class Processor:
    def __init__(self):
        self.positions = iter((0, 20, 80, 100))

    def process(self, frame, sequence, observed_at):
        y = next(self.positions)
        return [SimpleNamespace(
            track_id=7, class_id=0, class_name="box", confidence=0.92,
            box=(40, y - 5, 60, y + 5), inventory_name=None,
        )]

    def reset(self, reason):
        pass


def test_pipeline_persists_detection_recognition_rule_and_approved_count():
    db = MemoryDB()
    pipeline = LiveVisionPipeline(
        camera_id="camera-1", stream_id="stream-1", processor=Processor(),
        recognition_engine=RecognitionEngine(LocalRecognizer()),
        rule_engine=ObjectRuleEngine(RULES), counting_engine=CountingEngine(RULES),
        event_engine=EventEngine(db, 1, "warehouse-a"), database=db,
        pipeline_version="2.0", detector_version="universal", class_ids={"box": 0},
    )

    for sequence in range(4):
        pipeline.process(np.zeros((120, 120, 3), dtype=np.uint8), sequence, datetime.now(timezone.utc).timestamp())

    assert len(db.detections) == 4
    assert len(db.recognitions) == 4
    assert all(result.source == "local_embedding" for result in db.recognitions)
    assert len(db.decisions) == 4
    assert all(decision.keep for decision in db.decisions)
    assert len(db.counts) == 1


def test_vision_db_persists_new_architecture_layers(tmp_path):
    db = VisionDB(str(tmp_path / "vision.db"))
    with db.db.connect() as connection:
        tables = {
            row["name"] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert {"detections", "recognitions", "rule_decisions", "counts", "operator_actions"} <= tables
