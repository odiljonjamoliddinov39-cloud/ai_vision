import os
import subprocess
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.server import _redact_sensitive_text, _test_camera_stream
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
