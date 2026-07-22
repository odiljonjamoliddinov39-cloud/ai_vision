"""Frame providers for analytics consumers.

The detector process uses these lightweight camera-like objects so YOLO reads
frames already published by the Stream Manager instead of opening RTSP itself.
"""

from __future__ import annotations

from pathlib import Path
import time

import cv2
import numpy as np


class StreamFrameCamera:
    def __init__(self, name: str, slot_number: int | None, source: str, snapshot_dir: str = "snapshots"):
        self.name = name
        self.slot_number = slot_number
        self.source = source
        self.snapshot_dir = Path(snapshot_dir)
        self._dummy_frame_number = 0
        self._last_mtime = 0.0

    def read(self):
        if str(self.source).strip().lower() == "dummy":
            return self._read_dummy_frame()

        if self.slot_number is None:
            return None

        path = self.snapshot_dir / f"latest_stream_slot_{self.slot_number}.jpg"
        fallback = self.snapshot_dir / f"latest_slot_{self.slot_number}.jpg"
        if not path.exists() and fallback.exists():
            path = fallback
        if not path.exists():
            time.sleep(0.05)
            return None

        try:
            current_mtime = path.stat().st_mtime
            if current_mtime <= self._last_mtime:
                time.sleep(0.02)
                return None
            data = path.read_bytes()
        except OSError:
            return None
        if not (data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9")):
            return None

        frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is not None:
            self._last_mtime = current_mtime
        return frame

    def release(self) -> None:
        return None

    def is_opened(self) -> bool:
        return True

    def _read_dummy_frame(self):
        frame = np.zeros((600, 1000, 3), dtype="uint8")
        y = min(520, 170 + self._dummy_frame_number * 5)
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
        self._dummy_frame_number += 1
        return frame


def load_processing_cameras(camera_configs: list[dict], snapshot_dir: str = "snapshots") -> list[StreamFrameCamera]:
    cameras: list[StreamFrameCamera] = []
    for entry in camera_configs:
        cameras.append(
            StreamFrameCamera(
                name=entry.get("name", "Camera"),
                slot_number=entry.get("slot_number"),
                source=str(entry.get("source", "")),
                snapshot_dir=snapshot_dir,
            )
        )
    return cameras
