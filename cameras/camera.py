"""
cameras/camera.py

Thin wrapper around OpenCV's VideoCapture that supports:
  - USB webcams (integer index, e.g. 0, 1, 2)
  - RTSP CCTV streams (rtsp:// URL)
  - Basic reconnect logic for flaky RTSP streams

FR-1: Camera Connection
"""

from __future__ import annotations

import time
import cv2


class Camera:
    def __init__(self, name: str, source, reconnect_delay: float = 2.0):
        """
        Args:
            name: Human-readable camera name, e.g. "Camera 1".
            source: Either an int (webcam index) or a str (RTSP/HTTP URL).
            reconnect_delay: Seconds to wait before retrying a dropped connection.
        """
        self.name = name
        self.source = source
        self.reconnect_delay = reconnect_delay
        self.cap: cv2.VideoCapture | None = None
        self._open()

    def _open(self) -> None:
        self.cap = cv2.VideoCapture(self.source)
        if not self.cap.isOpened():
            raise ConnectionError(
                f"[{self.name}] Could not open camera source: {self.source!r}"
            )

    def read(self):
        """
        Returns a BGR frame (numpy array), or None if the frame could not
        be read after a reconnect attempt.
        """
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
        try:
            self._open()
        except ConnectionError as e:
            print(str(e))

    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()

    def is_opened(self) -> bool:
        return self.cap is not None and self.cap.isOpened()


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
        try:
            cameras.append(Camera(name=name, source=source))
            print(f"[{name}] Connected (source={source})")
        except ConnectionError as e:
            print(f"WARNING: {e}")
    return cameras
