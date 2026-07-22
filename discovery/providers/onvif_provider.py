"""ONVIF stream provider (preferred when available).

ONVIF lets us ask the device for its *actual* media profiles and stream URIs
instead of guessing a vendor path - the truest form of "the operator never
needs to know stream paths". It is intentionally decoupled from a hard
dependency: the ONVIF client is imported lazily, and when the library isn't
installed (or the device doesn't speak ONVIF) this provider reports itself
unavailable and the orchestrator falls through to the vendor template
providers. That keeps a missing/broken optional dependency from ever taking
down discovery or the deploy.

Enabling ONVIF in production is a deliberate follow-up: the client library must
first be confirmed to build cleanly in the runtime image so it can be added to
requirements without risking the whole build.
"""

from __future__ import annotations

from discovery.providers.base import (
    EnumerationResult,
    StreamChannel,
    StreamCredentials,
    StreamProvider,
)

# Ports an ONVIF device service commonly listens on, tried in order.
_ONVIF_PORTS = (80, 8000, 8080)


def _onvif_available() -> bool:
    try:
        import onvif  # noqa: F401  (optional dependency, imported lazily)

        return True
    except Exception:
        return False


class OnvifStreamProvider(StreamProvider):
    name = "onvif"

    def supports(self, vendor: str | None, protocol: str) -> bool:
        # Preferred whenever the client is installed; produces RTSP stream URIs.
        return _onvif_available()

    def enumerate(
        self,
        host: str,
        port: int,
        protocol: str,
        credentials: StreamCredentials | None,
        channel_count: int,
    ) -> EnumerationResult:
        if not _onvif_available():
            return EnumerationResult(provider=self.name, error="ONVIF client is not installed.")

        try:  # pragma: no cover - exercised only where the ONVIF lib is present
            from onvif import ONVIFCamera
        except Exception as exc:  # pragma: no cover
            return EnumerationResult(provider=self.name, error=f"ONVIF import failed: {exc}")

        creds = credentials or StreamCredentials()
        last_error: str | None = None
        for onvif_port in _ONVIF_PORTS:  # pragma: no cover - needs a real device
            try:
                camera = ONVIFCamera(host, onvif_port, creds.username, creds.password)
                media = camera.create_media_service()
                profiles = media.GetProfiles()
                channels: list[StreamChannel] = []
                for index, profile in enumerate(profiles, start=1):
                    request = media.create_type("GetStreamUri")
                    request.ProfileToken = profile.token
                    request.StreamSetup = {
                        "Stream": "RTP-Unicast",
                        "Transport": {"Protocol": "RTSP"},
                    }
                    uri = media.GetStreamUri(request).Uri
                    channels.append(
                        StreamChannel(
                            channel=index,
                            stream_url=_inject_credentials(uri, creds),
                            name=getattr(profile, "Name", None) or f"Channel {index}",
                            description="ONVIF media profile",
                        )
                    )
                if channels:
                    return EnumerationResult(provider=self.name, channels=channels)
                last_error = "ONVIF returned no media profiles."
            except Exception as exc:  # try next port, then give up to fallback
                message = str(exc).lower()
                if "auth" in message or "401" in message or "unauthorized" in message:
                    return EnumerationResult(provider=self.name, requires_auth=True, error="ONVIF authentication required.")
                last_error = str(exc)

        return EnumerationResult(provider=self.name, error=last_error or "ONVIF enumeration failed.")


def _inject_credentials(uri: str, creds: StreamCredentials) -> str:
    """Embed credentials into an ONVIF-returned rtsp:// URI that lacks them."""
    userinfo = creds.userinfo()
    if not userinfo or "://" not in uri:
        return uri
    scheme, _, rest = uri.partition("://")
    if "@" in rest.split("/", 1)[0]:  # already has userinfo
        return uri
    return f"{scheme}://{userinfo}{rest}"
