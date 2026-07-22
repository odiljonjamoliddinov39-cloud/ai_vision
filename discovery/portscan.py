"""Bounded, safety-guarded TCP port scanning for device discovery.

This is deliberately *not* a general-purpose scanner. It probes a small fixed
set of well-known camera/NVR service ports, with per-port timeouts and a
capped concurrency, and it refuses to scan addresses that are not publicly
routable unless explicitly allowed. That combination keeps the feature from
being usable as an SSRF pivot or an internal-network scanner from the server.
"""

from __future__ import annotations

import ipaddress
import os
import socket
from concurrent.futures import ThreadPoolExecutor

from discovery.models import PortResult

# The known ports we probe. Kept intentionally small: these are the ports a
# real NVR/DVR/IP-camera actually exposes, not a broad sweep.
KNOWN_PORTS: dict[int, str] = {
    80: "http",
    443: "https",
    554: "rtsp",
    8000: "device",  # Hikvision SDK / ISAPI + common ONVIF port
    8080: "http",  # common HTTP-alt / ONVIF
    8554: "rtsp",  # common RTSP-alt
    2020: "device",  # Dahua auto-registration / management
    37777: "device",  # Dahua DVR/NVR TCP port
}

_CONNECT_TIMEOUT_SECONDS = 2.0
_MAX_CONCURRENCY = 8


class DiscoveryHostError(ValueError):
    """Raised when a host is syntactically invalid or disallowed by policy."""


def _allow_private_hosts() -> bool:
    return os.getenv("DISCOVERY_ALLOW_PRIVATE_HOSTS", "").strip().lower() in {"1", "true", "yes"}


def resolve_and_guard(host: str) -> str:
    """Validate a user-supplied host and return a numeric IP to scan.

    Blocks loopback, link-local (incl. the cloud metadata address
    169.254.169.254), private, multicast, and otherwise non-global addresses
    by default so the scanner can't be turned against the server's own network
    or a cloud metadata endpoint. Set DISCOVERY_ALLOW_PRIVATE_HOSTS=1 to permit
    LAN targets (e.g. an on-prem deployment scanning 192.168.x.x).
    """
    cleaned = (host or "").strip()
    if not cleaned:
        raise DiscoveryHostError("A device IP address or hostname is required.")
    if "/" in cleaned or " " in cleaned:
        raise DiscoveryHostError("Enter a single IP address or hostname, without a path or spaces.")

    # Accept a bare IP directly; otherwise resolve the hostname to one.
    try:
        ip = ipaddress.ip_address(cleaned)
    except ValueError:
        try:
            resolved = socket.gethostbyname(cleaned)
        except OSError as exc:
            raise DiscoveryHostError(f"Could not resolve '{cleaned}': {exc.strerror or exc}") from exc
        ip = ipaddress.ip_address(resolved)

    if not _allow_private_hosts() and not ip.is_global:
        raise DiscoveryHostError(
            f"{cleaned} is not a publicly routable address. Discovery targets a device reachable "
            "over the internet (public IP or DDNS hostname). Set DISCOVERY_ALLOW_PRIVATE_HOSTS=1 "
            "to allow scanning private/LAN addresses from an on-premise deployment."
        )
    return str(ip)


def _probe_port(ip: str, port: int, service: str, timeout: float) -> PortResult:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return PortResult(port=port, service=service, open=True)
    except TimeoutError:
        return PortResult(port=port, service=service, open=False, detail="timed out")
    except OSError as exc:
        return PortResult(port=port, service=service, open=False, detail=exc.strerror or str(exc))


def scan_ports(
    ip: str,
    ports: dict[int, str] | None = None,
    timeout: float = _CONNECT_TIMEOUT_SECONDS,
    max_concurrency: int = _MAX_CONCURRENCY,
) -> list[PortResult]:
    """Probe the given ports on an already-guarded IP, concurrently but bounded.

    ``ip`` must already have passed ``resolve_and_guard``.
    """
    targets = ports or KNOWN_PORTS
    results: list[PortResult] = []
    with ThreadPoolExecutor(max_workers=max(1, min(max_concurrency, len(targets)))) as pool:
        futures = [
            pool.submit(_probe_port, ip, port, service, timeout)
            for port, service in targets.items()
        ]
        for future in futures:
            results.append(future.result())
    results.sort(key=lambda result: result.port)
    return results
