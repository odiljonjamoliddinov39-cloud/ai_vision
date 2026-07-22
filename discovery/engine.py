"""Discovery Engine orchestration.

``discover_device(host)`` is the single public entry point: it guards the
target, scans the known service ports, probes each open one, and returns a
structured :class:`DiscoveryResult` describing what the device is and which
services the operator can connect to. It never asks for or sends credentials.
"""

from __future__ import annotations

from datetime import datetime, timezone

from discovery import fingerprint as fp
from discovery.models import (
    DeviceFingerprint,
    DiscoveredService,
    DiscoveryResult,
    PortResult,
)
from discovery.portscan import DiscoveryHostError, resolve_and_guard, scan_ports

# Display protocol names per canonical service, and whether the "device" port
# should be surfaced as an ONVIF candidate.
_PROTOCOL_LABELS = {
    "rtsp": "RTSP",
    "http": "HTTP",
    "https": "HTTPS",
    "device": "Device Service",
}


def _service_for_port(ip: str, result: PortResult) -> tuple[DiscoveredService, str | None]:
    """Probe one open port; return the operator-facing service + any banner."""
    service = result.service
    if service == "rtsp":
        probe = fp.probe_rtsp(ip, result.port)
    elif service in ("http", "device"):
        probe = fp.probe_http(ip, result.port, tls=False)
    elif service == "https":
        probe = fp.probe_http(ip, result.port, tls=True)
    else:  # pragma: no cover - defensive; KNOWN_PORTS only has the above
        probe = fp.ServiceProbe(reachable=True, requires_auth=False, banner=None)

    # The port scan already proved this TCP port is open, so the service is
    # reachable by definition. The probe only *enriches* (auth hint + banner)
    # and is best-effort: some NVRs accept the socket but don't answer an
    # unauthenticated RTSP OPTIONS quickly, so a probe timeout must never
    # downgrade an open port to "unreachable" - that produced a false negative
    # against a real NVR whose RTSP port was demonstrably open. Auth detection
    # here is likewise only a hint; credentials are always enterable at connect
    # time regardless, because OPTIONS-based detection is unreliable.
    status = "requires_auth" if probe.requires_auth else "available"

    return (
        DiscoveredService(
            protocol=_PROTOCOL_LABELS.get(service, service.upper()),
            port=result.port,
            status=status,
            requires_auth=probe.requires_auth,
        ),
        probe.banner,
    )


def _classify_device_type(vendor: str | None, open_services: list[str]) -> str:
    # A "device"/SDK management port alongside RTSP is characteristic of an
    # NVR/DVR; RTSP alone is more likely a single IP camera. Best-effort only.
    if "device" in open_services and "rtsp" in open_services:
        return "nvr_or_dvr"
    if "rtsp" in open_services:
        return "ip_camera"
    return "unknown"


def discover_device(host: str) -> DiscoveryResult:
    scanned_at = datetime.now(timezone.utc).isoformat()
    try:
        ip = resolve_and_guard(host)
    except DiscoveryHostError as exc:
        return DiscoveryResult(
            host=host,
            reachable=False,
            scanned_at=scanned_at,
            error=str(exc),
        )

    ports = scan_ports(ip)
    open_ports = [port for port in ports if port.open]
    if not open_ports:
        return DiscoveryResult(
            host=host,
            reachable=False,
            scanned_at=scanned_at,
            ports=ports,
            error=(
                f"{host} did not respond on any known camera/NVR service port. "
                "Confirm the device is online and that its stream/management ports are "
                "forwarded to the public address."
            ),
        )

    services: list[DiscoveredService] = []
    banners: dict[str, str] = {}
    for port in open_ports:
        service, banner = _service_for_port(ip, port)
        services.append(service)
        if banner:
            banners[service.protocol] = banner

    vendor = fp.identify_vendor(banners)
    fingerprint = DeviceFingerprint(
        vendor=vendor,
        device_type=_classify_device_type(vendor, [port.service for port in open_ports]),
        banners=banners,
    )
    return DiscoveryResult(
        host=host,
        reachable=True,
        scanned_at=scanned_at,
        fingerprint=fingerprint,
        services=services,
        ports=ports,
    )
