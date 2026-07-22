"""Service probing and vendor identification.

Once a port is known to be open, a light protocol-appropriate probe learns two
things the port scan alone can't: whether the service needs authentication,
and any vendor/model banner it volunteers. No credentials are ever sent here -
that only happens later, after the operator has chosen a service.
"""

from __future__ import annotations

import re
import socket
import ssl

_PROBE_TIMEOUT_SECONDS = 3.0
_MAX_BANNER_BYTES = 4096

# Substrings (case-insensitive) that identify a vendor from a Server banner or
# auth realm. Ordered by specificity; first hit wins.
_VENDOR_MARKERS: list[tuple[str, str]] = [
    ("hikvision", "hikvision"),
    ("app-webs", "hikvision"),  # Hikvision's embedded web server
    ("dnvrs-webs", "hikvision"),
    ("dvrdvs-webs", "hikvision"),
    ("dahua", "dahua"),
    ("webs\\b", "dahua"),  # Dahua's embedded server often reports "Webs"
    ("axis", "axis"),
    ("boa/", "generic-embedded"),
    ("lighttpd", "generic-embedded"),
]

_SERVER_HEADER_RE = re.compile(rb"^server:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_WWW_AUTH_RE = re.compile(rb"^www-authenticate:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_RTSP_STATUS_RE = re.compile(rb"^RTSP/1\.\d\s+(\d{3})", re.IGNORECASE)
_HTTP_STATUS_RE = re.compile(rb"^HTTP/1\.\d\s+(\d{3})", re.IGNORECASE)


class ServiceProbe:
    """Result of probing one open service port."""

    def __init__(self, reachable: bool, requires_auth: bool, banner: str | None):
        self.reachable = reachable
        self.requires_auth = requires_auth
        self.banner = banner


def identify_vendor(banners: dict[str, str]) -> str | None:
    haystack = " ".join(banners.values()).lower()
    for pattern, vendor in _VENDOR_MARKERS:
        if re.search(pattern, haystack):
            return vendor
    return None


def probe_rtsp(ip: str, port: int, timeout: float = _PROBE_TIMEOUT_SECONDS) -> ServiceProbe:
    """Send an unauthenticated RTSP OPTIONS and read the response.

    A 401/407 means the stream exists but needs credentials; a 200 means it is
    openly reachable. The Server header, if present, feeds vendor ID.
    """
    request = (
        f"OPTIONS rtsp://{ip}:{port}/ RTSP/1.0\r\n"
        "CSeq: 1\r\n"
        "User-Agent: AI-Vision-Discovery\r\n\r\n"
    ).encode("ascii")
    try:
        with socket.create_connection((ip, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(request)
            data = sock.recv(_MAX_BANNER_BYTES)
    except OSError:
        return ServiceProbe(reachable=False, requires_auth=False, banner=None)

    status = _RTSP_STATUS_RE.search(data)
    requires_auth = bool(_WWW_AUTH_RE.search(data)) or (status is not None and status.group(1) in (b"401", b"407"))
    server = _SERVER_HEADER_RE.search(data)
    return ServiceProbe(
        reachable=True,
        requires_auth=requires_auth,
        banner=server.group(1).decode("latin-1") if server else None,
    )


def probe_http(ip: str, port: int, tls: bool, timeout: float = _PROBE_TIMEOUT_SECONDS) -> ServiceProbe:
    """GET / over HTTP(S) and read headers for the Server banner + auth need.

    HTTPS uses an unverified TLS context on purpose: this is a direct probe of
    an embedded device that almost always presents a self-signed certificate,
    not a request through the agent egress proxy, so certificate verification
    would reject every real device. It never sends credentials or a body.
    """
    request = (
        "GET / HTTP/1.1\r\n"
        f"Host: {ip}\r\n"
        "User-Agent: AI-Vision-Discovery\r\n"
        "Accept: */*\r\n"
        "Connection: close\r\n\r\n"
    ).encode("ascii")
    try:
        raw = socket.create_connection((ip, port), timeout=timeout)
    except OSError:
        return ServiceProbe(reachable=False, requires_auth=False, banner=None)
    try:
        raw.settimeout(timeout)
        if tls:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            sock = context.wrap_socket(raw, server_hostname=None)
        else:
            sock = raw
        sock.sendall(request)
        data = sock.recv(_MAX_BANNER_BYTES)
    except OSError:
        return ServiceProbe(reachable=True, requires_auth=False, banner=None)
    finally:
        try:
            raw.close()
        except OSError:
            pass

    status = _HTTP_STATUS_RE.search(data)
    requires_auth = bool(_WWW_AUTH_RE.search(data)) or (status is not None and status.group(1) == b"401")
    server = _SERVER_HEADER_RE.search(data)
    return ServiceProbe(
        reachable=True,
        requires_auth=requires_auth,
        banner=server.group(1).decode("latin-1") if server else None,
    )
