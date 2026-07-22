"""
AI Vision Discovery Engine.

A device-first connection layer: the operator provides only an IP address or
hostname, and the engine determines what the device is and which streaming
services it exposes - without the operator ever supplying an RTSP URL, stream
path, connection type, or vendor.

The engine is deliberately isolated from the AI processing, stream
acquisition, and database layers. It only answers "what is at this address and
how can it be reached"; other modules decide what to do with that answer.

Public surface:
    from discovery import discover_device, DiscoveryResult
"""

from discovery.engine import discover_device
from discovery.models import (
    DeviceFingerprint,
    DiscoveredService,
    DiscoveryResult,
    PortResult,
)

__all__ = [
    "discover_device",
    "DiscoveryResult",
    "DiscoveredService",
    "DeviceFingerprint",
    "PortResult",
]
