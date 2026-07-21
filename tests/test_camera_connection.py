import os
import subprocess
import sys
from unittest.mock import patch

import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import api.server as server
from api.server import (
    CameraControllerCreate,
    _controller_camera_name,
    _controller_endpoint,
    _controller_stream_url,
    _private_controller_host_message,
    _live_feed_path,
    _live_feed_paths,
    _next_available_slot,
    _redact_sensitive_text,
    _test_camera_stream,
)
from cameras.camera import Camera, _mask_source
from database.camera_db import CameraDB


def test_camera_stream_closed_rtsp_port_fails_before_opencv():
    with patch("api.server.socket.create_connection", side_effect=TimeoutError("timed out")):
        with patch("api.server.subprocess.run") as run:
            result = _test_camera_stream(
                "rtsp://admin:secret@192.168.137.87:554/Streaming/Channels/101"
            )

    assert result["status"] == "failed"
    assert "Cannot reach RTSP endpoint 192.168.137.87:554" in result["message"]
    assert "secret" not in result["message"]
    assert result["details"]["endpoint_reachable"] is False
    run.assert_not_called()


def test_status_log_redaction_masks_rtsp_password():
    text = (
        "[Camera] Connected "
        "(source=rtsp://admin:secret@192.168.0.151:554/Streaming/Channels/101)"
    )

    redacted = _redact_sensitive_text(text)

    assert "secret" not in redacted
    assert "rtsp://admin:****@192.168.0.151:554/Streaming/Channels/101" in redacted


def test_camera_log_source_masks_rtsp_password():
    source = "rtsp://admin:secret@192.168.0.151:554/Streaming/Channels/101"

    masked = _mask_source(source)

    assert masked == "rtsp://admin:****@192.168.0.151:554/Streaming/Channels/101"


def test_next_available_camera_slot_uses_first_gap():
    cameras = [
        {"is_active": True, "slot_number": 1},
        {"is_active": True, "slot_number": 3},
        {"is_active": False, "slot_number": 2},
    ]

    assert _next_available_slot(cameras) == 2


def test_live_feed_path_can_target_slot():
    assert _live_feed_path(slot=3).name == "latest_slot_3.jpg"


def test_live_feed_paths_do_not_fall_back_to_global_latest_for_slots():
    paths = _live_feed_paths(slot=3)

    assert [path.name for path in paths] == ["latest_slot_3.jpg"]


def test_camera_stream_bare_ip_returns_actionable_message():
    result = _test_camera_stream("192.168.137.87")

    assert result["status"] == "failed"
    assert "starting with rtsp://" in result["message"]


def test_camera_stream_bad_port_returns_validation_message():
    result = _test_camera_stream("rtsp://admin:secret@ 192.168.0.151: 554/stream1")

    assert result["status"] == "failed"
    assert "Invalid camera stream port" in result["message"]
    assert "secret" not in result["message"]


def test_local_webcam_source_still_uses_opencv():
    completed = subprocess.CompletedProcess(
        args=["python"],
        returncode=0,
        stdout='{"ok": true, "opened": true, "frame_read": true}\n',
        stderr="",
    )
    with patch("api.server.socket.create_connection") as create_connection:
        with patch("api.server.subprocess.run", return_value=completed) as run:
            result = _test_camera_stream("0")

    assert result["status"] == "connected"
    create_connection.assert_not_called()
    run.assert_called_once()


def test_camera_stream_check_falls_back_when_ffmpeg_backend_cant_open_by_name(
    monkeypatch, tmp_path
):
    # Runs the real subprocess (not a mocked one) with a fake cv2 module on
    # its PYTHONPATH so the actual embedded fallback logic executes, not a
    # stand-in for it. The fake cv2.VideoCapture fails when called with an
    # explicit backend (CAP_FFMPEG, what's tried first for rtsp://) and
    # succeeds when called with no backend argument (the fallback).
    fake_cv2 = tmp_path / "cv2.py"
    fake_cv2.write_text(
        r"""
CAP_FFMPEG = 1
CAP_DSHOW = 2

class _Cap:
    def __init__(self, opens):
        self._opens = opens

    def isOpened(self):
        return self._opens

    def read(self):
        return True, "frame"

    def release(self):
        pass


def VideoCapture(*args):
    backend = args[1] if len(args) > 1 else None
    return _Cap(opens=backend is None)
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    with patch("api.server.socket.create_connection"):
        result = _test_camera_stream("rtsp://admin:secret@203.0.113.10:554/stream")

    assert result["status"] == "connected"


def test_controller_stream_url_builds_channel_rtsp_url_with_credentials():
    controller = CameraControllerCreate(
        name="NVR",
        host="192.168.1.10",
        username="admin",
        password="p@ss word",
        channel_count=2,
        stream_path_template="/Streaming/Channels/{channel}01",
    )

    assert _controller_stream_url(controller, 3) == (
        "rtsp://admin:p%40ss%20word@192.168.1.10:554/Streaming/Channels/301"
    )


def test_controller_endpoint_accepts_host_with_scheme():
    controller = CameraControllerCreate(host="http://192.168.1.10", protocol="http")

    assert _controller_endpoint(controller) == {
        "scheme": "http",
        "host": "192.168.1.10",
        "port": 80,
    }


def test_private_controller_host_message_flags_lan_ip():
    message = _private_controller_host_message("192.168.1.10")

    assert message is not None
    assert "not publicly reachable" in message
    assert "192.168.x.x" in message


def test_private_controller_host_message_allows_public_ip():
    assert _private_controller_host_message("8.8.8.8") is None


def test_private_controller_host_message_allows_dns_name():
    assert _private_controller_host_message("warehouse-nvr.example.com") is None


def test_controller_camera_name_template_can_use_slot_and_channel():
    controller = CameraControllerCreate(
        name="Main NVR",
        host="10.0.0.10",
        camera_name_template="{controller} slot {slot} channel {channel}",
    )

    assert _controller_camera_name(controller, channel=4, slot=9) == "Main NVR slot 9 channel 4"


def test_start_detection_syncs_config_from_active_camera_slots(monkeypatch, tmp_path):
    camera_db_path = tmp_path / "cameras.db"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "cameras": [{"name": "Demo Camera", "source": "dummy", "slot_number": 1}],
                "detection": {"model_path": "dummy"},
            }
        ),
        encoding="utf-8",
    )

    db = CameraDB(db_path=str(camera_db_path))
    first = db.add_camera(
        "NVR Camera 1",
        "rtsp://user:one@example.com/Streaming/Channels/101",
        "connected",
    )
    second = db.add_camera(
        "NVR Camera 2",
        "rtsp://user:two@example.com/Streaming/Channels/201",
        "connected",
    )
    db.assign_slot(first["id"], 1)
    db.assign_slot(second["id"], 2)

    class FakeProcess:
        pid = 12345

    monkeypatch.setattr(server, "CONFIG_PATH", config_path)
    monkeypatch.setattr(server, "CAMERA_DB_PATH", camera_db_path)
    monkeypatch.setattr(server, "DETECTION_STDOUT_PATH", tmp_path / "stdout.log")
    monkeypatch.setattr(server, "DETECTION_STDERR_PATH", tmp_path / "stderr.log")
    monkeypatch.setattr(server, "DETECTION_HEALTH_PATH", tmp_path / "health.json")
    monkeypatch.setattr(server, "DETECTION_PID_PATH", tmp_path / "detection.pid")
    monkeypatch.setattr(server, "_camera_db", None)
    monkeypatch.setattr(server, "_process", None)
    monkeypatch.setattr(server, "_detector_pid", lambda: None)
    monkeypatch.setattr(server, "_validate_active_cameras_for_start", lambda: None)
    monkeypatch.setattr(server.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())

    server.start_detection()

    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert [camera["name"] for camera in data["cameras"]] == ["NVR Camera 1", "NVR Camera 2"]
    assert [camera["slot_number"] for camera in data["cameras"]] == [1, 2]


def test_start_detection_clears_manual_stop_latch_even_when_validation_fails(monkeypatch):
    monkeypatch.setattr(server, "_detector_pid", lambda: None)
    monkeypatch.setattr(server, "_sync_config_active_cameras", lambda db: None)
    monkeypatch.setattr(server, "_get_camera_db", lambda: None)

    def _raise_validation_error():
        raise server.HTTPException(status_code=400, detail="Camera slot not reachable yet.")

    monkeypatch.setattr(server, "_validate_active_cameras_for_start", _raise_validation_error)
    server._manual_stop_requested = True

    try:
        server.start_detection()
        assert False, "expected start_detection to raise"
    except server.HTTPException:
        pass

    # A start attempt that fails validation must still unblock the watchdog,
    # otherwise a transient failure (e.g. a freshly reconnected RTSP stream
    # that hasn't sent its first keyframe yet) permanently disables
    # auto-recovery until someone restarts the container.
    assert server._manual_stop_requested is False


def test_validate_active_cameras_excludes_unreachable_cameras_instead_of_blocking_all(
    monkeypatch, tmp_path
):
    camera_db_path = tmp_path / "cameras.db"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump({"cameras": [], "detection": {"model_path": "dummy"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(server, "CAMERA_DB_PATH", camera_db_path)
    monkeypatch.setattr(server, "CONFIG_PATH", config_path)
    monkeypatch.setattr(server, "_camera_db", None)

    db = server._get_camera_db()
    good = db.add_camera("Good Camera", "dummy", "unknown")
    # A bare IP with no scheme fails _camera_stream_endpoint's validation
    # immediately, with no real network call - a deterministic stand-in for
    # a genuinely unreachable/misconfigured camera.
    bad = db.add_camera("Bad Camera", "192.168.137.87", "unknown")
    db.assign_slot(good["id"], 1)
    db.assign_slot(bad["id"], 2)

    # One unreachable camera used to make the whole call raise, blocking
    # every other (working) camera from starting too.
    server._validate_active_cameras_for_start()

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert [camera["name"] for camera in config["cameras"]] == ["Good Camera"]

    statuses = {camera["name"]: camera["status"] for camera in db.list_cameras(include_secret=False)}
    assert statuses["Good Camera"] == "connected"
    assert statuses["Bad Camera"] == "failed"

    # The bad camera stays active (so it keeps showing up and gets retried
    # on the next start) - it's only excluded from the detector's config.
    active_names = {
        camera["name"] for camera in db.list_active_cameras(include_secret=False)
    }
    assert active_names == {"Good Camera", "Bad Camera"}


def test_validate_active_cameras_still_raises_when_none_are_reachable(monkeypatch, tmp_path):
    camera_db_path = tmp_path / "cameras.db"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump({"cameras": [], "detection": {"model_path": "dummy"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(server, "CAMERA_DB_PATH", camera_db_path)
    monkeypatch.setattr(server, "CONFIG_PATH", config_path)
    monkeypatch.setattr(server, "_camera_db", None)

    db = server._get_camera_db()
    bad = db.add_camera("Bad Camera", "192.168.137.87", "unknown")
    db.assign_slot(bad["id"], 1)

    try:
        server._validate_active_cameras_for_start()
        assert False, "expected HTTPException"
    except server.HTTPException as exc:
        assert exc.status_code == 400
        assert "none of the active camera slots are reachable" in exc.detail


def test_camera_controller_registers_more_channels_than_free_slots_without_failing(
    monkeypatch, tmp_path
):
    from fastapi.testclient import TestClient

    camera_db_path = tmp_path / "cameras.db"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump({"cameras": [], "detection": {"model_path": "dummy"}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(server, "CAMERA_DB_PATH", camera_db_path)
    monkeypatch.setattr(server, "CONFIG_PATH", config_path)
    monkeypatch.setattr(server, "_camera_db", None)
    monkeypatch.setattr(server, "_detector_pid", lambda: None)
    # A small ceiling makes it easy to exceed deterministically instead of
    # registering 50+ channels just to prove the same point.
    monkeypatch.setattr(server, "MAX_CAMERA_SLOTS", 3)
    monkeypatch.setattr(server, "start_detection", lambda request=None: None)

    client = TestClient(server.app)
    # The default seeded "Camera 1" already occupies slot 1, leaving 2 free
    # slots (2 and 3) out of the lowered 3-slot ceiling.
    response = client.post(
        "/api/camera-controller",
        json={
            "name": "Big NVR",
            "host": "8.8.8.8",
            "protocol": "rtsp",
            "channel_count": 5,
            "make_active": True,
            "test_controller": False,
            "test_streams": False,
        },
    )

    # Registering more channels than there's slot budget for must not fail
    # the whole request - every channel still gets saved and tested.
    assert response.status_code == 200
    body = response.json()
    assert len(body["created"]) == 5

    results = body["results"]
    activated = [result for result in results if result["active"]]
    not_activated = [result for result in results if not result["active"]]

    assert len(activated) == 2
    assert {result["slot_number"] for result in activated} == {2, 3}
    assert len(not_activated) == 3
    for result in not_activated:
        assert result["slot_number"] is None
        assert result["status"] == "connected"
        assert "no free camera slot" in result["message"]

    # The channels that didn't get a slot still exist as registered cameras
    # - they're just inactive, ready to be activated later once a slot
    # frees up.
    cameras = body["cameras"]
    assert len(cameras) == 6  # default Camera 1 + 5 new channels
    assert sum(1 for camera in cameras if camera["is_active"]) == 3


def test_camera_controller_registration_succeeds_even_if_detection_fails_to_start(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    camera_db_path = tmp_path / "cameras.db"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump({"cameras": [], "detection": {"model_path": "dummy"}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(server, "CAMERA_DB_PATH", camera_db_path)
    monkeypatch.setattr(server, "CONFIG_PATH", config_path)
    monkeypatch.setattr(server, "_camera_db", None)
    monkeypatch.setattr(server, "_detector_pid", lambda: None)

    def _raise_validation_error(request=None):
        raise server.HTTPException(status_code=400, detail="Camera slot not reachable yet.")

    monkeypatch.setattr(server, "start_detection", _raise_validation_error)

    client = TestClient(server.app)
    response = client.post(
        "/api/camera-controller",
        json={
            "name": "Warehouse NVR",
            "host": "8.8.8.8",
            "protocol": "rtsp",
            "channel_count": 2,
            "make_active": True,
            "test_controller": False,
            "test_streams": False,
        },
    )

    # The cameras were genuinely created and activated; a transient failure
    # to (re)start detection right afterward shouldn't turn that into an
    # error response.
    assert response.status_code == 200
    body = response.json()
    assert len(body["created"]) == 2
    # 3, not 2: the default seeded "Camera 1" already occupies slot 1, and
    # the new channels now land on the next genuinely free slots (2 and 3)
    # instead of evicting it just because their requested start_slot (1)
    # happened to collide with an already-active camera.
    assert len(body["active_cameras"]) == 3


def test_update_config_can_enable_real_open_vocabulary_model(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "cameras": [{"name": "Demo Camera", "source": "dummy"}],
                "detection": {"model_path": "dummy", "confidence_threshold": 0.08},
                "snapshots": {},
                "logging": {},
                "tracking": {"enabled": True},
                "warehouse_counting": {"enabled": True},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(server, "CONFIG_PATH", config_path)

    updated = server.update_config(
        server.ConfigPatch(
            model_path="yolov8s-world.pt",
            confidence_threshold=0.12,
            image_size=640,
            class_prompts=["cardboard box", "stack of cardboard boxes"],
            class_agnostic_nms=True,
            tracking_enabled=False,
            warehouse_counting_enabled=False,
        )
    )

    assert updated["detection"]["model_path"] == "yolov8s-world.pt"
    assert updated["detection"]["confidence_threshold"] == 0.12
    assert updated["detection"]["image_size"] == 640
    assert updated["detection"]["class_prompts"] == [
        "cardboard box",
        "stack of cardboard boxes",
    ]
    assert updated["detection"]["class_agnostic_nms"] is True
    assert updated["tracking"]["enabled"] is False
    assert updated["warehouse_counting"]["enabled"] is False


def test_environment_camera_controller_seed_creates_active_slots(monkeypatch, tmp_path):
    camera_db_path = tmp_path / "cameras.db"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "cameras": [{"name": "Demo Camera", "source": "dummy", "slot_number": 1}],
                "detection": {"model_path": "dummy"},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(server, "CAMERA_DB_PATH", camera_db_path)
    monkeypatch.setattr(server, "CONFIG_PATH", config_path)
    monkeypatch.setattr(server, "_camera_db", None)
    monkeypatch.setenv("CAMERA_CONTROLLER_HOST", "203.0.113.10")
    monkeypatch.setenv("CAMERA_CONTROLLER_USERNAME", "admin")
    monkeypatch.setenv("CAMERA_CONTROLLER_PASSWORD", "secret")
    monkeypatch.setenv("CAMERA_CONTROLLER_CHANNEL_COUNT", "3")
    monkeypatch.setenv("CAMERA_CONTROLLER_STREAM_TEMPLATE", "/Streaming/Channels/{channel}02")

    db = server._get_camera_db()
    active = db.list_active_cameras(include_secret=False)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert [camera["slot_number"] for camera in active] == [1, 2, 3]
    assert [camera["slot_number"] for camera in config["cameras"]] == [1, 2, 3]
    assert config["cameras"][0]["source"].endswith("/Streaming/Channels/102")


def test_camera_falls_back_to_the_next_backend_when_the_first_fails_to_open():
    # A real, observed OpenCV quirk: CAP_FFMPEG sometimes fails to open a
    # perfectly valid RTSP source with "backend is generally available but
    # can't be used to capture by name", even though the same source opens
    # fine via the unspecified/"Auto" backend. The initial connect should
    # try every configured backend before giving up, the same way a
    # dropped-connection reconnect already does.
    class FakeCapture:
        def __init__(self, opens: bool):
            self._opens = opens

        def isOpened(self):
            return self._opens

        def set(self, *args, **kwargs):
            return True

        def read(self):
            return False, None

        def release(self):
            return None

    calls = []

    def fake_video_capture(source, backend=None):
        calls.append(backend)
        # CAP_FFMPEG (the first backend tried for rtsp://) fails; the
        # fallback ("Auto", no backend argument) succeeds.
        return FakeCapture(opens=backend is None)

    with patch("cameras.camera.cv2.VideoCapture", side_effect=fake_video_capture):
        camera = Camera(name="Gate Camera", source="rtsp://example.com/stream")
        try:
            assert len(calls) == 2
            assert camera.cap.isOpened()
        finally:
            camera.release()


def test_camera_raises_only_after_every_backend_fails():
    class FakeCapture:
        def isOpened(self):
            return False

        def release(self):
            return None

    with patch("cameras.camera.cv2.VideoCapture", return_value=FakeCapture()):
        try:
            Camera(name="Gate Camera", source="rtsp://example.com/stream")
            assert False, "expected ConnectionError"
        except ConnectionError as exc:
            assert "Gate Camera" in str(exc)
