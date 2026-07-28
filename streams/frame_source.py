"""Frame providers for analytics consumers.

The detector process uses these lightweight camera-like objects so YOLO reads
frames already published by the Stream Manager instead of opening RTSP itself.
"""

from __future__ import annotations

import time

import cv2
import numpy as np

from streams.shared_buffer import SharedFrameReader


class StreamFrameCamera:
    def __init__(self, name: str, slot_number: int | None, source: str, snapshot_dir: str = "snapshots"):
        self.name = name
        self.slot_number = slot_number
        self.source = source
        self.snapshot_dir = snapshot_dir
        self._dummy_frame_number = 0
        self._last_sequence = 0
        self._reader = (
            SharedFrameReader(snapshot_dir, slot_number)
            if slot_number is not None
            else None
        )

    def read(self):
        if str(self.source).strip().lower() == "dummy":
            return self._read_dummy_frame()

        if self.slot_number is None:
            return None

        if self._reader is None:
            time.sleep(0.05)
            return None

        snapshot = self._reader.read(after_sequence=self._last_sequence)
        if snapshot is None:
            time.sleep(0.02)
            return None

        sequence, data = snapshot
        frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is not None:
            self._last_sequence = sequence
        return frame

    def release(self) -> None:
        if self._reader is not None:
            self._reader.close()

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
