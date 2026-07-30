"""MediaMTX-backed stream manager used by the API and detector.

MediaMTX owns upstream network camera connections. AI, recording, snapshots,
and viewers consume the stable local path exposed here instead of opening the
NVR URL independently.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


_NETWORK_SOURCE_PREFIXES = ("rtsp://", "rtsps://", "http://", "https://")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _safe_path(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return normalized or "camera"


def _network_source(source: Any) -> bool:
    return isinstance(source, str) and source.lower().startswith(_NETWORK_SOURCE_PREFIXES)


@dataclass(frozen=True)
class StreamDescriptor:
    name: str
    source: Any
    slot_number: int | None
    path: str

    @classmethod
    def from_camera(cls, camera: dict[str, Any]) -> "StreamDescriptor":
        name = str(camera.get("name") or "Camera")
        slot = camera.get("slot_number")
        try:
            slot = int(slot) if slot is not None else None
        except (TypeError, ValueError):
            slot = None
        path = f"camera_{slot}" if slot is not None else _safe_path(name)
        return cls(name=name, source=camera.get("source"), slot_number=slot, path=path)


@dataclass
class MediaEngine:
    enabled: bool
    rtsp_base_url: str
    api_url: str
    hls_base_url: str
    webrtc_base_url: str
    ai_fps: float
    request_timeout: float = 2.0

    @classmethod
    def from_config(cls, config: dict[str, Any] | None) -> "MediaEngine":
        config = config or {}
        return cls(
            enabled=_env_bool("MEDIA_ENGINE_ENABLED", bool(config.get("enabled", False))),
            rtsp_base_url=os.getenv(
                "MEDIA_ENGINE_RTSP_URL", str(config.get("rtsp_url", "rtsp://127.0.0.1:8554"))
            ).rstrip("/"),
            api_url=os.getenv(
                "MEDIA_ENGINE_API_URL", str(config.get("api_url", "http://127.0.0.1:9997"))
            ).rstrip("/"),
            hls_base_url=os.getenv(
                "MEDIA_ENGINE_HLS_URL", str(config.get("hls_url", "http://127.0.0.1:8888"))
            ).rstrip("/"),
            webrtc_base_url=os.getenv(
                "MEDIA_ENGINE_WEBRTC_URL", str(config.get("webrtc_url", "http://127.0.0.1:8889"))
            ).rstrip("/"),
            ai_fps=max(0.1, float(os.getenv("MEDIA_ENGINE_AI_FPS", config.get("ai_fps", 5)))),
            request_timeout=max(
                0.1,
                float(os.getenv("MEDIA_ENGINE_TIMEOUT", config.get("request_timeout", 2))),
            ),
        )

    def consumer_source(self, camera: dict[str, Any]) -> Any:
        descriptor = StreamDescriptor.from_camera(camera)
        if not self.enabled or not _network_source(descriptor.source):
            return descriptor.source
        return f"{self.rtsp_base_url}/{descriptor.path}"

    def route_cameras(self, cameras: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        routed = []
        for camera in cameras:
            item = dict(camera)
            item["source"] = self.consumer_source(item)
            routed.append(item)
        return routed

    def sync_paths(self, cameras: Iterable[dict[str, Any]]) -> dict[str, Any]:
        """Create/update MediaMTX paths without exposing credentials in responses."""
        cameras = list(cameras)
        if not self.enabled:
            return {"enabled": False, "synced": 0, "errors": []}

        synced = 0
        errors: list[dict[str, str]] = []
        for camera in cameras:
            descriptor = StreamDescriptor.from_camera(camera)
            if not _network_source(descriptor.source):
                continue
            try:
                self._upsert_path(descriptor.path, str(descriptor.source))
                synced += 1
            except (OSError, URLError, ValueError) as exc:
                errors.append({"path": descriptor.path, "error": _safe_error(exc)})
        return {"enabled": True, "synced": synced, "errors": errors}

    def wait_until_ready(self, timeout: float = 15.0) -> bool:
        if not self.enabled:
            return True
        deadline = time.monotonic() + max(0.0, timeout)
        while time.monotonic() <= deadline:
            try:
                self._request_json("/v3/paths/list")
                return True
            except (OSError, URLError, ValueError):
                time.sleep(0.25)
        return False

    def describe(self, cameras: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.describe_camera(camera) for camera in cameras]

    def describe_camera(self, camera: dict[str, Any]) -> dict[str, Any]:
        descriptor = StreamDescriptor.from_camera(camera)
        result: dict[str, Any] = {
            "name": descriptor.name,
            "slot_number": descriptor.slot_number,
            "path": descriptor.path,
            "online": False,
            "status": "disabled" if not self.enabled else "offline",
            "fps": None,
            "resolution": None,
            "codec": None,
            "bitrate": None,
            "connection_time": None,
            "last_reconnect_time": None,
            "rtsp_url": f"{self.rtsp_base_url}/{descriptor.path}" if self.enabled else None,
            "hls_url": f"{self.hls_base_url}/{descriptor.path}/index.m3u8" if self.enabled else None,
            "webrtc_url": f"{self.webrtc_base_url}/{descriptor.path}" if self.enabled else None,
        }
        if not self.enabled:
            return result

        try:
            payload = self._request_json(f"/v3/paths/get/{quote(descriptor.path, safe='')}")
        except (OSError, URLError, ValueError):
            return result

        result["online"] = self._is_ready(payload)
        result["status"] = "online" if result["online"] else "offline"
        result.update(_media_metrics(payload))
        return result

    def _upsert_path(self, path: str, source: str) -> None:
        payload = {
            "source": source,
            "sourceOnDemand": False,
            "record": _env_bool("MEDIA_ENGINE_RECORD", False),
        }
        encoded_path = quote(path, safe="")
        try:
            self._request_json(
                f"/v3/config/paths/patch/{encoded_path}", method="PATCH", payload=payload
            )
        except HTTPError as exc:
            if exc.code != 404:
                raise
            self._request_json(
                f"/v3/config/paths/add/{encoded_path}", method="POST", payload=payload
            )

    def _request_json(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            f"{self.api_url}{path}",
            data=body,
            method=method,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        with urlopen(request, timeout=self.request_timeout) as response:
            raw = response.read()
        if not raw:
            return {}
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("MediaMTX returned a non-object response")
        return data

    @staticmethod
    def _is_ready(payload: dict[str, Any]) -> bool:
        for key in ("ready", "sourceReady", "running"):
            if key in payload:
                return bool(payload[key])
        return bool(payload.get("source") or payload.get("publisher") or payload.get("tracks"))


class FrameRateLimiter:
    """Non-blocking per-stream limiter for expensive AI inference."""

    def __init__(self, fps: float):
        self.interval = 1.0 / max(0.1, float(fps))
        self._next_at: dict[str, float] = {}

    def ready(self, stream: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        if now < self._next_at.get(stream, 0.0):
            return False
        self._next_at[stream] = now + self.interval
        return True


def _safe_error(exc: BaseException) -> str:
    text = str(exc)
    text = re.sub(
        r"\b(?P<scheme>rtsp|rtsps|https?)://(?P<username>[^:/\s]+):(?P<password>[^@\s]+)@",
        r"\g<scheme>://\g<username>:****@",
        text,
        flags=re.IGNORECASE,
    )
    return text[:300]


def _media_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    tracks = payload.get("tracks")
    tracks = tracks if isinstance(tracks, list) else []
    first_track = next((track for track in tracks if isinstance(track, dict)), {})
    video_track = next(
        (
            track
            for track in tracks
            if isinstance(track, dict)
            and str(track.get("type") or track.get("media") or "").lower() == "video"
        ),
        first_track,
    )
    width = video_track.get("width") or payload.get("width")
    height = video_track.get("height") or payload.get("height")
    return {
        "fps": video_track.get("fps") or payload.get("fps"),
        "resolution": f"{width}x{height}" if width and height else None,
        "codec": video_track.get("codec") or payload.get("codec"),
        "bitrate": video_track.get("bitrate") or payload.get("bitrate"),
        "connection_time": payload.get("sourceReadySince") or payload.get("created"),
        "last_reconnect_time": payload.get("lastReconnectTime")
        or payload.get("sourceReadySince"),
    }
