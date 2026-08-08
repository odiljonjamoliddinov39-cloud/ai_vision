from pathlib import Path

import cv2
import numpy as np

from database.vision_db import VisionDB
from dataset_builder import DatasetBuilder, DatasetError


def image_bytes(value: int = 120) -> bytes:
    image = np.full((120, 160, 3), value, dtype=np.uint8)
    cv2.rectangle(image, (20, 20), (80, 90), (value // 2, 20, 240), -1)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    return encoded.tobytes()


def test_ai_suggestion_requires_human_resolution(tmp_path: Path):
    builder = DatasetBuilder(tmp_path, VisionDB(str(tmp_path / "vision.db")))
    dataset = builder.create_dataset("1", "Baget Box")
    image = builder.ingest(dataset["id"], image_bytes(), suffix=".jpg", source="upload")
    builder.save_annotations(dataset["id"], image["id"], [{
        "x1": .1, "y1": .1, "x2": .5, "y2": .7,
        "provenance": "ai_suggested", "confidence": .88,
    }])
    try:
        builder.approve(dataset["id"], image["id"])
        assert False, "unverified AI annotation was promoted"
    except DatasetError as exc:
        assert "AI suggestions" in str(exc)


def test_verified_annotations_materialize_single_class_yolo(tmp_path: Path):
    builder = DatasetBuilder(tmp_path, VisionDB(str(tmp_path / "vision.db")))
    dataset = builder.create_dataset("1", "Baget Box")
    image = builder.ingest(dataset["id"], image_bytes(), suffix=".jpg", source="upload")
    builder.save_annotations(dataset["id"], image["id"], [{
        "x1": .1, "y1": .2, "x2": .5, "y2": .8, "provenance": "manual",
    }])
    builder.approve(dataset["id"], image["id"])
    root = tmp_path / "datasets" / "baget_box" / "v1"
    labels = list((root / "labels").rglob("*.txt"))
    assert len(labels) == 1
    assert labels[0].read_text(encoding="utf-8").startswith("0 ")
    assert "baget_box" in (root / "dataset.yaml").read_text(encoding="utf-8")


def test_near_duplicate_capture_is_skipped(tmp_path: Path):
    builder = DatasetBuilder(tmp_path, VisionDB(str(tmp_path / "vision.db")))
    dataset = builder.create_dataset("1", "Baget Box")
    first = builder.ingest(dataset["id"], image_bytes(), suffix=".jpg", source="camera")
    second = builder.ingest(dataset["id"], image_bytes(), suffix=".jpg", source="camera")
    assert not first["skipped"]
    assert second == {"skipped": True, "reason": "near_duplicate", "duplicate_of": first["id"]}
