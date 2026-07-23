import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.camera_db import CameraDB, mask_stream_url


def test_mask_stream_url_hides_password():
    masked = mask_stream_url("rtsp://username:password@192.168.1.64:554/stream1")

    assert masked == "rtsp://username:****@192.168.1.64:554/stream1"
    assert "password" not in masked


def test_mask_stream_url_handles_bad_port_without_exposing_password():
    masked = mask_stream_url("rtsp://admin:secret@ 192.168.0.151: 554/stream1")

    assert masked == "rtsp://admin:****@ 192.168.0.151: 554/stream1"
    assert "secret" not in masked


def test_camera_db_saves_masked_response_and_active_camera(tmp_path):
    db = CameraDB(db_path=str(tmp_path / "cameras.db"))

    first = db.add_camera("Warehouse Camera 1", "rtsp://user:secret@192.168.1.64:554/live")
    second = db.add_camera("Entrance Camera", "http://192.168.1.64:8080/video")
    active = db.set_active(second["id"])

    cameras = db.list_cameras()

    assert active["stream_url"] == "http://192.168.1.64:8080/video"
    assert active["slot_number"] == 1
    assert cameras[0]["name"] == "Entrance Camera"
    assert cameras[0]["is_active"] is True
    assert cameras[0]["slot_number"] == 1
    assert "stream_url" not in cameras[0]
    assert cameras[1]["masked_stream_url"] == "rtsp://user:****@192.168.1.64:554/live"


def test_camera_db_assigns_multiple_camera_slots(tmp_path):
    db = CameraDB(db_path=str(tmp_path / "cameras.db"))

    first = db.add_camera("Warehouse Camera 1", "rtsp://user:one@192.168.1.64:554/live")
    second = db.add_camera("Entrance Camera", "http://192.168.1.65:8080/video")
    third = db.add_camera("Dock Camera", "rtsp://user:two@192.168.1.66:554/live")

    db.assign_slot(first["id"], 1)
    db.assign_slot(second["id"], 2)
    db.assign_slot(third["id"], 2)

    active = db.list_active_cameras(include_secret=True)

    assert [camera["name"] for camera in active] == ["Warehouse Camera 1", "Dock Camera"]
    assert [camera["slot_number"] for camera in active] == [1, 2]
    assert all(camera["is_active"] for camera in active)


def test_camera_db_deletes_camera(tmp_path):
    db = CameraDB(db_path=str(tmp_path / "cameras.db"))
    camera = db.add_camera("Test Camera", "dummy", status="connected")

    assert db.delete_camera(camera["id"]) is True
    assert db.get_camera(camera["id"]) is None
    assert db.delete_camera(camera["id"]) is False


def test_upsert_camera_by_stream_url_reuses_existing_slot(tmp_path):
    db = CameraDB(db_path=str(tmp_path / "cameras.db"))
    first = db.add_camera("NVR Main Camera 1", "rtsp://example.test/Streaming/Channels/101", "connected")
    active = db.assign_slot(first["id"], 7)

    updated = db.upsert_camera_by_stream_url(
        "NVR Main Ch 1",
        "rtsp://example.test/Streaming/Channels/101",
        "stream_managed",
    )

    assert updated["id"] == first["id"]
    assert db.get_camera(first["id"])["name"] == "NVR Main Ch 1"
    assert db.list_active_cameras()[0]["slot_number"] == active["slot_number"]
    assert len(db.list_cameras()) == 1
