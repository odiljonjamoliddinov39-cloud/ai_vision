"""Stream Manager.

Owns upstream video connections independently from the AI detector process.
The dashboard reads clean JPEG frames from this layer, while analytics workers
consume the same published frames instead of reconnecting to the camera/NVR.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
import os
import re
import shutil
import subprocess
import threading
import time
from typing import Any

import cv2
import numpy as np


@dataclass(frozen=True)
class StreamSessionConfig:
    channel_id: str
    name: str
    source: str
    slot_number: int | None = None
    snapshot_dir: str | Path = "snapshots"
    width: int = 360
    jpeg_quality: int = 30
    preview_fps: float = 2.0


@dataclass
class StreamSessionStatus:
    channel_id: str
    name: str
    slot_number: int | None
    status: str = "starting"
    codec: str | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    last_frame_at: str | None = None
    reconnect_count: int = 0
    last_error: str | None = None
    started_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class StreamManager:
    def __init__(self, snapshot_dir: str | Path = "snapshots"):
        self.snapshot_dir = Path(snapshot_dir)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, _ManagedStreamSession] = {}
        self._aliases: dict[str, _ManagedStreamSession] = {}
        self._lock = threading.Lock()

    def start(self, config: StreamSessionConfig) -> dict[str, Any]:
        with self._lock:
            channel_id = str(config.channel_id)
            existing = self._sessions.get(channel_id) or self._aliases.get(channel_id)
            if existing and existing.same_source(config):
                existing.add_alias(config)
                return existing.status(config)
            if existing:
                self._remove_alias(channel_id)
                if self._sessions.get(channel_id) is existing:
                    existing.stop()
                    self._sessions.pop(channel_id, None)

            shared = self._find_same_source(config)
            if shared is not None:
                shared.add_alias(config)
                self._aliases[channel_id] = shared
                return shared.status(config)

            session = _ManagedStreamSession(config)
            self._sessions[channel_id] = session
            session.start()
            return session.status()

    def stop(self, channel_id: str) -> bool:
        with self._lock:
            channel_id = str(channel_id)
            alias = self._aliases.pop(channel_id, None)
            if alias is not None:
                alias.remove_alias(channel_id)
                return True
            session = self._sessions.pop(channel_id, None)
            if session is not None:
                self._aliases = {
                    alias_id: alias_session
                    for alias_id, alias_session in self._aliases.items()
                    if alias_session is not session
                }
        if session is None:
            return False
        session.stop()
        return True

    def stop_all(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
            self._aliases.clear()
        for session in sessions:
            session.stop()

    def status(self, channel_id: str | None = None) -> dict[str, Any]:
        with self._lock:
            if channel_id is not None:
                channel_id = str(channel_id)
                session = self._sessions.get(channel_id) or self._aliases.get(channel_id)
                return session.status_for_channel(channel_id) if session else {"channel_id": channel_id, "status": "offline"}
            streams = []
            for session in self._sessions.values():
                streams.append(session.status())
                streams.extend(session.alias_statuses())
            return {"streams": streams, "upstream_count": len(self._sessions)}

    def latest_frame_bytes(
        self,
        channel_id: str | None = None,
        slot_number: int | None = None,
        name: str | None = None,
    ) -> bytes | None:
        with self._lock:
            session = None
            if channel_id is not None:
                channel_id = str(channel_id)
                session = self._sessions.get(channel_id) or self._aliases.get(channel_id)
            if session is None:
                for candidate in self._sessions.values():
                    if candidate.matches(slot_number=slot_number, name=name):
                        session = candidate
                        break
        return session.latest_frame_bytes() if session is not None else None

    def ensure_from_cameras(self, cameras: list[dict[str, Any]]) -> dict[str, Any]:
        seen: set[str] = set()
        statuses = []
        for camera in cameras:
            if not camera.get("is_active"):
                continue
            channel_id = str(camera.get("id") or camera.get("slot_number") or camera.get("name"))
            seen.add(channel_id)
            statuses.append(
                self.start(
                    StreamSessionConfig(
                        channel_id=channel_id,
                        name=str(camera.get("name") or f"Camera {channel_id}"),
                        source=str(camera.get("stream_url") or camera.get("source") or ""),
                        slot_number=camera.get("slot_number"),
                        snapshot_dir=self.snapshot_dir,
                    )
                )
            )

        with self._lock:
            stale = [channel_id for channel_id in self._sessions if channel_id not in seen]
            stale_aliases = [channel_id for channel_id in self._aliases if channel_id not in seen]
        for channel_id in stale_aliases:
            self.stop(channel_id)
        for channel_id in stale:
            self.stop(channel_id)
        return {"streams": statuses}

    def _find_same_source(self, config: StreamSessionConfig) -> _ManagedStreamSession | None:
        for session in self._sessions.values():
            if session.same_source(config):
                return session
        return None

    def _remove_alias(self, channel_id: str) -> None:
        alias = self._aliases.pop(channel_id, None)
        if alias is not None:
            alias.remove_alias(channel_id)


class _ManagedStreamSession:
    def __init__(self, config: StreamSessionConfig):
        self.config = config
        self.status_data = StreamSessionStatus(
            channel_id=str(config.channel_id),
            name=config.name,
            slot_number=config.slot_number,
        )
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._process: subprocess.Popen | None = None
        self._warning_log = _RateLimitedWarnings()
        self._latest_jpeg: bytes | None = None
        self._latest_lock = threading.Lock()
        self._aliases: dict[str, StreamSessionConfig] = {}

    def same_source(self, config: StreamSessionConfig) -> bool:
        if self._thread is None or not self._thread.is_alive():
            return False
        if str(self.config.channel_id) == str(config.channel_id):
            return self.config.source == config.source
        source = str(self.config.source).strip()
        return bool(source and source.lower() != "dummy" and source == str(config.source).strip())

    def add_alias(self, config: StreamSessionConfig) -> None:
        self._aliases[str(config.channel_id)] = config
        data = self.latest_frame_bytes()
        if data is not None:
            self._write_frame_files(config.name, config.slot_number, data)

    def remove_alias(self, channel_id: str) -> None:
        self._aliases.pop(str(channel_id), None)

    def matches(self, slot_number: int | None = None, name: str | None = None) -> bool:
        names_and_slots = [(self.config.name, self.config.slot_number)]
        names_and_slots.extend((config.name, config.slot_number) for config in self._aliases.values())
        return any(
            (slot_number is not None and slot == slot_number)
            or (name is not None and candidate_name == name)
            for candidate_name, slot in names_and_slots
        )

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run,
            name=f"stream-manager-{self.config.channel_id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._terminate_process()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=2.0)
        self.status_data.status = "offline"

    def status_for_channel(self, channel_id: str) -> dict[str, Any]:
        config = self._aliases.get(str(channel_id))
        if config is None and str(self.config.channel_id) != str(channel_id):
            return {"channel_id": str(channel_id), "status": "offline"}
        return self.status(config)

    def alias_statuses(self) -> list[dict[str, Any]]:
        return [self.status(config) for config in self._aliases.values()]

    def latest_frame_bytes(self) -> bytes | None:
        with self._latest_lock:
            return bytes(self._latest_jpeg) if self._latest_jpeg is not None else None

    def status(self, config: StreamSessionConfig | None = None) -> dict[str, Any]:
        status = self.status_data.to_dict()
        if config is not None:
            status["channel_id"] = str(config.channel_id)
            status["name"] = config.name
            status["slot_number"] = config.slot_number
        status["shared_source"] = bool(self._aliases)
        return status

    def _run(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                self.status_data.status = "starting"
                if self.config.source.strip().lower() == "dummy":
                    self._run_dummy()
                elif self.config.source.lower().startswith("rtsp://"):
                    self._run_ffmpeg()
                else:
                    self._run_opencv()
                backoff = 1.0
            except Exception as exc:
                self.status_data.status = "reconnecting"
                self.status_data.last_error = _mask_source(str(exc))
                self.status_data.reconnect_count += 1
                delay = min(backoff, 30.0)
                backoff = min(backoff * 2.0, 30.0)
                if self._stop.wait(delay):
                    break

    def _run_dummy(self) -> None:
        frame_number = 0
        while not self._stop.is_set():
            frame = np.zeros((600, 1000, 3), dtype="uint8")
            y = min(520, 170 + frame_number * 5)
            cv2.rectangle(frame, (430, y), (530, y + 80), (0, 180, 0), -1)
            cv2.putText(
                frame,
                "Stream Manager demo feed",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
            self._publish(frame)
            frame_number += 1
            time.sleep(0.2)

    def _run_opencv(self) -> None:
        source: int | str = int(self.config.source) if self.config.source.isdigit() else self.config.source
        cap = cv2.VideoCapture(source)
        try:
            if not cap.isOpened():
                raise ConnectionError(f"could not open stream {_mask_source(self.config.source)}")
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    raise ConnectionError("stream stopped returning frames")
                self._publish(frame)
        finally:
            cap.release()

    def _run_ffmpeg(self) -> None:
        process = subprocess.Popen(
            _ffmpeg_command(
                self.config.source,
                width=self.config.width,
                jpeg_quality=self.config.jpeg_quality,
                fps=self.config.preview_fps,
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._process = process
        threading.Thread(
            target=self._drain_stderr,
            args=(process,),
            name=f"stream-manager-log-{self.config.channel_id}",
            daemon=True,
        ).start()

        buffer = b""
        try:
            while not self._stop.is_set():
                if process.poll() is not None or process.stdout is None:
                    raise ConnectionError(f"ffmpeg exited with code {process.returncode}")
                chunk = process.stdout.read(65536)
                if not chunk:
                    raise ConnectionError("ffmpeg stream returned no data")
                buffer += chunk
                start = buffer.find(b"\xff\xd8")
                end = buffer.find(b"\xff\xd9", start + 2) if start != -1 else -1
                while start != -1 and end != -1:
                    jpeg = buffer[start : end + 2]
                    self._publish_jpeg(jpeg)
                    buffer = buffer[end + 2 :]
                    start = buffer.find(b"\xff\xd8")
                    end = buffer.find(b"\xff\xd9", start + 2) if start != -1 else -1
        finally:
            self._terminate_process()

    def _drain_stderr(self, process: subprocess.Popen) -> None:
        stderr = getattr(process, "stderr", None)
        if stderr is None:
            return
        for line in iter(stderr.readline, b""):
            if self._stop.is_set():
                break
            text = line.decode("utf-8", errors="replace").strip()
            if not text or _is_benign_ffmpeg_noise(text):
                continue
            if self._warning_log.should_log(text):
                print(f"[stream:{self.config.name}] ffmpeg: {_mask_source(text)}")

    def _terminate_process(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        try:
            process.terminate()
            process.wait(timeout=2.0)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    def _publish(self, frame) -> None:
        frame_height, frame_width = frame.shape[:2]
        output = frame
        width = max(240, min(int(self.config.width), 1280))
        if frame_width > width:
            height = max(1, int(frame_height * (width / frame_width)))
            output = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
        quality = max(20, min(int(self.config.jpeg_quality), 90))
        ok, jpg = cv2.imencode(".jpg", output, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        if not ok:
            return
        data = jpg.tobytes()

        self.status_data.status = "online"
        self.status_data.width = frame_width
        self.status_data.height = frame_height
        self.status_data.last_frame_at = datetime.now().isoformat(timespec="seconds")
        self.status_data.last_error = None

        self._publish_jpeg_data(data)

    def _publish_jpeg(self, data: bytes) -> None:
        if not (data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9")):
            return

        self.status_data.status = "online"
        self.status_data.width = max(240, min(int(self.config.width), 1280))
        self.status_data.height = None
        self.status_data.fps = float(self.config.preview_fps)
        self.status_data.last_frame_at = datetime.now().isoformat(timespec="seconds")
        self.status_data.last_error = None

        self._publish_jpeg_data(data)

    def _publish_jpeg_data(self, data: bytes) -> None:
        with self._latest_lock:
            self._latest_jpeg = data
        self._write_frame_files(self.config.name, self.config.slot_number, data)
        for alias in list(self._aliases.values()):
            self._write_frame_files(alias.name, alias.slot_number, data)

    def _write_frame_files(self, name: str, slot_number: int | None, data: bytes) -> None:
        safe_name = _safe_name(name)
        self._write_atomic(self.config.snapshot_dir / f"latest_stream_{safe_name}.jpg", data)
        if slot_number is not None:
            self._write_atomic(self.config.snapshot_dir / f"latest_stream_slot_{slot_number}.jpg", data)
            self._write_atomic(self.config.snapshot_dir / f"latest_slot_{slot_number}.jpg", data)

    @staticmethod
    def _write_atomic(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        tmp.write_bytes(data)
        tmp.replace(path)


class _RateLimitedWarnings:
    def __init__(self, interval_seconds: float = 30.0):
        self.interval_seconds = interval_seconds
        self._last: dict[str, float] = {}

    def should_log(self, text: str) -> bool:
        key = text[:160]
        now = time.monotonic()
        last = self._last.get(key, 0.0)
        if now - last < self.interval_seconds:
            return False
        self._last[key] = now
        return True


def _ffmpeg_command(source: str, width: int = 360, jpeg_quality: int = 30, fps: float = 2.0) -> list[str]:
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    preview_width = max(240, min(int(width), 1280))
    preview_fps = max(1.0, min(float(fps), 10.0))
    # OpenCV JPEG quality is 0..100, while ffmpeg's mjpeg qscale is roughly
    # 2(best)..31(worst). Keep previews small enough for 20+ camera grids.
    qscale = max(4, min(18, round((100 - max(20, min(int(jpeg_quality), 90))) / 4)))
    return [
        ffmpeg,
        "-rtsp_transport",
        "tcp",
        "-probesize",
        "32768",
        "-analyzeduration",
        "0",
        "-skip_frame",
        "nokey",
        "-fflags",
        "+nobuffer+discardcorrupt",
        "-flags",
        "low_delay",
        "-i",
        source,
        "-vf",
        f"fps={preview_fps:g},scale={preview_width}:-2",
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "-q:v",
        str(qscale),
        "-an",
        "-threads",
        "1",
        "-loglevel",
        "error",
        "-",
    ]


_BENIGN_FFMPEG_MARKERS = (
    "PPS changed between slices",
    "PPS id out of range",
    "Could not find ref with POC",
    "error while decoding MB",
    "bad cseq",
    "Last message repeated",
    "non-existing PPS",
    "decode_slice_header error",
    "mmco: unref short failure",
    "illegal short term buffer",
    "concealing",
    "no frame!",
    "corrupt decoded frame",
    "left block unavailable",
    "error while decoding",
)


def _is_benign_ffmpeg_noise(text: str) -> bool:
    return any(marker in text for marker in _BENIGN_FFMPEG_MARKERS)


_SECRET_URL_RE = re.compile(r"\b(?P<scheme>rtsp|https?)://(?P<username>[^:/\s]+):(?P<password>[^@\s]+)@")


def _mask_source(source: str) -> str:
    return _SECRET_URL_RE.sub(
        lambda match: f"{match.group('scheme')}://{match.group('username')}:****@",
        str(source),
    )


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(value)).strip("_") or "camera"
