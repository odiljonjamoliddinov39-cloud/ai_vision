"""The only legal inference input: a frame acquired from a live stream."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class LiveFrame:
    camera_id: str
    stream_id: str
    frame_uuid: UUID
    captured_at: datetime
    image: object
    source: str = "live_rtsp"

    def __post_init__(self) -> None:
        if self.source != "live_rtsp":
            raise ValueError("inference frames must originate from a live RTSP stream")
        if self.captured_at.tzinfo is None:
            raise ValueError("captured_at must be timezone-aware")
