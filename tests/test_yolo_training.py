import importlib.util
from pathlib import Path
import sys

import yaml

from database.catalog_db import CatalogDB


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "train_yolo.py"
EXPORT_SCRIPT_PATH = ROOT / "scripts" / "export_yolo_dataset_from_results.py"

spec = importlib.util.spec_from_file_location("train_yolo", SCRIPT_PATH)
train_yolo = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = train_yolo
spec.loader.exec_module(train_yolo)

export_spec = importlib.util.spec_from_file_location("export_yolo_dataset_from_results", EXPORT_SCRIPT_PATH)
export_yolo_dataset = importlib.util.module_from_spec(export_spec)
assert export_spec.loader is not None
sys.modules[export_spec.name] = export_yolo_dataset
export_spec.loader.exec_module(export_yolo_dataset)


def test_baget_box_training_template_is_present():
    dataset_yaml = ROOT / "datasets" / "baget_box" / "data.yaml"
    docs = ROOT / "docs" / "yolo_training.md"

    data = yaml.safe_load(dataset_yaml.read_text(encoding="utf-8"))

    assert data["train"] == "images/train"
    assert data["val"] == "images/val"
    assert data["names"] == {0: "baget box"}
    assert "python scripts/train_yolo.py --validate-only" in docs.read_text(encoding="utf-8")


def test_training_helper_validates_yolo_dataset_layout(tmp_path):
    for split in ("train", "val"):
        image_dir = tmp_path / "images" / split
        label_dir = tmp_path / "labels" / split
        image_dir.mkdir(parents=True)
        label_dir.mkdir(parents=True)
        (image_dir / f"{split}_001.jpg").write_bytes(b"not decoded by validator")
        (label_dir / f"{split}_001.txt").write_text("0 0.5 0.5 0.4 0.3\n", encoding="utf-8")

    dataset_yaml = tmp_path / "data.yaml"
    dataset_yaml.write_text(
        yaml.safe_dump(
            {
                "path": str(tmp_path),
                "train": "images/train",
                "val": "images/val",
                "names": {0: "baget box"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    reports = train_yolo.validate_dataset(dataset_yaml)

    assert [(report.name, report.image_count, report.label_count) for report in reports] == [
        ("train", 1, 1),
        ("val", 1, 1),
    ]


def test_result_visual_export_builds_yolo_dataset_from_catalog_history(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db_path = tmp_path / "catalog.db"
    db = CatalogDB(str(db_path))
    item = db.create_item("warehouse-a", "Baget Box")
    run_id = db.start_run("warehouse-a", interval_hours=12, camera_count=1)
    snapshot_dir = tmp_path / "snapshots"
    frame_dir = snapshot_dir / "catalog-recognition" / "warehouse-a" / run_id
    frame_dir.mkdir(parents=True)
    frame = frame_dir / "camera_frame.jpg"
    frame.write_bytes(b"image bytes")
    frame_url = f"/snapshots/catalog-recognition/warehouse-a/{run_id}/camera_frame.jpg"
    db.add_result(
        run_id,
        item["id"],
        "Baget Box",
        quantity=1,
        confidence=0.93,
        camera_counts=[
            {
                "camera_name": "NVR Main Camera 2",
                "quantity": 1,
                "frame_url": frame_url,
                "bbox": {"x1": 10, "y1": 20, "x2": 50, "y2": 80},
            }
        ],
    )
    db.complete_run(run_id)
    dataset_dir = tmp_path / "dataset"
    data_yaml = dataset_dir / "data.yaml"
    data_yaml.parent.mkdir()
    data_yaml.write_text(
        yaml.safe_dump(
            {
                "path": str(dataset_dir),
                "train": "images/train",
                "val": "images/val",
                "names": {0: "Baget Box"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(export_yolo_dataset, "image_size", lambda _path: (100, 100))
    args = type(
        "Args",
        (),
        {
            "catalog_db": str(db_path),
            "scope_id": "warehouse-a",
            "snapshot_dir": str(snapshot_dir),
            "data_yaml": str(data_yaml),
            "dataset": None,
            "limit": 50,
            "split": "train",
            "val_ratio": 0.2,
            "min_confidence": 0.2,
            "item": None,
            "include_new_classes": False,
            "dry_run": False,
        },
    )()

    report = export_yolo_dataset.build_dataset(args)

    labels = list((dataset_dir / "labels" / "train").glob("*.txt"))
    images = list((dataset_dir / "images" / "train").glob("*.jpg"))
    assert (report.image_count, report.label_count, report.skipped_count) == (1, 1, 0)
    assert len(images) == 1
    assert labels[0].read_text(encoding="utf-8") == "0 0.300000 0.500000 0.400000 0.600000\n"
