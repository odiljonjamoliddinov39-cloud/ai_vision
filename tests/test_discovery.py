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
