import os
import subprocess
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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


def test_live_feed_paths_fall_back_to_global_latest():
    paths = _live_feed_paths(slot=3)

    assert [path.name for path in paths] == ["latest_slot_3.jpg", "latest.jpg"]


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
