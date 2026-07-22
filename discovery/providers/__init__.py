"""Stream-enumeration providers.

A provider turns a *discovered service* (e.g. "RTSP on 554 of a Hikvision
device") plus optional credentials into concrete, connectable channels -
without the operator ever typing a stream path. Providers are tried in
priority order; the first that supports the device wins.

Adding support for a new vendor/protocol is implementing one more
:class:`StreamProvider` and listing it in ``_PROVIDERS`` - no change to the
core discovery flow, per the migration spec's extensibility requirement.
"""

from __future__ import annotations

from discovery.providers.base import (
    EnumerationResult,
    StreamChannel,
    StreamCredentials,
    StreamProvider,
)
from discovery.providers.onvif_provider import OnvifStreamProvider
from discovery.providers.vendor import (
    DahuaStreamProvider,
    GenericRtspStreamProvider,
    HikvisionStreamProvider,
)

# Priority order: ONVIF asks the device for its real profiles (most accurate,
# vendor-agnostic) and is preferred when available; vendor template providers
# handle known devices when ONVIF is off; the generic provider is the last
# resort so a reachable RTSP service is never left unconnectable.
_PROVIDERS: list[StreamProvider] = [
    OnvifStreamProvider(),
    HikvisionStreamProvider(),
    DahuaStreamProvider(),
    GenericRtspStreamProvider(),
]


def select_provider(vendor: str | None, protocol: str) -> StreamProvider | None:
    for provider in _PROVIDERS:
        if provider.supports(vendor=vendor, protocol=protocol):
            return provider
    return None


def enumerate_streams(
    host: str,
    port: int,
    protocol: str,
    credentials: StreamCredentials | None,
    vendor: str | None,
    channel_count: int,
) -> EnumerationResult:
    """Try each supporting provider in priority order, falling through on
    failure so ONVIF is preferred but a vendor/generic provider still connects
    the device when ONVIF is unavailable or errors. A provider that needs
    credentials short-circuits (so the UI can prompt) rather than falling
    through to a provider that would silently produce an unauthenticated URL.
    """
    last: EnumerationResult | None = None
    for provider in _PROVIDERS:
        if not provider.supports(vendor=vendor, protocol=protocol):
            continue
        result = provider.enumerate(
            host=host,
            port=port,
            protocol=protocol,
            credentials=credentials,
            channel_count=channel_count,
        )
        if result.channels:
            return result
        if result.requires_auth:
            return result
        last = result
    if last is not None:
        return last
    return EnumerationResult(
        provider="none",
        channels=[],
        error=f"No stream provider can handle a {protocol.upper()} service on this device.",
    )


__all__ = [
    "StreamProvider",
    "StreamChannel",
    "StreamCredentials",
    "EnumerationResult",
    "select_provider",
    "enumerate_streams",
]
