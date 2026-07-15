import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.server import _redact_config, _security_enabled, _valid_api_key, status  # noqa: E402
from database.security_audit_db import SecurityAuditDB  # noqa: E402


class FakeRequest:
    def __init__(self, headers=None, query_params=None):
        self.headers = headers or {}
        self.query_params = query_params or {}
        self.client = SimpleNamespace(host="127.0.0.1")


def test_security_status_reflects_api_key_enabled(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "test-secret")

    assert _security_enabled() is True
    assert status()["security"]["api_key_required"] is True


def test_api_key_validation_accepts_header_and_query(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "test-secret")

    denied = FakeRequest()
    header_allowed = FakeRequest(headers={"x-api-key": "test-secret"})
    query_allowed = FakeRequest(query_params={"api_key": "test-secret"})

    assert _valid_api_key(denied) is False
    assert _valid_api_key(header_allowed) is True
    assert _valid_api_key(query_allowed) is True


def test_security_audit_chain_detects_valid_log(tmp_path):
    db = SecurityAuditDB(str(tmp_path / "security_audit.db"))

    db.append("tester", "camera.update", {"slot": 1})
    db.append("tester", "detection.start", {"config": "config/config.yaml"})

    result = db.verify()
    events = db.recent()

    assert result["verified"] is True
    assert result["event_count"] == 2
    assert len(events) == 2


def test_config_redaction_masks_camera_sources():
    config = {
        "cameras": [
            {
                "name": "NVR Slot 1",
                "source": "rtsp://admin:secret@203.0.113.10:554/Streaming/Channels/101",
            }
        ]
    }

    redacted = _redact_config(config)

    assert "secret" not in redacted["cameras"][0]["source"]
    assert "rtsp://admin:****@203.0.113.10:554/Streaming/Channels/101" == redacted["cameras"][0]["source"]
    assert config["cameras"][0]["source"].startswith("rtsp://admin:secret@")
