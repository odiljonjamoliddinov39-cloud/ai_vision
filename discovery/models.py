"""Structured results returned by the Discovery Engine.

These are plain dataclasses with no behaviour so they stay trivially
serialisable across the module boundary (the API layer turns them into JSON,
other backend modules read them directly).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class PortResult:
    """Outcome of probing a single TCP port on a device."""

    port: int
    service: str  # canonical service name, e.g. "rtsp", "http", "https", "device"
    open: bool
    detail: str | None = None


@dataclass
class DeviceFingerprint:
    """Best-effort identification of the device behind an address.

    Every field is optional/best-effort: fingerprinting a remote device over a
    handful of probes is inherently uncertain, so unknowns are represented
    honestly as ``None`` / ``"unknown"`` rather than guessed.
    """

    vendor: str | None = None  # "hikvision", "dahua", "axis", ... or None
    model: str | None = None
    device_type: str = "unknown"  # "nvr_or_dvr", "ip_camera", "unknown"
    banners: dict[str, str] = field(default_factory=dict)  # service -> raw Server banner


@dataclass
class DiscoveredService:
    """A streaming/management service the operator can choose to connect to."""

    protocol: str  # display protocol, e.g. "RTSP", "HTTP", "HTTPS", "ONVIF"
    port: int
    status: str  # "available", "requires_auth", "unreachable"
    requires_auth: bool
    detail: str | None = None


@dataclass
class DiscoveryResult:
    host: str
    reachable: bool
    scanned_at: str
    fingerprint: DeviceFingerprint = field(default_factory=DeviceFingerprint)
    services: list[DiscoveredService] = field(default_factory=list)
    ports: list[PortResult] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)
