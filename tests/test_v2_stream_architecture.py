import time

import numpy as np

from streams.frame_source import StreamFrameCamera
from streams.manager import StreamManager, StreamSessionConfig


def test_stream_manager_publishes_live_frame_without_ai(tmp_path):
    manager = StreamManager(snapshot_dir=tmp_path)
    status = manager.start(
        StreamSessionConfig(
            channel_id="1",
            name="Demo",
            source="dummy",
            slot_number=1,
            snapshot_dir=tmp_path,
        )
    )

    assert status["status"] == "starting"
    path = tmp_path / "latest_stream_slot_1.jpg"
    deadline = time.time() + 3
    while time.time() < deadline and not path.exists():
        time.sleep(0.05)

    try:
        assert path.exists()
        data = path.read_bytes()
        assert data.startswith(b"\xff\xd8")
        assert data.endswith(b"\xff\xd9")
        assert manager.status()["streams"][0]["status"] == "online"
    finally:
        manager.stop_all()


def test_analytics_frame_source_reads_stream_manager_frame(tmp_path):
    manager = StreamManager(snapshot_dir=tmp_path)
    manager.start(
        StreamSessionConfig(
            channel_id="1",
            name="Demo",
            source="dummy",
            slot_number=1,
            snapshot_dir=tmp_path,
        )
    )
    camera = StreamFrameCamera("Demo", slot_number=1, source="rtsp://example.invalid/stream", snapshot_dir=tmp_path)

    deadline = time.time() + 3
    frame = None
    while time.time() < deadline and frame is None:
        frame = camera.read()
        time.sleep(0.05)

    try:
        assert isinstance(frame, np.ndarray)
        assert frame.shape[0] > 0
        assert frame.shape[1] > 0
    finally:
        manager.stop_all()


def test_start_validation_does_not_open_rtsp(monkeypatch, tmp_path):
    from api import server
    from database.camera_db import CameraDB

    db = CameraDB(str(tmp_path / "cameras.db"))
    saved = db.add_camera("NVR Channel 1", "rtsp://user:secret@example.com/Streaming/Channels/101", "connected")
    db.assign_slot(saved["id"], 1)

    monkeypatch.setattr(server, "_get_camera_db", lambda: db)
    monkeypatch.setattr(server, "_set_config_active_cameras", lambda cameras: {"cameras": cameras})

    def fail_if_called(_stream_url, timeout_seconds=10):
        raise AssertionError("analytics validation must not open RTSP directly")

    monkeypatch.setattr(server, "_test_camera_stream", fail_if_called)

    server._validate_active_cameras_for_start()
