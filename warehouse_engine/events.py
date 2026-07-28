from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class WarehouseEvent:
    event_type: str
    object_id: str
    camera_id: str
    timestamp: str
    zone: str | None = None
    previous_zone: str | None = None
    product_name: str | None = None
    confidence: float = 0.0
    inventory_delta: int = 0
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
