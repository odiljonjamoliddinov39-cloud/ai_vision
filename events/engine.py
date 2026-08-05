"""Persists approved rule events; it never detects or tracks objects."""
from dataclasses import asdict

from database.vision_db import VisionDB
from rules.models import CountEvent


class EventEngine:
    def __init__(self, database: VisionDB, scan_run_id: int, block_id: str | None = None):
        self.database = database
        self.scan_run_id = scan_run_id
        self.block_id = block_id

    def publish_count(self, detection_id: int, event: CountEvent, class_id: int) -> int:
        payload = asdict(event)
        payload["class_id"] = class_id
        for key, value in tuple(payload.items()):
            if hasattr(value, "isoformat"):
                payload[key] = value.isoformat()
        return self.database.record_count(self.scan_run_id, detection_id, payload, self.block_id)
