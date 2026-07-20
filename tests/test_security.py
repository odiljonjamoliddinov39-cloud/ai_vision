import os
import sys
import asyncio
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import api.server as server  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from api.server import (  # noqa: E402
    _authorized_modules,
    _rbac_context,
    _redact_config,
    _security_enabled,
    _valid_api_key,
    dashboard_v2_navigation,
    live_frame,
    status,
)
from database.security_audit_db import SecurityAuditDB  # noqa: E402


class FakeRequest:
    def __init__(self, headers=None, query_params=None):
        self.headers = headers or {}
        self.query_params = query_params or {}
        self.client = SimpleNamespace(host="127.0.0.1")


def test_vercel_dashboard_preflight_allows_identity_headers():
    client = TestClient(server.app)

    response = client.options(
        "/api/v2/rbac/me",
        headers={
            "Origin": "https://ai-vision-dashboard-phi.vercel.app",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-ai-role,x-ai-user-name,x-ai-company",
        },
    )

    assert response.status_code == 200
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "x-ai-role" in allowed_headers
    assert "x-ai-user-name" in allowed_headers
    assert "x-ai-company" in allowed_headers


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


def test_live_frame_returns_stable_jpeg_bytes(tmp_path, monkeypatch):
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    jpeg = b"\xff\xd8stable-frame\xff\xd9"
    (snapshot_dir / "latest_slot_6.jpg").write_bytes(jpeg)
    monkeypatch.setattr(server, "SNAPSHOT_DIR", snapshot_dir)

    response = asyncio.run(live_frame(slot=6))

    assert response.body == jpeg
    assert response.media_type == "image/jpeg"


def test_dashboard_v2_rbac_filters_user_modules():
    request = FakeRequest(headers={"x-ai-role": "viewer"})
    context = _rbac_context(request)
    modules = _authorized_modules("user", set(context["permissions"]))
    module_ids = {module["id"] for module in modules}

    assert "live" in module_ids
    assert "verification" not in module_ids


def test_dashboard_v2_navigation_rejects_unknown_surface():
    request = FakeRequest(headers={"x-ai-role": "super_admin"})

    try:
        dashboard_v2_navigation(request, surface="unknown")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        raise AssertionError("Unknown dashboard surface should be rejected")
