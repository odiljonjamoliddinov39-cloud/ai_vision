import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.camera_db import CameraDB, mask_stream_url


def test_mask_stream_url_hides_password():
    masked = mask_stream_url("rtsp://username:password@192.168.1.64:554/stream1")

    assert masked == "rtsp://username:****@192.168.1.64:554/stream1"
    assert "password" not in masked


def test_camera_db_saves_masked_response_and_active_camera(tmp_path):
    db = CameraDB(db_path=str(tmp_path / "cameras.db"))

    first = db.add_camera("Warehouse Camera 1", "rtsp://user:secret@192.168.1.64:554/live")
    second = db.add_camera("Entrance Camera", "http://192.168.1.64:8080/video")
    active = db.set_active(second["id"])

    cameras = db.list_cameras()

    assert active["stream_url"] == "http://192.168.1.64:8080/video"
    assert cameras[0]["name"] == "Entrance Camera"
    assert cameras[0]["is_active"] is True
    assert "stream_url" not in cameras[0]
    assert cameras[1]["masked_stream_url"] == "rtsp://user:****@192.168.1.64:554/live"
