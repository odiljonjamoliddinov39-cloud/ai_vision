from streams.manager import StreamManager, StreamSessionConfig, _ffmpeg_command
from streams.mediamtx import MediaMTXClient


class FakeMediaMTX(MediaMTXClient):
    def __init__(self):
        super().__init__(
            enabled=True,
            required=True,
            api_url="http://mediamtx:9997",
            rtsp_url="rtsp://mediamtx:8554",
            public_webrtc_url="https://video.example.test",
            public_hls_url="https://hls.example.test",
        )
        self.sources = []

    def ensure_source(self, channel_id, upstream_url):
        self.sources.append((str(channel_id), upstream_url))
        return self.route(str(channel_id))

    def health(self):
        return {"enabled": True, "reachable": True}


def test_mediamtx_route_exposes_ai_webrtc_and_hls_renditions():
    client = FakeMediaMTX()
    route = client.route("camera 12")

    assert route.source_rtsp_url == "rtsp://mediamtx:8554/camera-camera-12-source"
    assert route.ai_rtsp_url == "rtsp://mediamtx:8554/camera-camera-12-ai"
    assert route.dashboard_rtsp_url == "rtsp://mediamtx:8554/camera-camera-12-dashboard"
    assert route.webrtc_url == "https://video.example.test/camera-camera-12-dashboard/whep"
    assert route.hls_url == "https://hls.example.test/camera-camera-12-dashboard/index.m3u8"


def test_stream_manager_routes_upstream_rtsp_through_mediamtx(monkeypatch, tmp_path):
    client = FakeMediaMTX()
    captured = []

    def fake_start(self):
        captured.append(self.config)

    monkeypatch.setattr("streams.manager._ManagedStreamSession.start", fake_start)
    manager = StreamManager(snapshot_dir=tmp_path, media_client=client)
    status = manager.start(
        StreamSessionConfig(
            channel_id="12",
            name="Warehouse 12",
            source="rtsp://user:secret@camera.example.test/live",
            slot_number=12,
            snapshot_dir=tmp_path,
        )
    )

    assert client.sources == [
        ("12", "rtsp://user:secret@camera.example.test/live")
    ]
    assert captured[0].source == "rtsp://mediamtx:8554/camera-12-source"
    assert captured[0].origin_source.startswith("rtsp://user:secret@")
    assert status["transport"] == "mediamtx"


def test_enterprise_ffmpeg_decodes_once_and_publishes_specialized_feeds():
    client = FakeMediaMTX()
    route = client.route("7")
    command = _ffmpeg_command(route.source_rtsp_url, media_route=route)

    assert command.count("-i") == 1
    assert route.ai_rtsp_url in command
    assert route.dashboard_rtsp_url in command
    assert "split=3" in command[command.index("-filter_complex") + 1]
    assert "pipe:1" == command[-1]


def test_direct_transport_remains_available_for_rollback(tmp_path):
    client = MediaMTXClient(enabled=False, required=False)
    manager = StreamManager(snapshot_dir=tmp_path, media_client=client)
    route = manager.route_info("4")

    assert route["ai_path"] == "camera-4-ai"
    assert manager.status()["media_server"]["enabled"] is False
