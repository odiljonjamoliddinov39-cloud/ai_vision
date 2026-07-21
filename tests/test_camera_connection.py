import io
import os
import subprocess
import sys
import threading
import time
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


def test_camera_stream_check_uses_a_real_ffmpeg_subprocess_for_rtsp(monkeypatch, tmp_path):
    # Runs the real subprocess (not a mocked one), with a fake `ffmpeg`
    # executable on PATH so the actual embedded validation logic executes
    # end to end, not a stand-in for it. Mirrors what Camera._open_ffmpeg()
    # does in cameras/camera.py: OpenCV's bundled FFMPEG backend can refuse
    # a perfectly valid RTSP source with no other OpenCV backend to fall
    # back to, so this pre-flight check shells out to ffmpeg directly too -
    # it has to agree with what the real detector can actually achieve.
    fake_ffmpeg = tmp_path / "ffmpeg"
    fake_ffmpeg.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "sys.stdout.buffer.write(b'\\xff\\xd8fake-jpeg-data\\xff\\xd9')\n"
        "sys.stdout.buffer.flush()\n",
        encoding="utf-8",
    )
    fake_ffmpeg.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ.get('PATH', '')}")

    with patch("api.server.socket.create_connection"):
        result = _test_camera_stream("rtsp://admin:secret@203.0.113.10:554/stream")

    assert result["status"] == "connected"


def test_camera_stream_check_reports_failure_when_ffmpeg_is_not_installed(monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent-empty-bin-dir")
    with patch("api.server.socket.create_connection"):
        result = _test_camera_stream("rtsp://admin:secret@203.0.113.10:554/stream")

    assert result["status"] == "failed"


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
    # The seed path now actually tests connectivity/streams before
    # activating a channel (it used to activate every channel
    # unconditionally, which is exactly what let stale env-var credentials
    # silently occupy real slots forever). Fake both checks as passing so
    # this test exercises the seeding logic without a real network call.
    monkeypatch.setattr(server, "_check_camera_endpoint", lambda endpoint, timeout_seconds=2.0: None)
    monkeypatch.setattr(
        server,
        "_test_camera_stream",
        lambda stream_url, timeout_seconds=10: {"status": "connected", "message": "ok"},
    )

    db = server._get_camera_db()
    active = db.list_active_cameras(include_secret=False)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert [camera["slot_number"] for camera in active] == [1, 2, 3]
    assert [camera["slot_number"] for camera in config["cameras"]] == [1, 2, 3]
    assert config["cameras"][0]["source"].endswith("/Streaming/Channels/102")


def test_environment_camera_controller_seed_does_not_activate_unreachable_channels(
    monkeypatch, tmp_path
):
    # This is the actual bug: the seed path used to build a
    # CameraControllerCreate with test_controller/test_streams fields that
    # were never consulted by its own hand-rolled activation loop, so a
    # stale or wrong CAMERA_CONTROLLER_* credential baked into the droplet's
    # environment would silently occupy real slots forever, with nothing
    # ever having actually verified it worked.
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
    monkeypatch.setenv("CAMERA_CONTROLLER_CHANNEL_COUNT", "3")
    monkeypatch.setattr(
        server,
        "_check_camera_endpoint",
        lambda endpoint, timeout_seconds=2.0: "connection refused",
    )

    db = server._get_camera_db()

    assert db.list_active_cameras(include_secret=False) == []
    # The channels are still saved (visible, inspectable) - they're just
    # never activated, since nothing ever confirmed they actually work.
    assert len(db.list_cameras(include_secret=False)) == 3


def test_camera_falls_back_to_the_next_backend_when_the_first_fails_to_open():
    # This backend-cycling path (_open_with_fallback / _camera_backends) is
    # no longer used for RTSP sources at all - those go through a real
    # ffmpeg subprocess now (see the ffmpeg-specific tests below) - but it's
    # still real, live code for non-RTSP sources (webcams, Windows capture
    # devices). Force a multi-backend list regardless of platform so this
    # exercises the fallback logic itself without depending on os.name or
    # a real webcam being present.
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
        return FakeCapture(opens=backend is None)

    with patch(
        "cameras.camera.Camera._camera_backends",
        return_value=[("Primary", 111), ("Auto", None)],
    ):
        with patch("cameras.camera.cv2.VideoCapture", side_effect=fake_video_capture):
            camera = Camera(name="Dock Camera", source=0)
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

    with patch(
        "cameras.camera.Camera._camera_backends",
        return_value=[("Primary", 111), ("Auto", None)],
    ):
        with patch("cameras.camera.cv2.VideoCapture", return_value=FakeCapture()):
            try:
                Camera(name="Dock Camera", source=0)
                assert False, "expected ConnectionError"
            except ConnectionError as exc:
                assert "Dock Camera" in str(exc)


def test_camera_opens_rtsp_via_a_real_ffmpeg_subprocess_and_decodes_frames(monkeypatch):
    # OpenCV's bundled FFMPEG backend can refuse a perfectly valid RTSP
    # source ("backend is generally available but can't be used to capture
    # by name") with no other OpenCV backend available to fall back to on
    # a minimal Linux image - confirmed against a real, VLC-reachable NVR.
    # RTSP sources are captured via a real ffmpeg subprocess instead,
    # sidestepping OpenCV's video I/O layer for RTSP entirely.
    import cv2
    import numpy as np

    ok, encoded = cv2.imencode(".jpg", np.zeros((4, 4, 3), dtype=np.uint8))
    assert ok
    jpeg_bytes = encoded.tobytes()

    class FakeStdout:
        """One frame, then blocks - like a real pipe on a still-alive
        process with no new data yet, unlike io.BytesIO which would
        spuriously return EOF (b"") once exhausted and trigger the
        reconnect path even though nothing actually went wrong."""

        def __init__(self, data: bytes):
            self._data = data
            self._served = False
            self._unblock = threading.Event()

        def read(self, size=-1):
            if not self._served:
                self._served = True
                return self._data
            self._unblock.wait()
            return b""

        def stop(self):
            self._unblock.set()

    class FakeProcess:
        def __init__(self):
            self.stdout = FakeStdout(jpeg_bytes)
            self.stderr = io.BytesIO(b"")
            self.returncode = None
            self.terminated = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            return 0

    fake_process = FakeProcess()
    monkeypatch.setattr("cameras.camera.subprocess.Popen", lambda *a, **k: fake_process)

    camera = Camera(name="Gate Camera", source="rtsp://admin:secret@203.0.113.10:554/stream")
    try:
        assert camera.is_opened()
        frame = None
        for _ in range(50):
            frame = camera.read()
            if frame is not None:
                break
            time.sleep(0.02)
        assert frame is not None
    finally:
        fake_process.stdout.stop()
        camera.release()
        assert fake_process.terminated


def test_camera_ffmpeg_command_only_decodes_keyframes():
    # RTSP-over-TCP sessions commonly start mid-GOP, which HEVC decoders
    # tolerate far worse than H.264 - confirmed live against a real
    # Hikvision NVR streaming H.265 ("PPS id out of range", "Could not
    # find ref with POC"). Keyframes are self-contained and need no
    # missing reference frames, so restricting decode to keyframes only
    # sidesteps the problem instead of just tolerating the errors.
    camera = Camera(name="Gate Camera", source="dummy")
    command = camera._ffmpeg_command()
    assert "-skip_frame" in command
    assert command[command.index("-skip_frame") + 1] == "nokey"
    assert command.index("-skip_frame") < command.index("-i")


def test_camera_stream_check_only_decodes_keyframes():
    server_path = os.path.join(os.path.dirname(__file__), "..", "api", "server.py")
    with open(server_path, encoding="utf-8") as handle:
        source = handle.read()
    assert '"-rtsp_transport", "tcp", "-skip_frame", "nokey", "-i", url,' in source


def test_camera_raises_when_ffmpeg_exits_immediately(monkeypatch):
    class FakeProcess:
        def __init__(self):
            self.stdout = None
            self.stderr = io.BytesIO(b"Connection refused\n")
            self.returncode = 1

        def poll(self):
            return 1

    monkeypatch.setattr("cameras.camera.subprocess.Popen", lambda *a, **k: FakeProcess())
    monkeypatch.setattr("cameras.camera.time.sleep", lambda seconds: None)

    try:
        Camera(name="Gate Camera", source="rtsp://admin:secret@203.0.113.10:554/stream")
        assert False, "expected ConnectionError"
    except ConnectionError as exc:
        assert "Gate Camera" in str(exc)
        assert "Connection refused" in str(exc)


def test_camera_raises_when_ffmpeg_is_not_installed(monkeypatch):
    def raise_not_found(*args, **kwargs):
        raise FileNotFoundError("ffmpeg not found")

    monkeypatch.setattr("cameras.camera.subprocess.Popen", raise_not_found)

    try:
        Camera(name="Gate Camera", source="rtsp://admin:secret@203.0.113.10:554/stream")
        assert False, "expected ConnectionError"
    except ConnectionError as exc:
        assert "ffmpeg is not installed" in str(exc)


def test_cameras_cleanup_deletes_only_matching_name_prefix(monkeypatch, tmp_path):
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
    # Isolate the cleanup logic itself - the detection-restart side effect
    # (and its own real connectivity re-test of every active camera) is
    # already covered elsewhere.
    monkeypatch.setattr(server, "start_detection", lambda request=None: None)

    db = server._get_camera_db()  # also seeds a default "Camera 1" (source=0)
    stale_one = db.add_camera("Warehouse NVR Camera 1", "rtsp://a/1", "connected")
    stale_two = db.add_camera("Warehouse NVR Camera 2", "rtsp://a/2", "connected")
    keep = db.add_camera("NVR Next 1 Camera 1", "rtsp://b/1", "connected")
    db.assign_slot(stale_one["id"], 10)
    db.assign_slot(stale_two["id"], 11)
    db.assign_slot(keep["id"], 12)

    client = TestClient(server.app)
    response = client.post("/api/cameras/cleanup", json={"name_prefix": "Warehouse NVR"})

    assert response.status_code == 200
    body = response.json()
    assert body["deleted_count"] == 2
    assert {entry["name"] for entry in body["deleted"]} == {
        "Warehouse NVR Camera 1",
        "Warehouse NVR Camera 2",
    }

    remaining_names = {camera["name"] for camera in db.list_cameras(include_secret=False)}
    assert remaining_names == {"Camera 1", "NVR Next 1 Camera 1"}
    active_names = {
        camera["name"] for camera in db.list_active_cameras(include_secret=False)
    }
    assert active_names == {"Camera 1", "NVR Next 1 Camera 1"}


def test_cameras_cleanup_requires_a_non_empty_prefix():
    from fastapi.testclient import TestClient

    client = TestClient(server.app)
    response = client.post("/api/cameras/cleanup", json={"name_prefix": "   "})

    assert response.status_code == 400
