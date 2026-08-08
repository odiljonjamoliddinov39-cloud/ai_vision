from inventory import InventoryCandidate, VisibleInventoryCounter
from database.vision_db import VisionDB


def candidate(index, box, name="Baget Box", confidence=0.9):
    return InventoryCandidate(index, box, "baget_box", confidence, name, confidence, "custom_detector")


def test_visible_inventory_count_does_not_require_tracks_or_movement():
    counter = VisibleInventoryCounter(target_product="Baget Box", minimum_area_px=20)
    result = counter.evaluate([
        candidate(0, (0, 0, 20, 20)),
        candidate(1, (30, 0, 50, 20)),
        candidate(2, (60, 0, 80, 20), name="Pallet"),
    ])
    assert result.raw_detection_count == 3
    assert result.final_inventory_count == 2
    assert len(result.rejected) == 1


def test_visible_inventory_suppresses_overlapping_duplicates():
    counter = VisibleInventoryCounter(target_product="baget_box", duplicate_iou=0.5)
    result = counter.evaluate([
        candidate(0, (0, 0, 100, 100), confidence=0.95),
        candidate(1, (5, 5, 95, 95), confidence=0.8),
    ])
    assert result.final_inventory_count == 1
    assert result.rejected[0].reason == "duplicate_overlap"


def test_visible_inventory_applies_roi_and_minimum_size():
    counter = VisibleInventoryCounter(
        target_product="Baget Box", minimum_area_px=100,
        inventory_roi=((0, 0), (50, 0), (50, 50), (0, 50)),
    )
    result = counter.evaluate([
        candidate(0, (10, 10, 30, 30)),
        candidate(1, (60, 60, 90, 90)),
        candidate(2, (1, 1, 5, 5)),
    ])
    assert result.final_inventory_count == 1
    assert {item.reason for item in result.rejected} == {"outside_inventory_roi", "object_too_small"}


def test_benchmark_persists_ground_truth_and_count_accuracy(tmp_path):
    database = VisionDB(str(tmp_path / "vision.db"))
    result_id = database.record_inventory_result({
        "camera_id": "camera-3", "block_id": "warehouse-a",
        "frame_uuid": "frame-1", "target_product": "Baget Box",
        "requested_model": "baget_box_best.pt", "loaded_model": "baget_box_best.pt",
        "detector_mode": "baget_box_custom", "fallback_used": False,
        "raw_detection_count": 31, "accepted_detection_count": 27,
        "rejected_detection_count": 4, "final_inventory_count": 27,
        "detections": [{"box": [1, 2, 3, 4], "accepted": True}],
        "evidence_path": "snapshots/benchmark/frame-1.jpg",
    })
    database.record_benchmark(result_id, 27, "manually verified")
    benchmark = database.list_benchmarks()[0]
    assert benchmark["predicted_count"] == 27
    assert benchmark["ground_truth_count"] == 27
    assert benchmark["accuracy"] == 1.0
