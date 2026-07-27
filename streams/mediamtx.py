"""MediaMTX control-plane adapter for enterprise stream routing.

MediaMTX is the only component allowed to pull an upstream RTSP camera when
enterprise streaming is enabled.  AI Vision's FFmpeg worker reads the internal
MediaMTX source and publishes specialized AI/dashboard renditions back to it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class MediaRoute:
    channel_id: str
    path: str
    source_path: str
    ai_path: str
    dashboard_path: str
    source_rtsp_url: str
    ai_rtsp_url: str
    dashboard_rtsp_url: str
    webrtc_url: str
    hls_url: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MediaMTXClient:
    def __init__(
        self,
        *,
        enabled: bool | None = None,
        required: bool | None = None,
        api_url: str | None = None,
        rtsp_url: str | None = None,
        webrtc_url: str | None = None,
        hls_url: str | None = None,
        public_webrtc_url: str | None = None,
        public_hls_url: str | None = None,
        timeout_seconds: float = 3.0,
    ):
        self.enabled = _env_bool("AI_VISION_ENTERPRISE_STREAMING", False) if enabled is None else enabled
        self.required = _env_bool("MEDIAMTX_REQUIRED", self.enabled) if required is None else required
        self.api_url = (api_url or os.getenv("MEDIAMTX_API_URL", "http://mediamtx:9997")).rstrip("/")
        self.rtsp_url = (rtsp_url or os.getenv("MEDIAMTX_RTSP_URL", "rtsp://mediamtx:8554")).rstrip("/")
        self.webrtc_url = (webrtc_url or os.getenv("MEDIAMTX_WEBRTC_URL", "http://mediamtx:8889")).rstrip("/")
        self.hls_url = (hls_url or os.getenv("MEDIAMTX_HLS_URL", "http://mediamtx:8888")).rstrip("/")
        self.public_webrtc_url = (
            public_webrtc_url or os.getenv("MEDIAMTX_PUBLIC_WEBRTC_URL", self.webrtc_url)
        ).rstrip("/")
        self.public_hls_url = (
            public_hls_url or os.getenv("MEDIAMTX_PUBLIC_HLS_URL", self.hls_url)
        ).rstrip("/")
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_environment(cls) -> "MediaMTXClient":
        return cls()

    def route(self, channel_id: str) -> MediaRoute:
        safe_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(channel_id)).strip("-") or "camera"
        path = f"camera-{safe_id}"
        source_path = f"{path}-source"
        ai_path = f"{path}-ai"
        dashboard_path = f"{path}-dashboard"
        return MediaRoute(
            channel_id=str(channel_id),
            path=path,
            source_path=source_path,
            ai_path=ai_path,
            dashboard_path=dashboard_path,
            source_rtsp_url=f"{self.rtsp_url}/{source_path}",
            ai_rtsp_url=f"{self.rtsp_url}/{ai_path}",
            dashboard_rtsp_url=f"{self.rtsp_url}/{dashboard_path}",
            webrtc_url=f"{self.public_webrtc_url}/{dashboard_path}/whep",
            hls_url=f"{self.public_hls_url}/{dashboard_path}/index.m3u8",
        )

    def ensure_source(self, channel_id: str, upstream_url: str) -> MediaRoute:
        route = self.route(channel_id)
        if not self.enabled:
            return route
        payload = {
            "source": upstream_url,
            "sourceOnDemand": False,
            "record": True,
            "recordPath": f"/recordings/{safe_recording_id(channel_id)}/%Y/%m/%d/%H-%M-%S-%f",
        }
        try:
            self._request("POST", f"/v3/config/paths/add/{quote(route.source_path, safe='')}", payload)
        except HTTPError as exc:
            if exc.code != 400:
                raise
            # MediaMTX returns 400 when the named path already exists. Replace
            # its source atomically so credential/channel changes take effect.
            self._request("PATCH", f"/v3/config/paths/patch/{quote(route.source_path, safe='')}", payload)
        return route

    def remove_source(self, channel_id: str) -> None:
        if not self.enabled:
            return
        route = self.route(channel_id)
        try:
            self._request("DELETE", f"/v3/config/paths/delete/{quote(route.source_path, safe='')}")
        except HTTPError as exc:
            if exc.code != 404:
                raise

    def path_status(self, path: str) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "path": path}
        try:
            result = self._request("GET", f"/v3/paths/get/{quote(path, safe='')}")
            return {"enabled": True, "reachable": True, **(result or {})}
        except (HTTPError, URLError, TimeoutError) as exc:
            return {
                "enabled": True,
                "reachable": False,
                "path": path,
                "error": str(exc),
            }

    def health(self) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "required": self.required}
        try:
            result = self._request("GET", "/v3/paths/list")
            items = (result or {}).get("items") or []
            return {
                "enabled": True,
                "required": self.required,
                "reachable": True,
                "path_count": len(items),
            }
        except (HTTPError, URLError, TimeoutError) as exc:
            return {
                "enabled": True,
                "required": self.required,
                "reachable": False,
                "error": str(exc),
            }

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None):
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            f"{self.api_url}{path}",
            data=body,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            data = response.read()
        return json.loads(data) if data else None


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def safe_recording_id(channel_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", str(channel_id)).strip("-") or "camera"
