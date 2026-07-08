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
        self._open()

    def _open(self) -> None:
        if self._dummy:
            return

        backend_name, backend = self._backends[self._backend_index]
        if backend is None:
            self.cap = cv2.VideoCapture(self.source)
        else:
            self.cap = cv2.VideoCapture(self.source, backend)

        if not self.cap.isOpened():
            raise ConnectionError(
                f"[{self.name}] Could not open camera source: {_mask_source(self.source)!r} ({backend_name})"
            )
        print(f"[{self.name}] Opened with backend: {backend_name}")

    def read(self):
        """
        Returns a BGR frame (numpy array), or None if the frame could not
        be read after a reconnect attempt.
        """
        if self._dummy:
            return self._read_dummy_frame()

        if self.cap is None or not self.cap.isOpened():
            self._try_reconnect()

        ok, frame = self.cap.read()
        if not ok:
            self._try_reconnect()
            ok, frame = self.cap.read()
            if not ok:
                return None
        return frame

    def _try_reconnect(self) -> None:
        print(f"[{self.name}] Connection lost, reconnecting...")
        if self.cap is not None:
            self.cap.release()
        time.sleep(self.reconnect_delay)

        for _ in range(len(self._backends)):
            self._backend_index = (self._backend_index + 1) % len(self._backends)
            try:
                self._open()
                return
            except ConnectionError as e:
                print(str(e))

    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()

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


_SECRET_URL_RE = re.compile(r"\b(?P<scheme>rtsp|https?)://(?P<username>[^:/\s]+):(?P<password>[^@\s]+)@")


def _mask_source(source) -> str:
    return _SECRET_URL_RE.sub(
        lambda match: f"{match.group('scheme')}://{match.group('username')}:****@",
        str(source),
    )
