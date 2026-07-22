"""Tests for the device-first Discovery Engine.

Network behaviour is exercised against short-lived local sockets rather than
mocks where it's cheap to do so, so the real socket/parse code paths run.
Every server thread is bounded by a timeout to avoid hangs.
"""

import socket
import threading

import pytest
from fastapi.testclient import TestClient

from api import server
from discovery import discover_device
from discovery.engine import _classify_device_type
from discovery.fingerprint import identify_vendor, probe_rtsp
from discovery.models import DiscoveredService, DiscoveryResult, PortResult
from discovery.portscan import DiscoveryHostError, resolve_and_guard, scan_ports


class _ScriptedServer:
    """A one-shot TCP server that optionally returns a scripted response."""

    def __init__(self, response: bytes | None = None, read_first: bool = True):
        self._response = response
        self._read_first = read_first
        self._sock = socket.socket()
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(1)
        self._sock.settimeout(5.0)
        self.port = self._sock.getsockname()[1]
        self._thread: threading.Thread | None = None

    def __enter__(self):
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        return self

    def _serve(self):
        try:
            conn, _ = self._sock.accept()
        except OSError:
            return
        try:
            conn.settimeout(5.0)
            if self._read_first:
                try:
                    conn.recv(4096)
                except OSError:
                    pass
            if self._response is not None:
                conn.sendall(self._response)
        finally:
            conn.close()

    def __exit__(self, *exc):
        try:
            self._sock.close()
        except OSError:
            pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)


def test_resolve_and_guard_blocks_non_global_hosts_by_default(monkeypatch):
    monkeypatch.delenv("DISCOVERY_ALLOW_PRIVATE_HOSTS", raising=False)
    for blocked in ("127.0.0.1", "192.168.1.10", "10.0.0.5", "169.254.169.254"):
        with pytest.raises(DiscoveryHostError):
            resolve_and_guard(blocked)


def test_resolve_and_guard_allows_private_when_opted_in(monkeypatch):
    monkeypatch.setenv("DISCOVERY_ALLOW_PRIVATE_HOSTS", "1")
    assert resolve_and_guard("192.168.1.10") == "192.168.1.10"


def test_resolve_and_guard_accepts_a_public_ip(monkeypatch):
    monkeypatch.delenv("DISCOVERY_ALLOW_PRIVATE_HOSTS", raising=False)
    assert resolve_and_guard("8.8.8.8") == "8.8.8.8"


def test_resolve_and_guard_rejects_urls_and_paths():
    with pytest.raises(DiscoveryHostError):
        resolve_and_guard("87.192.242.82/Streaming/Channels/101")
    with pytest.raises(DiscoveryHostError):
        resolve_and_guard("")


def test_scan_ports_detects_open_and_closed(monkeypatch):
    # A listening socket is open; a just-closed one gives us a definitely-free port.
    with _ScriptedServer(read_first=False) as open_server:
        closed = socket.socket()
        closed.bind(("127.0.0.1", 0))
        closed_port = closed.getsockname()[1]
        closed.close()

        results = scan_ports(
            "127.0.0.1",
            {open_server.port: "rtsp", closed_port: "http"},
        )

    by_port = {result.port: result for result in results}
    assert by_port[open_server.port].open is True
    assert by_port[closed_port].open is False


def test_probe_rtsp_reports_auth_and_banner_on_401():
    response = (
        b"RTSP/1.0 401 Unauthorized\r\n"
        b"CSeq: 1\r\n"
        b"Server: Hikvision/V5.5.0\r\n"
        b'WWW-Authenticate: Digest realm="IP Camera", nonce="abc"\r\n\r\n'
    )
    with _ScriptedServer(response=response) as srv:
        probe = probe_rtsp("127.0.0.1", srv.port)

    assert probe.reachable is True
    assert probe.requires_auth is True
    assert probe.banner == "Hikvision/V5.5.0"


def test_probe_rtsp_reports_open_stream_on_200():
    response = b"RTSP/1.0 200 OK\r\nCSeq: 1\r\nPublic: OPTIONS, DESCRIBE\r\n\r\n"
    with _ScriptedServer(response=response) as srv:
        probe = probe_rtsp("127.0.0.1", srv.port)

    assert probe.reachable is True
    assert probe.requires_auth is False


def test_identify_vendor_matches_known_banners():
    assert identify_vendor({"RTSP": "Hikvision/V5.5.0"}) == "hikvision"
    assert identify_vendor({"HTTP": "App-webs/"}) == "hikvision"
    assert identify_vendor({"HTTP": "Boa/0.94"}) == "generic-embedded"
    assert identify_vendor({"HTTP": "nginx"}) is None


def test_classify_device_type_distinguishes_nvr_from_camera():
    assert _classify_device_type("hikvision", ["rtsp", "device"]) == "nvr_or_dvr"
    assert _classify_device_type("hikvision", ["rtsp"]) == "ip_camera"
    assert _classify_device_type(None, ["http"]) == "unknown"


def test_discover_device_returns_error_for_disallowed_host(monkeypatch):
    monkeypatch.delenv("DISCOVERY_ALLOW_PRIVATE_HOSTS", raising=False)
    result = discover_device("192.168.1.50")
    assert isinstance(result, DiscoveryResult)
    assert result.reachable is False
    assert result.error is not None
    assert result.services == []


def test_discover_device_builds_services_from_open_ports(monkeypatch):
    # Drive the orchestration deterministically without real network by
    # canning the scan + probes.
    monkeypatch.setattr(
        "discovery.engine.scan_ports",
        lambda ip, *a, **k: [
            PortResult(port=554, service="rtsp", open=True),
            PortResult(port=8000, service="device", open=True),
            PortResult(port=443, service="https", open=False),
        ],
    )

    class _Probe:
        def __init__(self, reachable, requires_auth, banner):
            self.reachable = reachable
            self.requires_auth = requires_auth
            self.banner = banner

    monkeypatch.setattr(
        "discovery.engine.fp.probe_rtsp",
        lambda ip, port, **k: _Probe(True, True, "Hikvision/V5.5.0"),
    )
    monkeypatch.setattr(
        "discovery.engine.fp.probe_http",
        lambda ip, port, tls, **k: _Probe(True, False, "App-webs/"),
    )

    result = discover_device("8.8.8.8")

    assert result.reachable is True
    assert result.fingerprint.vendor == "hikvision"
    assert result.fingerprint.device_type == "nvr_or_dvr"
    protocols = {service.protocol: service for service in result.services}
    assert protocols["RTSP"].requires_auth is True
    assert protocols["RTSP"].status == "requires_auth"
    assert protocols["Device Service"].status == "available"


def test_discovery_scan_endpoint_returns_structured_services(monkeypatch):
    canned = DiscoveryResult(
        host="203.0.113.10",
        reachable=True,
        scanned_at="2026-07-21T14:00:00+00:00",
        services=[
            DiscoveredService(protocol="RTSP", port=554, status="requires_auth", requires_auth=True),
        ],
    )
    monkeypatch.setattr(server, "discover_device", lambda host: canned)

    with TestClient(server.app) as client:
        response = client.post("/api/discovery/scan", json={"host": "203.0.113.10"})

    assert response.status_code == 200
    body = response.json()
    assert body["reachable"] is True
    assert body["services"][0]["protocol"] == "RTSP"
    assert body["services"][0]["requires_auth"] is True


# --- Stream enumeration providers ------------------------------------------

from discovery.providers import enumerate_streams, select_provider  # noqa: E402
from discovery.providers.base import StreamCredentials  # noqa: E402
from discovery.providers.onvif_provider import OnvifStreamProvider  # noqa: E402


def test_hikvision_provider_builds_the_working_channel_paths():
    result = enumerate_streams(
        host="87.192.242.82",
        port=554,
        protocol="rtsp",
        credentials=StreamCredentials("admin", "Q135246q"),
        vendor="hikvision",
        channel_count=3,
    )
    assert result.provider == "hikvision"
    urls = [channel.stream_url for channel in result.channels]
    assert urls == [
        "rtsp://admin:Q135246q@87.192.242.82:554/Streaming/Channels/101",
        "rtsp://admin:Q135246q@87.192.242.82:554/Streaming/Channels/201",
        "rtsp://admin:Q135246q@87.192.242.82:554/Streaming/Channels/301",
    ]


def test_dahua_provider_uses_its_realmonitor_path():
    result = enumerate_streams(
        host="203.0.113.5",
        port=554,
        protocol="rtsp",
        credentials=StreamCredentials("admin", "x"),
        vendor="dahua",
        channel_count=2,
    )
    assert result.provider == "dahua"
    assert result.channels[1].stream_url == (
        "rtsp://admin:x@203.0.113.5:554/cam/realmonitor?channel=2&subtype=0"
    )


def test_unknown_vendor_falls_back_to_generic_single_stream():
    result = enumerate_streams(
        host="203.0.113.5",
        port=554,
        protocol="rtsp",
        credentials=None,
        vendor=None,
        channel_count=5,
    )
    assert result.provider == "generic-rtsp"
    assert len(result.channels) == 1
    assert result.channels[0].stream_url == "rtsp://203.0.113.5:554/"


def test_credentials_are_url_encoded_in_stream_urls():
    result = enumerate_streams(
        host="203.0.113.5",
        port=554,
        protocol="rtsp",
        credentials=StreamCredentials("admin", "p@ss/word"),
        vendor="hikvision",
        channel_count=1,
    )
    # '@' and '/' in the password must be percent-encoded so they don't corrupt
    # the URL's authority/path.
    assert "p%40ss%2Fword" in result.channels[0].stream_url


def test_onvif_provider_is_skipped_when_the_library_is_absent():
    # The optional ONVIF dependency is not installed here, so the provider must
    # report itself unavailable rather than raising - discovery still works.
    provider = OnvifStreamProvider()
    assert provider.supports(vendor="hikvision", protocol="rtsp") is False
    # And it is not the provider selected for a known vendor.
    selected = select_provider(vendor="hikvision", protocol="rtsp")
    assert selected is not None
    assert selected.name == "hikvision"


def test_discovery_connect_registers_enumerated_channels(tmp_path, monkeypatch):
    from database.camera_db import CameraDB

    monkeypatch.delenv("DATABASE_URL", raising=False)
    db = CameraDB(str(tmp_path / "cameras.db"))
    monkeypatch.setattr(server, "_get_camera_db", lambda: db)
    monkeypatch.setattr(server, "_sync_config_active_cameras", lambda db: None)
    monkeypatch.setattr(server, "_status", lambda: {"running": False})
    # Don't touch the real config / spawn a detector from a test.
    monkeypatch.setattr(server, "stop_detection", lambda: None)
    monkeypatch.setattr(server, "start_detection", lambda request: None)
    # Skip the real ffmpeg stream test; treat every enumerated stream as reachable.
    monkeypatch.setattr(server, "_test_camera_stream", lambda url: {"status": "connected", "message": "ok"})

    with TestClient(server.app) as client:
        response = client.post(
            "/api/discovery/connect",
            json={
                "host": "8.8.8.8",
                "protocol": "rtsp",
                "port": 554,
                "username": "admin",
                "password": "secret",
                "vendor": "hikvision",
                "channel_count": 3,
                "name": "Warehouse",
                "test_streams": True,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "hikvision"
    assert len(body["results"]) == 3
    assert all(result["active"] for result in body["results"])
    assert [row["name"] for row in body["cameras"]] == [
        "Warehouse Channel 1",
        "Warehouse Channel 2",
        "Warehouse Channel 3",
    ]
    # Credentials must never come back in the masked camera listing.
    assert all("secret" not in row["masked_stream_url"] for row in body["cameras"])


def test_discovery_connect_rejects_a_disallowed_host(monkeypatch):
    with TestClient(server.app) as client:
        response = client.post(
            "/api/discovery/connect",
            json={"host": "192.168.1.10", "protocol": "rtsp", "vendor": "hikvision"},
        )
    assert response.status_code == 400


# --- Frontend device-first discovery flow ----------------------------------

def _app_js() -> str:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    return (root / "dashboard-v2" / "app.js").read_text(encoding="utf-8")


def test_camera_page_uses_device_first_discovery_not_the_manual_form():
    source = _app_js()
    # The camera page renders the discovery panel, and the search/connect flow
    # is wired to the discovery endpoints.
    assert "data-discovery-panel" in source
    assert "function renderDiscoveryPanel(container)" in source
    assert 'accountsApi("/api/v2/devices/discover"' in source
    assert "/api/v2/devices/${st.deviceId}/authenticate" in source
    assert "function discoverySelectService(container, btn)" in source


def test_manual_stream_entry_is_removed_from_normal_discovery_flow():
    source = _app_js()
    # The legacy manual form still exists but only inside the Advanced
    # disclosure, not as the primary path.
    assert "discovery-advanced" not in source
    assert "stream URL manually" not in source
    assert "function manualNvrFormHtml()" not in source


def test_open_port_with_a_flaky_probe_stays_available_not_unreachable(monkeypatch):
    # The scan proved 554 open; a probe that can't get a clean OPTIONS response
    # (e.g. timeout) must NOT downgrade the service to "unreachable".
    monkeypatch.setattr(
        "discovery.engine.scan_ports",
        lambda ip, *a, **k: [PortResult(port=554, service="rtsp", open=True)],
    )

    class _Probe:
        reachable = False
        requires_auth = False
        banner = None

    monkeypatch.setattr("discovery.engine.fp.probe_rtsp", lambda ip, port, **k: _Probe())

    result = discover_device("8.8.8.8")
    assert result.reachable is True
    assert result.services[0].status == "available"


def test_discovery_connect_form_always_offers_optional_credentials():
    source = _app_js()
    # RTSP auth probing is best-effort; an "Available" port can still require
    # credentials for the real channel profile.
    assert 'placeholder="Username (optional)"' in source
    assert 'placeholder="Password (optional)"' in source
    assert "discoveryState.selectedRequiresAuth" in source


def test_connect_form_hides_vendor_selection_from_operator():
    source = _app_js()
    assert "data-discovery-vendor" not in source
    assert 'container.querySelector("[data-discovery-vendor]")?.value' not in source


def test_explicit_hikvision_vendor_builds_channel_paths_even_without_detection(tmp_path, monkeypatch):
    # The reported failure: an NVR whose brand wasn't detected fell back to the
    # generic single-stream provider. An explicit "hikvision" choice must
    # produce the real channel paths regardless of what discovery detected.
    from database.camera_db import CameraDB

    monkeypatch.delenv("DATABASE_URL", raising=False)
    db = CameraDB(str(tmp_path / "cameras.db"))
    monkeypatch.setattr(server, "_get_camera_db", lambda: db)
    monkeypatch.setattr(server, "_sync_config_active_cameras", lambda db: None)
    monkeypatch.setattr(server, "_status", lambda: {"running": False})
    monkeypatch.setattr(server, "stop_detection", lambda: None)
    monkeypatch.setattr(server, "start_detection", lambda request: None)
    monkeypatch.setattr(server, "_test_camera_stream", lambda url: {"status": "connected", "message": "ok"})

    with TestClient(server.app) as client:
        response = client.post(
            "/api/discovery/connect",
            json={
                "host": "8.8.8.8",
                "protocol": "rtsp",
                "port": 554,
                "username": "admin",
                "password": "secret",
                "vendor": "hikvision",  # explicit, even though detection found nothing
                "channel_count": 2,
                "name": "NVR main",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "hikvision"
    urls = sorted(row["masked_stream_url"] for row in body["cameras"])
    assert urls[0].endswith("/Streaming/Channels/101")
    assert urls[1].endswith("/Streaming/Channels/201")


def test_v2_unknown_rtsp_defaults_to_hikvision_channel_path(tmp_path, monkeypatch):
    from database.camera_db import CameraDB
    from database.device_db import DeviceDB

    monkeypatch.delenv("DATABASE_URL", raising=False)
    camera_db = CameraDB(str(tmp_path / "cameras.db"))
    device_db = DeviceDB(str(tmp_path / "devices.db"))
    monkeypatch.setattr(server, "_get_camera_db", lambda: camera_db)
    monkeypatch.setattr(server, "_get_device_db", lambda: device_db)
    monkeypatch.setattr(server, "_sync_config_active_cameras", lambda db: None)
    monkeypatch.setattr(
        server,
        "_start_stream_for_camera",
        lambda camera: {"channel_id": str(camera["id"]), "status": "starting"},
    )

    device = device_db.upsert_device_from_discovery(
        name="Unknown RTSP Camera",
        host="8.8.8.8",
        result={
            "reachable": True,
            "fingerprint": {"vendor": None, "device_type": "ip_camera", "banners": {}},
            "services": [
                {"protocol": "RTSP", "port": 554, "status": "available", "requires_auth": False}
            ],
        },
    )

    with TestClient(server.app) as client:
        response = client.post(
            f"/api/v2/devices/{device['id']}/authenticate",
            json={
                "protocol": "rtsp",
                "port": 554,
                "username": "admin",
                "password": "secret",
                "channel_count": 1,
                "make_active": True,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "hikvision"
    assert body["channels"][0]["masked_stream_reference"].endswith("/Streaming/Channels/101")
    assert "secret" not in body["channels"][0]["masked_stream_reference"]
