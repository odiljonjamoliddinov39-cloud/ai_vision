"""Typed models for the package counting rule engine."""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Tuple

Point = Tuple[float, float]
Polygon = Tuple[Point, ...]

@dataclass(frozen=True)
class Line:
    start: Point
    end: Point

class TrackState(str, Enum):
    OUTSIDE = "outside"
    ENTERED = "entered"
    INSIDE = "inside"
    FINISHED = "finished"

@dataclass(frozen=True)
class RuleConfig:
    package_class_ids: frozenset[int]
    counting_zone: Polygon
    entry_line: Line
    exit_line: Line
    minimum_confidence: float = 0.5
    minimum_track_age: int = 2
    ignore_zones: Tuple[Polygon, ...] = ()
    direction: int = 1
    target_products: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.package_class_ids:
            raise ValueError("package_class_ids cannot be empty")
        if len(self.counting_zone) < 3:
            raise ValueError("counting_zone needs at least three points")
        if not 0 <= self.minimum_confidence <= 1:
            raise ValueError("minimum_confidence must be between 0 and 1")
        if self.minimum_track_age < 1:
            raise ValueError("minimum_track_age must be positive")
        if self.direction not in (-1, 1):
            raise ValueError("direction must be -1 or 1")

@dataclass(frozen=True)
class TrackObservation:
    camera_id: str
    stream_id: str
    frame_uuid: str
    frame_timestamp: datetime
    detection_timestamp: datetime
    track_id: int
    class_id: int
    confidence: float
    center: Point
    previous_center: Point
    track_age: int
    pipeline_version: str
    detector_version: str
    recognition_source: str
    processing_latency_ms: float
    recognized_name: str | None = None
    recognition_confidence: float = 0.0

    def __post_init__(self) -> None:
        if self.frame_timestamp.tzinfo is None or self.detection_timestamp.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")

@dataclass(frozen=True)
class CountEvent:
    camera_id: str
    stream_id: str
    frame_uuid: str
    frame_timestamp: datetime
    detection_timestamp: datetime
    track_id: int
    pipeline_version: str
    detector_version: str
    recognition_source: str
    processing_latency_ms: float

    @classmethod
    def from_observation(cls, observation: TrackObservation) -> "CountEvent":
        return cls(**{name: getattr(observation, name) for name in cls.__dataclass_fields__})


@dataclass(frozen=True)
class RuleDecision:
    decision: str
    reason: str
    observation: TrackObservation

    @property
    def keep(self) -> bool:
        return self.decision == "keep"
