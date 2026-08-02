"""One-frame camera vision orchestration: detect once, then track once."""

from __future__ import annotations

import time
from typing import Any


class CameraVisionProcessor:
    def __init__(self, camera_name: str, detector, tracker=None):
        self.camera_name = camera_name
        self.detector = detector
        self.tracker = tracker

    def process(
        self, frame: Any, frame_sequence: int, observed_at: float | None = None
    ) -> list:
        detections = self.detector.detect(frame)
        if self.tracker is None:
            return detections
        return self.tracker.update(
            detections=detections,
            frame_shape=frame.shape,
            frame_sequence=frame_sequence,
            observed_at=observed_at if observed_at is not None else time.time(),
        )

    def reset(self, reason: str = "camera_reconnect") -> None:
        if self.tracker is not None:
            self.tracker.reset(reason)
