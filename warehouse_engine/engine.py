from __future__ import annotations

import time
from datetime import datetime, timezone

from warehouse_engine.database import EngineDatabase
from warehouse_engine.events import WarehouseEvent
from warehouse_engine.identity import IdentityEngine
from warehouse_engine.inventory import Inventory
from warehouse_engine.movement import MovementEngine
from warehouse_engine.rules import RuleEngine
from warehouse_engine.zones import ZoneEngine


class WarehouseEngine:
    """Consumes tracked detections; only accepted rule events mutate inventory."""

    def __init__(self, config: dict, movement_sink=None):
        self.config = config
        self.database = EngineDatabase(
            config.get("db_path", "database/warehouse_engine.db")
        )
        self.identity = IdentityEngine(
            recovery_seconds=config.get("identity_recovery_seconds", 30)
        )
        self.zones = ZoneEngine(config.get("zones"))
        self.movement = MovementEngine(config.get("stopped_pixels", 8))
        self.rules = RuleEngine(config.get("minimum_confidence", 0.8))
        self.inventory = Inventory()
        self.movement_sink = movement_sink
        self.lines = config.get("counting_lines") or {}
        self.default_line = config.get("counting_line")
        self.previous_centers: dict[str, tuple[int, int]] = {}
        self.entry_times: dict[str, str] = {}
        self.lost_timeout = float(config.get("lost_timeout_seconds", 10))

    def process(
        self, camera_id: str, detections, timestamp: float | None = None
    ) -> list[WarehouseEvent]:
        now = float(timestamp if timestamp is not None else time.time())
        iso_time = datetime.fromtimestamp(now, timezone.utc).isoformat()
        events: list[WarehouseEvent] = []
        active_ids: set[str] = set()
        for detection in detections:
            if not hasattr(detection, "track_id"):
                continue
            box = tuple(int(value) for value in detection.box)
            class_name = str(detection.class_name)
            product_name = str(
                getattr(detection, "inventory_name", None) or class_name
            )
            confidence = float(detection.confidence)
            object_id, created, recovered = self.identity.resolve(
                camera_id, int(detection.track_id), class_name, box, now
            )
            active_ids.add(object_id)
            center = ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2)
            zone = self.zones.locate(center)
            movement, previous_zone = self.movement.update(
                object_id, center, zone, now
            )
            self.entry_times.setdefault(object_id, iso_time)

            if created:
                events.append(self._event("object_created", object_id, camera_id, iso_time, zone, product_name, confidence))
            elif recovered:
                events.append(self._event("track_recovered", object_id, camera_id, iso_time, zone, product_name, confidence))
            if movement == "zone_changed":
                events.append(
                    WarehouseEvent(
                        "zone_changed", object_id, camera_id, iso_time, zone,
                        previous_zone, product_name, confidence,
                    )
                )

            crossing = self._crossing(camera_id, object_id, center)
            delta, reason = self.rules.inventory_delta(
                object_id, confidence, crossing
            )
            if reason == "duplicate_ignored":
                events.append(self._event("duplicate_ignored", object_id, camera_id, iso_time, zone, product_name, confidence))
            if delta:
                self.inventory.apply(product_name, delta)
                event_type = "inventory_increased" if delta > 0 else "inventory_decreased"
                event = WarehouseEvent(
                    event_type, object_id, camera_id, iso_time, zone,
                    previous_zone, product_name, confidence, delta,
                    {"rule": reason, "crossing": crossing},
                )
                events.append(event)
                if self.movement_sink is not None:
                    self.movement_sink(event, detection)

            self.database.upsert_object(
                {
                    "object_id": object_id,
                    "product_name": product_name,
                    "class_name": class_name,
                    "current_zone": zone,
                    "entry_time": self.entry_times[object_id],
                    "exit_time": None,
                    "last_camera": camera_id,
                    "current_status": "active",
                    "confidence": confidence,
                    "last_seen_at": iso_time,
                    "metadata": {"track_id": int(detection.track_id), "box": box},
                }
            )

        active_recent = {
            object_id
            for object_id, identity in self.identity.objects.items()
            if now - float(identity["last_seen"]) < self.lost_timeout
        }
        for object_id in self.movement.expire(active_recent, now, self.lost_timeout):
            identity = self.identity.objects.get(object_id) or {}
            if identity.get("camera_id") != camera_id:
                continue
            event = self._event(
                "lost_track", object_id, camera_id, iso_time,
                self.movement.states[object_id].zone,
                identity.get("class_name"), 0.0,
            )
            events.append(event)
        for event in events:
            self.database.add_event(event)
        return events

    def _crossing(
        self, camera_id: str, object_id: str, center: tuple[int, int]
    ) -> str | None:
        previous = self.previous_centers.get(object_id)
        self.previous_centers[object_id] = center
        line = self.lines.get(camera_id) or self.default_line
        if previous is None or not line:
            return None
        x1, y1, x2, y2 = (int(line[key]) for key in ("x1", "y1", "x2", "y2"))
        if y1 == y2:
            if previous[1] < y1 <= center[1]:
                return "IN"
            if previous[1] > y1 >= center[1]:
                return "OUT"
        elif x1 == x2:
            if previous[0] < x1 <= center[0]:
                return "IN"
            if previous[0] > x1 >= center[0]:
                return "OUT"
        return None

    @staticmethod
    def _event(kind, object_id, camera_id, timestamp, zone, product, confidence):
        return WarehouseEvent(
            kind, object_id, camera_id, timestamp, zone,
            product_name=product, confidence=confidence,
        )
