"""Vendor stream-path template providers.

When ONVIF isn't available, these build a vendor's well-known RTSP stream URLs
for channels 1..N so the operator still never has to know the path. They are
pattern-based by design: they encode the vendor's documented URL scheme rather
than querying the device, which is why ONVIF is preferred when present.
"""

from __future__ import annotations

from discovery.providers.base import (
    EnumerationResult,
    StreamChannel,
    StreamCredentials,
    StreamProvider,
)

_DEFAULT_RTSP_PORT = 554


class _TemplateStreamProvider(StreamProvider):
    """Builds channel URLs from a ``{userinfo}``/``{host}``/``{port}``/``{channel}`` template."""

    name = "template"
    template = ""  # subclasses set this
    vendors: tuple[str, ...] = ()
    default_channels = 1

    def supports(self, vendor: str | None, protocol: str) -> bool:
        if protocol.lower() != "rtsp":
            return False
        return vendor in self.vendors

    def enumerate(
        self,
        host: str,
        port: int,
        protocol: str,
        credentials: StreamCredentials | None,
        channel_count: int,
    ) -> EnumerationResult:
        creds = credentials or StreamCredentials()
        userinfo = creds.userinfo()
        rtsp_port = port or _DEFAULT_RTSP_PORT
        count = channel_count if channel_count and channel_count > 0 else self.default_channels
        channels: list[StreamChannel] = []
        for channel in range(1, count + 1):
            url = self.template.format(
                userinfo=userinfo, host=host, port=rtsp_port, channel=channel
            )
            channels.append(
                StreamChannel(
                    channel=channel,
                    stream_url=url,
                    name=f"Channel {channel}",
                    description=f"{self.name} channel {channel}",
                )
            )
        return EnumerationResult(provider=self.name, channels=channels)


class HikvisionStreamProvider(_TemplateStreamProvider):
    # channel 1 -> /Streaming/Channels/101 (main stream). Matches the path
    # confirmed working against the real NVR earlier.
    name = "hikvision"
    vendors = ("hikvision",)
    template = "rtsp://{userinfo}{host}:{port}/Streaming/Channels/{channel}01"


class DahuaStreamProvider(_TemplateStreamProvider):
    name = "dahua"
    vendors = ("dahua",)
    template = "rtsp://{userinfo}{host}:{port}/cam/realmonitor?channel={channel}&subtype=0"


class GenericRtspStreamProvider(StreamProvider):
    """Last-resort provider: a single stream at the RTSP root.

    Supports any RTSP service (unknown/None vendor included) so a reachable
    RTSP endpoint is never left unconnectable, even if we can't identify it.
    """

    name = "generic-rtsp"

    def supports(self, vendor: str | None, protocol: str) -> bool:
        return protocol.lower() == "rtsp"

    def enumerate(
        self,
        host: str,
        port: int,
        protocol: str,
        credentials: StreamCredentials | None,
        channel_count: int,
    ) -> EnumerationResult:
        creds = credentials or StreamCredentials()
        rtsp_port = port or _DEFAULT_RTSP_PORT
        url = f"rtsp://{creds.userinfo()}{host}:{rtsp_port}/"
        return EnumerationResult(
            provider=self.name,
            channels=[
                StreamChannel(channel=1, stream_url=url, name="Stream", description="RTSP root stream")
            ],
        )
