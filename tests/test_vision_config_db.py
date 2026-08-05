from database.vision_config_db import VisionConfigDB


def test_blocks_and_camera_rules_survive_reopen(tmp_path):
    path = str(tmp_path / "vision.db")
    db = VisionConfigDB(path)
    block = db.create_block("Packing", "Baget packing line")
    zones = {
        "entry_line": [[0, 10], [100, 10]], "exit_line": [[0, 90], [100, 90]],
        "counting_zone": [[0, 10], [100, 10], [100, 90], [0, 90]],
        "ignore_zone": [[0, 0], [5, 0], [5, 5], [0, 5]],
    }
    db.save_camera_rules("camera-1", block_id=block["id"], confidence=.4,
                         minimum_track_age=5, direction=1, zones=zones)
    loaded = VisionConfigDB(path).get_camera_rules("camera-1")
    assert loaded["settings"]["block_id"] == block["id"]
    assert loaded["zones"]["counting_zone"] == zones["counting_zone"]


def test_camera_block_assignment_preserves_rules_and_can_be_cleared(tmp_path):
    path = str(tmp_path / "vision.db")
    db = VisionConfigDB(path)
    block = db.create_block("Warehouse A", "Primary warehouse")
    db.save_camera_rules("7", block_id=None, confidence=.61,
                         minimum_track_age=8, direction=-1, zones={})

    assigned = db.assign_camera_block(7, block["id"])
    loaded = db.get_camera_rules("7")
    assert assigned["block_name"] == "Warehouse A"
    assert loaded["settings"]["confidence"] == .61
    assert loaded["settings"]["minimum_track_age"] == 8

    cleared = db.assign_camera_block(7, None)
    assert cleared["block_id"] is None
