import time
from pathlib import Path

import cv2
import numpy as np

from streams.frame_source import StreamFrameCamera
from streams.manager import StreamManager, StreamSessionConfig, _ManagedStreamSession, _ffmpeg_command
from streams.shared_buffer import SharedFrameReader, SharedFrameWriter, buffer_path


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
    path = buffer_path(tmp_path, 1)
    deadline = time.time() + 3
    while time.time() < deadline and not path.exists():
        time.sleep(0.05)

    try:
        assert path.exists()
        reader = SharedFrameReader(tmp_path, 1)
        snapshot = reader.read()
        assert snapshot is not None
        _, data = snapshot
        assert data.startswith(b"\xff\xd8")
        assert data.endswith(b"\xff\xd9")
        assert manager.status()["streams"][0]["status"] == "online"
        reader.close()
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


def test_stream_manager_keeps_latest_frame_in_memory(tmp_path):
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

    deadline = time.time() + 3
    data = None
    while time.time() < deadline and data is None:
        data = manager.latest_frame_bytes(channel_id="1")
        time.sleep(0.05)

    try:
        assert data is not None
        assert data.startswith(b"\xff\xd8")
        assert data.endswith(b"\xff\xd9")
    finally:
        manager.stop_all()


def test_stream_manager_reuses_one_upstream_for_duplicate_camera_source(monkeypatch, tmp_path):
    ok, encoded = cv2.imencode(".jpg", np.zeros((4, 4, 3), dtype=np.uint8))
    assert ok
    jpeg = encoded.tobytes()
    starts = []

    def fake_run(self):
        starts.append(self.config.channel_id)
        self.status_data.status = "online"
        self._publish_jpeg(jpeg)
        while not self._stop.wait(0.05):
            pass

    monkeypatch.setattr(_ManagedStreamSession, "_run", fake_run)
    manager = StreamManager(snapshot_dir=tmp_path)
    try:
        first = manager.start(
            StreamSessionConfig(
                channel_id="1",
                name="Primary",
                source="rtsp://example.test/stream",
                slot_number=1,
                snapshot_dir=tmp_path,
            )
        )
        deadline = time.time() + 2
        while time.time() < deadline and manager.latest_frame_bytes(channel_id="1") is None:
            time.sleep(0.05)
        second = manager.start(
            StreamSessionConfig(
                channel_id="2",
                name="Alias",
                source="rtsp://example.test/stream",
                slot_number=2,
                snapshot_dir=tmp_path,
            )
        )

        assert first["channel_id"] == "1"
        assert second["channel_id"] == "2"
        status = manager.status()
        assert len(status["streams"]) == 2
        assert status["upstream_count"] == 1
        assert starts == ["1"]
        assert manager.latest_frame_bytes(channel_id="2") == manager.latest_frame_bytes(channel_id="1")
        assert buffer_path(tmp_path, 2).exists()
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


def test_live_frame_prefers_stream_manager_memory(monkeypatch, tmp_path):
    import asyncio
    from api import server

    data = b"\xff\xd8from-memory\xff\xd9"

    class FakeStreamManager:
        def latest_frame_bytes(self, channel_id=None, slot_number=None, name=None):
            assert slot_number == 7
            return data

    monkeypatch.setattr(server, "_get_stream_manager", lambda: FakeStreamManager())
    monkeypatch.setattr(server, "SNAPSHOT_DIR", tmp_path)

    response = asyncio.run(server.live_frame(slot=7))

    assert response.body == data
    assert response.headers["x-ai-frame-source"] == "stream-manager"


def test_stream_manager_ffmpeg_outputs_scaled_preview_jpegs():
    command = _ffmpeg_command("rtsp://example.test/Streaming/Channels/101")

    assert "-vf" in command
    assert command[command.index("-vf") + 1] == "fps=15,scale=960:-2"
    assert "-q:v" in command
    assert command[command.index("-q:v") + 1] == "8"
    assert "-probesize" in command
    assert command[command.index("-fflags") + 1] == "+nobuffer+discardcorrupt"
    assert command[command.index("-flags") + 1] == "low_delay"
    # Decode every frame for smooth motion, not just keyframes.
    assert "-skip_frame" not in command


def test_analytics_frame_source_skips_unchanged_stream_frame(tmp_path):
    ok, jpg = cv2.imencode(".jpg", np.zeros((80, 120, 3), dtype="uint8"))
    assert ok
    writer = SharedFrameWriter(tmp_path, 1)
    writer.publish(jpg.tobytes())
    camera = StreamFrameCamera("Demo", slot_number=1, source="rtsp://example.invalid/stream", snapshot_dir=tmp_path)

    try:
        first = camera.read()
        assert isinstance(first, np.ndarray)
        assert camera.read() is None
    finally:
        camera.release()
        writer.close(remove=True)


def test_multiple_consumers_share_one_worker_and_decoder(monkeypatch, tmp_path):
    ok, encoded = cv2.imencode(".jpg", np.zeros((20, 30, 3), dtype=np.uint8))
    assert ok
    jpeg = encoded.tobytes()
    decoder_starts = []

    def fake_run(self):
        decoder_starts.append(self.config.channel_id)
        while not self._stop.is_set():
            self._publish_jpeg(jpeg)
            self._stop.wait(0.02)

    monkeypatch.setattr(_ManagedStreamSession, "_run", fake_run)
    manager = StreamManager(snapshot_dir=tmp_path)
    config = StreamSessionConfig(
        channel_id="1",
        name="Primary",
        source="rtsp://example.test/stream",
        slot_number=1,
        snapshot_dir=tmp_path,
    )
    try:
        manager.start(config)
        manager.start(config)
        camera = StreamFrameCamera(
            "Primary", slot_number=1, source=config.source, snapshot_dir=tmp_path
        )
        deadline = time.time() + 2
        frame = None
        while time.time() < deadline and frame is None:
            assert manager.latest_frame_bytes(channel_id="1") in (None, jpeg)
            frame = camera.read()
        assert isinstance(frame, np.ndarray)
        assert decoder_starts == ["1"]
        assert manager.status()["upstream_count"] == 1
        camera.release()
    finally:
        manager.stop_all()


def test_shared_buffer_rejects_partial_frame(tmp_path):
    writer = SharedFrameWriter(tmp_path, 3)
    reader = SharedFrameReader(tmp_path, 3)
    try:
        writer._write_header(1, 100, 0)
        assert reader.read() is None
    finally:
        reader.close()
        writer.close(remove=True)


def test_shared_buffer_reader_follows_replaced_worker(tmp_path):
    first = SharedFrameWriter(tmp_path, 4)
    reader = SharedFrameReader(tmp_path, 4)
    first.publish(b"\xff\xd8first\xff\xd9")
    assert reader.read() is not None
    first.close()

    second = SharedFrameWriter(tmp_path, 4)
    try:
        sequence = second.publish(b"\xff\xd8second\xff\xd9")
        assert reader.read() == (sequence, b"\xff\xd8second\xff\xd9")
    finally:
        reader.close()
        second.close(remove=True)


def test_detector_stream_first_reads_every_camera_without_four_camera_cap():
    source = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")

    assert "if stream_first and cam.name not in inference_camera_names:" not in source
    assert "LatestFrameInferenceScheduler(processors)" in source


def test_detector_direct_camera_mode_requires_explicit_dev_override():
    source = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")

    assert "AI_VISION_ALLOW_DIRECT_CAMERA" in source
    assert "or not direct_camera_override" in source
