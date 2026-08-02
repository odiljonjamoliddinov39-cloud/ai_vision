"""Ultralytics BYTETracker adapter; this module performs no inference."""

from __future__ import annotations

from argparse import Namespace
from datetime import datetime
from pathlib import Path
import time
from typing import Any

import numpy as np
import yaml

from detection.detector import Detection
from tracking.tracker import TrackedObject

_REQUIRED_KEYS = {
    "tracker_type", "track_high_thresh", "track_low_thresh",
    "new_track_thresh", "track_buffer", "match_thresh", "fuse_score",
}


class ByteTrackAdapter:
    """Own exactly one independent BYTETracker timeline for one camera."""

    def __init__(self, camera_name: str, tracker_config: str):
        self.camera_name = camera_name
        self.tracker_config = str(tracker_config)
        self._args = self._load_config(self.tracker_config)
        self._tracker = self._new_tracker()
        self._last_sequence: int | None = None
        self._last_frame_shape: tuple[int, int] | None = None
        self._updates = 0
        self._empty_updates = 0
        self._out_of_order_skips = 0
        self._resets = 0
        self._last_reset_reason: str | None = None
        self._last_update_at: float | None = None

    @staticmethod
    def _load_config(path: str) -> Namespace:
        config_path = Path(path)
        if not config_path.is_file():
            raise FileNotFoundError(f"ByteTrack config not found: {config_path}")
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError("ByteTrack config must be a YAML mapping")
        missing = sorted(_REQUIRED_KEYS - raw.keys())
        if missing:
            raise ValueError(f"ByteTrack config missing keys: {', '.join(missing)}")
        if str(raw["tracker_type"]).lower() != "bytetrack":
            raise ValueError("tracker_type must be 'bytetrack'")
        return Namespace(**raw)

    def _new_tracker(self):
        from ultralytics.trackers.byte_tracker import BYTETracker, STrack

        class CameraSTrack(STrack):
            _camera_count = 0

            @classmethod
            def next_id(cls) -> int:
                cls._camera_count += 1
                return cls._camera_count

            @classmethod
            def reset_id(cls) -> None:
                cls._camera_count = 0

        class CameraBYTETracker(BYTETracker):
            track_class = CameraSTrack

            def reset_id(self) -> None:
                self.track_class.reset_id()

        return CameraBYTETracker(self._args)

    def update(
        self,
        detections: list[Detection],
        frame_shape: tuple[int, ...],
        frame_sequence: int,
        observed_at: float | datetime,
    ) -> list[TrackedObject]:
        sequence = int(frame_sequence)
        if self._last_sequence is not None and sequence <= self._last_sequence:
            self._out_of_order_skips += 1
            return []
        shape = (int(frame_shape[0]), int(frame_shape[1]))
        if self._last_frame_shape is not None and shape != self._last_frame_shape:
            self.reset("resolution_change")
        self._last_sequence = sequence
        self._last_frame_shape = shape
        self._updates += 1
        self._empty_updates += int(not detections)
        self._last_update_at = time.time()

        from ultralytics.engine.results import Boxes
        rows = np.asarray(
            [[*d.box, float(d.confidence), int(d.class_id)] for d in detections],
            dtype=np.float32,
        ).reshape((-1, 6))
        tracks = self._tracker.update(Boxes(rows, shape))
        by_index = {index: detection for index, detection in enumerate(detections)}
        observed = observed_at.timestamp() if isinstance(observed_at, datetime) else float(observed_at)
        output: list[TrackedObject] = []
        for row in np.asarray(tracks).reshape((-1, 8)):
            x1, y1, x2, y2, track_id, score, class_id, detection_index = row
            source = by_index.get(int(detection_index))
            class_name = source.class_name if source else str(int(class_id))
            output.append(
                TrackedObject(
                    track_id=int(track_id), class_name=class_name,
                    confidence=float(score), box=(int(x1), int(y1), int(x2), int(y2)),
                    object_type=source.object_type if source else class_name,
                    inventory_name=source.inventory_name if source else None,
                    quantity=source.quantity if source else 1,
                    quantity_grid=source.quantity_grid if source else (1, 1, 1),
                    width_m=source.width_m if source else None,
                    height_m=source.height_m if source else None,
                    depth_m=source.depth_m if source else None,
                    distance_m=source.distance_m if source else None,
                    method=source.method if source else "bytetrack",
                    class_id=int(class_id), camera_name=self.camera_name,
                    frame_sequence=sequence, observed_at=observed,
                    is_confirmed=True,
                )
            )
        return output

    def reset(self, reason: str = "manual") -> None:
        self._tracker.reset()
        self._last_sequence = None
        self._last_frame_shape = None
        self._resets += 1
        self._last_reset_reason = reason

    def health(self) -> dict[str, Any]:
        return {
            "provider": "ultralytics_bytetrack", "camera_name": self.camera_name,
            "ready": True, "config": self.tracker_config,
            "last_sequence": self._last_sequence, "updates": self._updates,
            "empty_updates": self._empty_updates,
            "out_of_order_skips": self._out_of_order_skips,
            "resets": self._resets, "last_reset_reason": self._last_reset_reason,
            "last_update_at": self._last_update_at,
        }
