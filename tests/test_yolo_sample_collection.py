import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "collect_yolo_samples.py"

spec = importlib.util.spec_from_file_location("collect_yolo_samples", SCRIPT_PATH)
collect_yolo_samples = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = collect_yolo_samples
spec.loader.exec_module(collect_yolo_samples)


def test_detection_bbox_converts_to_yolo_label():
    label = collect_yolo_samples.yolo_box(
        {"bbox": {"x1": 10, "y1": 20, "x2": 50, "y2": 80}},
        width=100,
        height=100,
    )

    assert label == "0 0.300000 0.500000 0.400000 0.600000"


def test_collector_saves_matching_detection_sample(tmp_path, monkeypatch):
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    frame = snapshot_dir / "latest_stream_slot_5.jpg"
    frame.write_bytes(b"image bytes")
    health = {
        "cameras": [{"name": "NVR Camera 5", "slot_number": 5}],
        "last_detections_by_camera": {
            "NVR Camera 5": [
                {
                    "class_name": "cardboard box",
                    "confidence": 0.8,
                    "bbox": {"x1": 10, "y1": 20, "x2": 50, "y2": 80},
                }
            ]
        },
    }
    health_path = tmp_path / "detection_health.json"
    health_path.write_text(json.dumps(health), encoding="utf-8")
    dataset_dir = tmp_path / "dataset"

    monkeypatch.setattr(collect_yolo_samples, "image_size", lambda _path: (100, 100))

    args = type(
        "Args",
        (),
        {
            "health": str(health_path),
            "snapshot_dir": str(snapshot_dir),
            "dataset": str(dataset_dir),
            "split": "train",
            "camera": None,
            "match": "baget box,cardboard box",
            "min_confidence": 0.05,
            "dry_run": False,
        },
    )()

    saved = collect_yolo_samples.collect_samples(args)

    assert len(saved) == 1
    labels = list((dataset_dir / "labels" / "train").glob("*.txt"))
    assert labels[0].read_text(encoding="utf-8") == "0 0.300000 0.500000 0.400000 0.600000\n"
