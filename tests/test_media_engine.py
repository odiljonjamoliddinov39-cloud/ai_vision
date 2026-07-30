from urllib.error import HTTPError

import pytest

from streaming.media_engine import FrameRateLimiter, MediaEngine, StreamDescriptor


def engine(enabled=True):
    return MediaEngine(
        enabled=enabled,
        rtsp_base_url="rtsp://mediamtx:8554",
        api_url="http://mediamtx:9997",
        hls_base_url="http://localhost:8888",
        webrtc_base_url="http://localhost:8889",
        ai_fps=5,
    )


def test_stream_descriptor_uses_stable_slot_path():
    descriptor = StreamDescriptor.from_camera(
        {"name": "Warehouse Camera", "source": "rtsp://nvr/live", "slot_number": "3"}
    )
    assert descriptor.path == "camera_3"
    assert descriptor.slot_number == 3


def test_network_camera_is_routed_through_media_engine():
    camera = {"name": "Camera", "source": "rtsp://nvr/live", "slot_number": 2}
    assert engine().consumer_source(camera) == "rtsp://mediamtx:8554/camera_2"
    assert engine(False).consumer_source(camera) == "rtsp://nvr/live"


def test_local_webcam_is_not_routed():
    camera = {"name": "USB", "source": 0, "slot_number": 1}
    assert engine().consumer_source(camera) == 0


def test_sync_paths_adds_path_when_patch_returns_not_found(monkeypatch):
    media_engine = engine()
    calls = []

    def fake_request(path, *, method="GET", payload=None):
        calls.append((path, method, payload))
        if method == "PATCH":
            raise HTTPError(path, 404, "not found", {}, None)
        return {}

    monkeypatch.setattr(media_engine, "_request_json", fake_request)
    result = media_engine.sync_paths(
        [{"name": "Dock", "source": "rtsp://user:secret@nvr/live", "slot_number": 4}]
    )

    assert result == {"enabled": True, "synced": 1, "errors": []}
    assert calls[0][0] == "/v3/config/paths/patch/camera_4"
    assert calls[1][0] == "/v3/config/paths/add/camera_4"
    assert calls[1][2]["source"] == "rtsp://user:secret@nvr/live"


def test_stream_health_exposes_urls_and_metrics(monkeypatch):
    media_engine = engine()
    monkeypatch.setattr(
        media_engine,
        "_request_json",
        lambda *_args, **_kwargs: {
            "ready": True,
            "sourceReadySince": "2026-07-25T10:00:00Z",
            "tracks": [{"type": "video", "codec": "H264", "width": 1920, "height": 1080}],
        },
    )
    status = media_engine.describe_camera(
        {"name": "Dock", "source": "rtsp://nvr/live", "slot_number": 1}
    )
    assert status["online"] is True
    assert status["codec"] == "H264"
    assert status["resolution"] == "1920x1080"
    assert status["hls_url"].endswith("/camera_1/index.m3u8")


def test_frame_rate_limiter_never_sleeps():
    limiter = FrameRateLimiter(5)
    assert limiter.ready("camera", now=10.0)
    assert not limiter.ready("camera", now=10.1)
    assert limiter.ready("camera", now=10.2)


def test_invalid_ai_fps_is_rejected(monkeypatch):
    monkeypatch.setenv("MEDIA_ENGINE_AI_FPS", "invalid")
    with pytest.raises(ValueError):
        MediaEngine.from_config({})
