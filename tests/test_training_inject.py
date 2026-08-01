import asyncio
import io
import json
import time

import cv2
import numpy as np
import yaml
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


def test_training_annotate_writes_labels_and_negatives(tmp_path, monkeypatch):
    _point_dataset(monkeypatch, tmp_path / "baget_box")

    boxes = json.dumps(
        [
            {"bbox": {"x1": 10, "y1": 10, "x2": 50, "y2": 40}, "name": "baget box", "necessary": True},
            {"bbox": {"x1": 0, "y1": 0, "x2": 20, "y2": 20}, "name": "sack", "necessary": False},
        ]
    )
    result = asyncio.run(server.training_annotate(split="train", boxes=boxes, file=_upload((9, 9, 9))))

    assert result["labeled"] == 1
    assert result["negative"] is False
    labels = list((tmp_path / "baget_box" / "labels" / "train").glob("*.txt"))
    assert labels[0].read_text(encoding="utf-8").strip().startswith("0 ")

    negative = json.dumps(
        [{"bbox": {"x1": 1, "y1": 1, "x2": 5, "y2": 5}, "name": "sack", "necessary": False}]
    )
    result_neg = asyncio.run(server.training_annotate(split="train", boxes=negative, file=_upload((1, 1, 1))))
    assert result_neg["labeled"] == 0
    assert result_neg["negative"] is True


def test_training_resolve_class_adds_new_class(tmp_path, monkeypatch):
    root = tmp_path / "baget_box"
    _point_dataset(monkeypatch, root)

    assert server._training_resolve_class("Baget Box") == 0  # matches existing (normalized)
    assert server._training_resolve_class("Pallet") == 2  # new class appended
    data = yaml.safe_load((root / "data.yaml").read_text(encoding="utf-8"))
    assert data["names"][2] == "Pallet"


def test_training_analytics_apply_writes_and_replaces(tmp_path, monkeypatch):
    root = tmp_path / "baget_box"
    _point_dataset(monkeypatch, root)
    staging = tmp_path / "staging"
    monkeypatch.setattr(server, "TRAINING_STAGING_DIR", staging)
    monkeypatch.setattr(server, "TRAINING_APPLIED_PATH", root / "applied.json")

    stage = staging / "sack"
    stage.mkdir(parents=True)
    for i in range(2):
        cv2.imwrite(str(stage / f"crop_{i:02d}.jpg"), _image((5, 5, 5)))

    kept = asyncio.run(
        server.training_analytics_apply(
            server.TrainingApply(group_id="sack", name="Sack", keep=True, split="train")
        )
    )
    assert kept["applied"] == 2
    labels = sorted((root / "labels" / "train").glob("*.txt"))
    assert len(labels) == 2
    assert labels[0].read_text(encoding="utf-8").strip().endswith("0.5 0.5 1.000000 1.000000") or \
        labels[0].read_text(encoding="utf-8").strip().endswith("0.5 0.5 1.0 1.0")

    # Re-apply as ignore: replaces (no duplicates) and writes negatives.
    ignored = asyncio.run(
        server.training_analytics_apply(
            server.TrainingApply(group_id="sack", name="Sack", keep=False, split="train")
        )
    )
    assert ignored["applied"] == 2
    images = sorted((root / "images" / "train").glob("*.jpg"))
    assert len(images) == 2  # not duplicated
    assert all(p.read_text(encoding="utf-8").strip() == "" for p in (root / "labels" / "train").glob("*.txt"))


def test_training_cluster_boxes_groups_adjacent():
    # Two boxes touching form one stack; a far-away box is its own cluster.
    boxes = [(0, 0, 10, 10), (10, 0, 20, 10), (200, 200, 210, 210)]
    clusters = server._training_cluster_boxes(boxes)
    sizes = sorted(len(c) for c in clusters)
    assert sizes == [1, 2]


def test_training_box_iou_gap_zero_when_overlapping():
    assert server._training_box_iou_gap((0, 0, 10, 10), (5, 5, 15, 15)) == 0.0
    assert server._training_box_iou_gap((0, 0, 10, 10), (100, 100, 110, 110)) > 1.0


def test_training_apply_persists_count(tmp_path, monkeypatch):
    root = tmp_path / "baget_box"
    _point_dataset(monkeypatch, root)
    staging = tmp_path / "staging"
    monkeypatch.setattr(server, "TRAINING_STAGING_DIR", staging)
    monkeypatch.setattr(server, "TRAINING_APPLIED_PATH", root / "applied.json")

    stage = staging / "search-1-1"
    stage.mkdir(parents=True)
    cv2.imwrite(str(stage / "crop_00.jpg"), _image((7, 7, 7)))

    asyncio.run(
        server.training_analytics_apply(
            server.TrainingApply(group_id="search-1-1", name="Stack of baget boxes", keep=True, count=56)
        )
    )
    counts = json.loads((root / "counts.json").read_text(encoding="utf-8"))
    assert counts["search-1-1"]["count"] == 56
    assert counts["search-1-1"]["name"] == "Stack of baget boxes"


def test_training_search_reports_diagnostics_without_model(tmp_path, monkeypatch):
    _point_dataset(monkeypatch, tmp_path / "baget_box")
    monkeypatch.setattr(server, "_training_detector", lambda: None)
    monkeypatch.setattr(server, "_catalog_health_snapshot", lambda: {"cameras": []})
    monkeypatch.setattr(server, "SNAPSHOT_DIR", tmp_path / "snaps")
    (tmp_path / "snaps").mkdir()
    out = server._training_search_sync("baget boxes")
    assert out["rows"] == []
    assert out["diagnostics"]["model"] is False


def test_training_search_background_job_completes_and_persists(tmp_path, monkeypatch):
    _point_dataset(monkeypatch, tmp_path / "baget_box")
    monkeypatch.setattr(server, "_training_detector", lambda: None)
    monkeypatch.setattr(server, "_catalog_health_snapshot", lambda: {"cameras": []})
    monkeypatch.setattr(server, "TRAINING_STAGING_DIR", tmp_path / "staging")
    monkeypatch.setattr(server, "TRAINING_SEARCH_STATE_PATH", tmp_path / "staging" / "search_job.json")
    monkeypatch.setattr(server, "_training_search_state", {})

    started = server._training_search_start("baget boxes")
    assert started["status"] in {"running", "done"}

    # The daemon thread finishes quickly with no cameras/model.
    deadline = time.time() + 5
    while time.time() < deadline and server._training_search_status().get("status") != "done":
        time.sleep(0.05)

    state = server._training_search_status()
    assert state["status"] == "done"
    assert state["rows"] == []
    # Persisted to disk so a reopened page restores the last results.
    assert (tmp_path / "staging" / "search_job.json").exists()


def test_training_search_stale_running_is_reported_done(tmp_path, monkeypatch):
    # Simulate a job left "running" on disk after a restart killed its worker:
    # no live worker (active False), so status must self-correct to done and
    # not make the page poll forever.
    monkeypatch.setattr(server, "TRAINING_STAGING_DIR", tmp_path / "staging")
    monkeypatch.setattr(server, "TRAINING_SEARCH_STATE_PATH", tmp_path / "staging" / "search_job.json")
    monkeypatch.setattr(server, "_training_search_state", {})
    monkeypatch.setattr(server, "_training_search_active", False)
    (tmp_path / "staging").mkdir(parents=True, exist_ok=True)
    (tmp_path / "staging" / "search_job.json").write_text(
        json.dumps({"status": "running", "query": "baget", "rows": [], "progress": {"done": 1, "total": 9}}),
        encoding="utf-8",
    )

    state = server._training_search_status()
    assert state["status"] == "done"
    assert state["diagnostics"]["interrupted"] is True


def test_training_dataset_backup_and_restore_round_trip(tmp_path, monkeypatch):
    root = tmp_path / "baget_box"
    _point_dataset(monkeypatch, root)
    monkeypatch.setattr(server, "TRAINING_DATASET_ROOT", root)
    # Backups now live at TRAINING_DATASET_ROOT.parent / "_backups" == tmp_path/_backups.
    (root / "images" / "train").mkdir(parents=True, exist_ok=True)
    (root / "labels" / "train").mkdir(parents=True, exist_ok=True)
    ok, buffer = cv2.imencode(".jpg", _image((30, 60, 90)))
    assert ok
    (root / "images" / "train" / "sample.jpg").write_bytes(buffer.tobytes())
    (root / "labels" / "train" / "sample.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")

    archive = server._training_backup_dataset("test", force=True)
    assert archive is not None and archive.exists()

    # Simulate a wiped working tree, then self-heal from the backup.
    import shutil

    shutil.rmtree(root / "images" / "train")
    assert not server._training_dataset_has_images()
    assert server._training_restore_from_backup_if_empty() is True
    assert (root / "images" / "train" / "sample.jpg").exists()
    assert (root / "labels" / "train" / "sample.txt").read_text(encoding="utf-8").strip() == "0 0.5 0.5 0.2 0.2"
