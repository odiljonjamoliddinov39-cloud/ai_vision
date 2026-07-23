import importlib.util
from pathlib import Path
import sys

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "train_yolo.py"

spec = importlib.util.spec_from_file_location("train_yolo", SCRIPT_PATH)
train_yolo = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = train_yolo
spec.loader.exec_module(train_yolo)


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
