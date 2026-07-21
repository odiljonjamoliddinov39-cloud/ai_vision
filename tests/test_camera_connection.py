import os
import subprocess
import sys
from unittest.mock import patch

import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import api.server as server
import main as app_main
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
from cameras.camera import _mask_source
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


def test_controller_stream_url_builds_channel_rtsp_url_with_credentials():
    controller = CameraControllerCreate(
        name="NVR",
        host="192.168.1.10",
        username="admin",
        password="p@ss word",
        channel_count=2,
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


def test_detector_camera_configs_load_from_database(monkeypatch, tmp_path):
    camera_db_path = tmp_path / "cameras.db"
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

    monkeypatch.setenv("CAMERA_DB_PATH", str(camera_db_path))

    cameras = app_main.load_camera_configs_from_db()

    assert [camera["name"] for camera in cameras] == ["NVR Camera 1", "NVR Camera 2"]
    assert [camera["slot_number"] for camera in cameras] == [1, 2]
    assert cameras[0]["source"].endswith("/Streaming/Channels/101")


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


def test_save_camera_controller_uses_single_01_template_and_deduplicates(monkeypatch, tmp_path):
    camera_db_path = tmp_path / "cameras.db"

    monkeypatch.setattr(server, "CAMERA_DB_PATH", camera_db_path)
    monkeypatch.setattr(server, "_camera_db", None)
    monkeypatch.setattr(server, "_status", lambda: {"running": False})
    monkeypatch.setattr(
        server,
        "_test_camera_stream",
        lambda stream_url, timeout_seconds=10: {
            "status": "connected",
            "message": "Camera stream opened and returned a frame.",
            "details": {"stream_url": stream_url, "reason": "ok"},
        },
    )

    controller = CameraControllerCreate(
        name="Main NVR",
        host="203.0.113.10",
        username="admin",
        password="secret",
        channel_count=3,
        channel_start=1,
        start_slot=1,
    )

    first = server.save_camera_controller(controller)
    second = server.save_camera_controller(controller)

    db = server._get_camera_db()
    active = db.list_active_cameras(include_secret=True)
    cameras = db.list_cameras(include_secret=True)
    urls = {camera["stream_url"] for camera in cameras}

    assert len(cameras) == 3
    assert len(active) == 3
    assert [camera["slot_number"] for camera in active] == [1, 2, 3]
    assert any(url.endswith("/Streaming/Channels/101") for url in urls)
    assert any(url.endswith("/Streaming/Channels/201") for url in urls)
    assert any(url.endswith("/Streaming/Channels/301") for url in urls)
    assert first["results"][0]["stream_url"].endswith("/Streaming/Channels/101")
    assert second["results"][2]["stream_url"].endswith("/Streaming/Channels/301")
