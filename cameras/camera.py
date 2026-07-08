"""
cameras/camera.py

Thin wrapper around OpenCV's VideoCapture that supports:
  - USB webcams (integer index, e.g. 0, 1, 2)
  - RTSP CCTV streams (rtsp:// URL)
  - Basic reconnect logic for flaky RTSP streams
  - Latest-frame grabbing: a background thread continuously drains the
    capture so `read()` always returns the *newest* frame instead of the
    oldest buffered one. Without this, when YOLO inference runs slower
    than the camera's FPS, OpenCV's internal buffer fills with stale
    frames and the live view lags further and further behind reality.

FR-1: Camera Connection
"""

from __future__ import annotations

import threading
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

        self._lock = threading.Lock()
        self._latest_frame = None
        self._stopped = False

        self._open()

        self._grab_thread = threading.Thread(
            target=self._grab_loop, name=f"grab-{name}", daemon=True
        )
        self._grab_thread.start()

    def _open(self) -> None:
        self.cap = cv2.VideoCapture(self.source)
        # Keep the driver-side buffer as small as the backend allows so a
        # slow consumer can't accumulate seconds of latency.
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not self.cap.isOpened():
            raise ConnectionError(
                f"[{self.name}] Could not open camera source: {self.source!r}"
            )

    def _grab_loop(self) -> None:
        """Continuously pull frames as fast as the camera produces them,
        keeping only the most recent one."""
        while not self._stopped:
            cap = self.cap
            if cap is None or not cap.isOpened():
                self._try_reconnect()
                continue

            ok, frame = cap.read()
            if not ok:
                self._try_reconnect()
                continue

            with self._lock:
                self._latest_frame = frame

    def read(self):
        """
        Returns the newest BGR frame (numpy array), or None if no frame
        has arrived yet / the stream is down. Never blocks on the camera.
        """
        with self._lock:
            frame = self._latest_frame
            # Hand each frame out only once so a stalled stream doesn't get
            # re-processed as if it were live footage.
            self._latest_frame = None
        return frame

    def _try_reconnect(self) -> None:
        if self._stopped:
            return
        print(f"[{self.name}] Connection lost, reconnecting...")
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        time.sleep(self.reconnect_delay)
        if self._stopped:
            return
        try:
            self._open()
        except ConnectionError as e:
            print(str(e))

    def release(self) -> None:
        self._stopped = True
        if self._grab_thread.is_alive():
            self._grab_thread.join(timeout=2)
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
