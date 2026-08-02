"""Tracking contracts shared by adapters and downstream consumers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from detection.detector import Detection


@dataclass
class TrackedObject:
    track_id: int
    class_name: str
    confidence: float
    box: tuple  # (x1, y1, x2, y2)
    object_type: str | None = None
    inventory_name: str | None = None
    quantity: int = 1
    quantity_grid: tuple[int, int, int] = (1, 1, 1)
    width_m: float | None = None
    height_m: float | None = None
    depth_m: float | None = None
    distance_m: float | None = None
    method: str | None = None
    class_id: int | None = None
    camera_name: str | None = None
    frame_sequence: int | None = None
    observed_at: float | datetime | None = None
    is_confirmed: bool = True


class TrackingEngine(Protocol):
    def update(
        self,
        detections: list[Detection],
        frame_shape: tuple[int, ...],
        frame_sequence: int,
        observed_at: float | datetime,
    ) -> list[TrackedObject]: ...

    def reset(self, reason: str = "manual") -> None: ...

    def health(self) -> dict: ...
