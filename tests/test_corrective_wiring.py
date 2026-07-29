from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import re

from runtime_wiring import (
    audit_snapshot_triggers,
    audit_warehouse_coordinates,
    business_detections,
    detection_accounting,
    runtime_health_fields,
)
from tracking.tracker import ObjectTracker


ROOT = Path(__file__).resolve().parents[1]
CONFIG_TEXT = (ROOT / "config" / "config.yaml").read_text(encoding="utf-8")


class PredictModel:
    def predict(self, **_kwargs):
        return []


def detection(class_name, inventory_name=None):
    return SimpleNamespace(
        class_name=class_name,
        object_type=class_name,
        inventory_name=inventory_name,
    )


def test_active_tracker_reports_custom_iou_and_does_not_apply_bytetrack_config():
    tracker = ObjectTracker(
        PredictModel(),
        tracker_config="config/warehouse_bytetrack.yaml",
    )

    assert tracker.tracking_engine == "custom_iou"
    assert tracker.tracker_config_applied is False
    assert tracker.tracker_config == "config/warehouse_bytetrack.yaml"


def test_unrecognized_proposals_are_excluded_from_every_business_consumer():
    raw_proposal = detection("object proposal")
    recognized_proposal = detection("object proposal", "Baget Box")
    named_detection = detection("cardboard box")
    observations = [raw_proposal, recognized_proposal, named_detection]

    eligible = business_detections(observations)

    assert eligible == [recognized_proposal, named_detection]
    assert raw_proposal not in eligible
    assert detection_accounting(observations) == {
        "proposal_count": 2,
        "verified_detection_count": 2,
    }

    source = re.sub(
        r"\s+",
        " ",
        (ROOT / "main.py").read_text(encoding="utf-8"),
    )
    assert source.index(
        "product_recognizer.annotate(cam.name, frame, detections)"
    ) < source.index("verified_detections = business_detections(detections)")
    assert "presence_tracker.update( cam.name, verified_detections," in source
    assert "_serialize_detection(det, frame) for det in verified_detections" in source
    assert "draw_counts(frame, verified_detections)" in source
    assert "for detection in verified_detections if getattr(" in source


def test_runtime_health_exposes_requested_corrective_wiring_fields():
    health = runtime_health_fields(
        tracking_engine="custom_iou",
        tracker_config_applied=False,
        active_model="yoloe-26s-seg.pt",
        frame_width=960,
        frame_height=540,
        inference_by_camera={
            "Camera 11": {"inference_fps": 2.1},
            "Camera 12": {"inference_fps": 1.9},
        },
        proposal_count_by_camera={"Camera 11": 3, "Camera 12": 2},
        verified_detection_count_by_camera={"Camera 11": 1, "Camera 12": 0},
    )

    assert health == {
        "tracking_engine": "custom_iou",
        "tracker_config_applied": False,
        "active_model": "yoloe-26s-seg.pt",
        "frame_width": 960,
        "frame_height": 540,
        "inference_fps": 4.0,
        "proposal_count": 5,
        "verified_detection_count": 1,
    }

    for source_path in (ROOT / "main.py", ROOT / "api" / "server.py"):
        source = source_path.read_text(encoding="utf-8")
        for field in health:
            assert f'"{field}"' in source


def test_configured_warehouse_coordinates_are_audited_without_mutation():
    engine_config = {
        "counting_line": {"x1": 100, "y1": 300, "x2": 900, "y2": 300},
        "zones": [
            {
                "name": "Receiving",
                "polygon": [[0, 0], [1280, 0], [1280, 360], [0, 360]],
            },
            {
                "name": "Storage",
                "polygon": [[0, 360], [1280, 360], [1280, 720], [0, 720]],
            },
        ],
    }
    assert "polygon: [[0, 0], [1280, 0], [1280, 360], [0, 360]]" in CONFIG_TEXT
    assert "polygon: [[0, 360], [1280, 360], [1280, 720], [0, 720]]" in CONFIG_TEXT
    original = deepcopy(engine_config)

    audit = audit_warehouse_coordinates(
        engine_config,
        {"Camera 11": {"width": 960, "height": 540}},
    )

    assert audit["status"] == "mismatch"
    assert audit["mismatch_count"] == 2
    camera = audit["cameras"]["Camera 11"]
    assert camera["counting_lines"][0]["compatible"] is True
    assert [zone["compatible"] for zone in camera["zones"]] == [False, False]
    assert engine_config == original


def test_snapshot_triggers_unreachable_from_active_prompts_are_reported():
    active_prompts = [
        "baget box",
        "baguette box",
        "stack of baget boxes",
        "stack of cardboard boxes",
        "cardboard box",
        "stack of sacks",
        "sack of flour",
        "large bag",
        "wrapped pallet",
        "wooden pallet",
        "warehouse package",
    ]
    assert "  - person" in CONFIG_TEXT
    assert "  - car" in CONFIG_TEXT
    for prompt in active_prompts:
        assert f"  - {prompt}" in CONFIG_TEXT

    audit = audit_snapshot_triggers(
        ["person", "car"],
        active_prompts,
    )

    assert audit["status"] == "mismatch"
    assert audit["unreachable_triggers"] == ["person", "car"]
    assert audit["reachable_triggers"] == []


def test_legacy_bytetrack_file_is_retained_and_explicitly_marked_unused():
    tracker_config = ROOT / "config" / "warehouse_bytetrack.yaml"
    content = tracker_config.read_text(encoding="utf-8")

    assert tracker_config.exists()
    assert "UNUSED BY ACTIVE RUNTIME" in content
    assert "tracker_config_applied=false" in content


def test_runtime_utility_is_mounted_and_packaged_for_both_process_modes():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    deploy = (ROOT.parent / "deploy_ai_vision_stack.ps1").read_text(encoding="utf-8")

    assert compose.count("./runtime_wiring.py:/app/runtime_wiring.py:ro") == 2
    assert '"runtime_wiring.py"' in deploy
