"""
cameras/camera.py

Thin wrapper around OpenCV's VideoCapture that supports:
  - USB webcams (integer index, e.g. 0, 1, 2)
  - RTSP CCTV streams (rtsp:// URL)
  - Basic reconnect logic for flaky RTSP streams

FR-1: Camera Connection
"""

from __future__ import annotations

import os
import re
import threading
import time
import cv2
import numpy as np


class Camera:
    def __init__(
        self,
        name: str,
        source,
        reconnect_delay: float = 2.0,
        slot_number: int | None = None,
    ):
        """
        Args:
            name: Human-readable camera name, e.g. "Camera 1".
            source: Either an int (webcam index) or a str (RTSP/HTTP URL).
            reconnect_delay: Seconds to wait before retrying a dropped connection.
        """
        self.name = name
        self.source = source
        self.slot_number = slot_number
        self.reconnect_delay = reconnect_delay
        self.cap: cv2.VideoCapture | None = None
        self._dummy_frame_number = 0
        self._dummy = source == "dummy"
        self._backend_index = 0
        self._backends = self._camera_backends(source)
        self._is_network_stream = isinstance(source, str) and source.lower().startswith(
            ("rtsp://", "http://", "https://")
        )
        self._frame = None
        self._frame_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._reader_thread: threading.Thread | None = None
        self._open()
        if self._is_network_stream:
            self._start_reader()

    def _open(self) -> None:
        if self._dummy:
            return

        _configure_network_video_options(self.source)
        backend_name, backend = self._backends[self._backend_index]
        if backend is None:
            self.cap = cv2.VideoCapture(self.source)
        else:
            self.cap = cv2.VideoCapture(self.source, backend)

        if not self.cap.isOpened():
            raise ConnectionError(
                f"[{self.name}] Could not open camera source: {_mask_source(self.source)!r} ({backend_name})"
            )
        if self._is_network_stream:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        print(f"[{self.name}] Opened with backend: {backend_name}")

    def read(self):
        """
        Returns a BGR frame (numpy array), or None if the frame could not
        be read after a reconnect attempt.
        """
        if self._dummy:
            return self._read_dummy_frame()

        if self._is_network_stream:
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline and not self._stop_event.is_set():
                with self._frame_lock:
                    if self._frame is not None:
                        return self._frame.copy()
                time.sleep(0.02)
            return None

        if self.cap is None or not self.cap.isOpened():
            self._try_reconnect()

        ok, frame = self.cap.read()
        if not ok:
            self._try_reconnect()
            ok, frame = self.cap.read()
            if not ok:
                return None
        return frame

    def _start_reader(self) -> None:
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            name=f"camera-reader-{self.name}",
            daemon=True,
        )
        self._reader_thread.start()

    def _reader_loop(self) -> None:
        while not self._stop_event.is_set():
            cap = self.cap
            if cap is None or not cap.isOpened():
                self._try_reconnect()
                continue

            ok, frame = cap.read()
            if ok:
                with self._frame_lock:
                    self._frame = frame
                continue

            with self._frame_lock:
                self._frame = None
            self._try_reconnect()

    def _try_reconnect(self) -> None:
        if self._stop_event.is_set():
            return
        print(f"[{self.name}] Connection lost, reconnecting...")
        if self.cap is not None:
            self.cap.release()
        if self._stop_event.wait(self.reconnect_delay):
            return

        for _ in range(len(self._backends)):
            if self._stop_event.is_set():
                return
            self._backend_index = (self._backend_index + 1) % len(self._backends)
            try:
                self._open()
                return
            except ConnectionError as e:
                print(str(e))

    def release(self) -> None:
        self._stop_event.set()
        if self.cap is not None:
            self.cap.release()
        if (
            self._reader_thread is not None
            and self._reader_thread is not threading.current_thread()
        ):
            self._reader_thread.join(timeout=2.0)

    def is_opened(self) -> bool:
        if self._dummy:
            return True
        return self.cap is not None and self.cap.isOpened()

    def _read_dummy_frame(self):
        frame = np.zeros((600, 1000, 3), dtype="uint8")
        y = min(520, 170 + self._dummy_frame_number * 5)
        cv2.rectangle(frame, (430, y), (530, y + 80), (0, 180, 0), -1)
        cv2.putText(
            frame,
            "Dummy warehouse feed",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        self._dummy_frame_number += 1
        return frame

    @staticmethod
    def _camera_backends(source) -> list[tuple[str, int | None]]:
        if isinstance(source, int) and os.name == "nt":
            return [
                ("DirectShow", cv2.CAP_DSHOW),
                ("MSMF", cv2.CAP_MSMF),
                ("Auto", None),
            ]
        if isinstance(source, str) and source.lower().startswith("rtsp://"):
            return [
                ("FFMPEG", cv2.CAP_FFMPEG),
                ("Auto", None),
            ]
        return [("Auto", None)]


def load_cameras(camera_configs: list[dict]) -> list[Camera]:
    """
    Build a list of Camera objects from config entries like:
        [{"name": "Camera 1", "source": 0}, ...]
    Cameras that fail to open are skipped with a warning so one bad
    camera doesn't take down the whole app.
    """
    cameras = []
    for entry in camera_configs:
        name = entry.get("name", "Camera")
        source = entry.get("source")
        slot_number = entry.get("slot_number")
        try:
            cameras.append(Camera(name=name, source=source, slot_number=slot_number))
            slot = f" slot={slot_number}" if slot_number is not None else ""
            print(f"[{name}] Connected{slot} (source={_mask_source(source)})")
        except ConnectionError as e:
            print(f"WARNING: {e}")
    return cameras


def _configure_network_video_options(source) -> None:
    if not isinstance(source, str) or not source.lower().startswith("rtsp://"):
        return
    # Prefer TCP for NVRs behind routers/NAT. UDP often reaches the host but
    # fails to establish a usable media stream from cloud runtimes.
    os.environ.setdefault(
        "OPENCV_FFMPEG_CAPTURE_OPTIONS",
        "rtsp_transport;tcp|stimeout;8000000|max_delay;500000|buffer_size;102400",
    )


_SECRET_URL_RE = re.compile(r"\b(?P<scheme>rtsp|https?)://(?P<username>[^:/\s]+):(?P<password>[^@\s]+)@")


def _mask_source(source) -> str:
    return _SECRET_URL_RE.sub(
        lambda match: f"{match.group('scheme')}://{match.group('username')}:****@",
        str(source),
    )
