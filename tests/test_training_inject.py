import asyncio
import io

import cv2
import numpy as np
from fastapi import UploadFile
from starlette.datastructures import Headers

from api import server


def _image(color):
    frame = np.zeros((60, 80, 3), dtype=np.uint8)
    frame[:, :] = color
    return frame


def _upload(color, name="a.jpg"):
    ok, buffer = cv2.imencode(".jpg", _image(color))
    assert ok
    return UploadFile(
        filename=name,
        file=io.BytesIO(buffer.tobytes()),
        headers=Headers({"content-type": "image/jpeg"}),
    )


def _point_dataset(monkeypatch, root):
    root.mkdir(parents=True, exist_ok=True)
    (root / "data.yaml").write_text("names:\n  0: baget box\n  1: sack\n", encoding="utf-8")
    monkeypatch.setattr(server, "TRAINING_DATASET_ROOT", root)
    monkeypatch.setattr(server, "TRAINING_DATASET_YAML", root / "data.yaml")
    monkeypatch.setattr(server, "TRAINING_PROMPTS_PATH", root / "prompts.json")


def test_training_inject_saves_images_and_prompts(tmp_path, monkeypatch):
    _point_dataset(monkeypatch, tmp_path / "baget_box")

    result = asyncio.run(
        server.training_inject(
            split="train",
            prompts="baget box, flour sack",
            files=[_upload((10, 20, 30))],
        )
    )

    assert result["images_saved"] == 1
    assert "baget box" in result["prompts_added"]
    assert result["dataset"]["splits"]["train"]["images"] == 1

    # Duplicate prompt is not re-added; a val image lands in the val split.
    again = asyncio.run(
        server.training_inject(split="val", prompts="baget box", files=[_upload((1, 2, 3))])
    )
    assert again["prompts_added"] == []
    assert again["dataset"]["splits"]["val"]["images"] == 1


def test_training_dataset_counts_labels_and_negatives(tmp_path, monkeypatch):
    root = tmp_path / "baget_box"
    (root / "images" / "train").mkdir(parents=True)
    (root / "labels" / "train").mkdir(parents=True)
    _point_dataset(monkeypatch, root)

    cv2.imwrite(str(root / "images" / "train" / "a.jpg"), _image((1, 2, 3)))
    (root / "labels" / "train" / "a.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    cv2.imwrite(str(root / "images" / "train" / "b.jpg"), _image((4, 5, 6)))
    (root / "labels" / "train" / "b.txt").write_text("", encoding="utf-8")  # negative
    cv2.imwrite(str(root / "images" / "train" / "c.jpg"), _image((7, 8, 9)))  # unlabeled

    stats = server.training_dataset()
    train = stats["splits"]["train"]
    assert (train["images"], train["labeled"], train["negatives"], train["unlabeled"]) == (3, 1, 1, 1)
    assert stats["class_instances"].get("0") == 1
