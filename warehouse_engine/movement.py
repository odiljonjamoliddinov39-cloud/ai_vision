from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MovementState:
    center: tuple[int, int]
    zone: str
    last_seen: float
    status: str = "active"


class MovementEngine:
    def __init__(self, stopped_pixels: float = 8.0):
        self.stopped_pixels = float(stopped_pixels)
        self.states: dict[str, MovementState] = {}

    def update(
        self, object_id: str, center: tuple[int, int], zone: str, now: float
    ) -> tuple[str, str | None]:
        previous = self.states.get(object_id)
        self.states[object_id] = MovementState(center, zone, now)
        if previous is None:
            return "appeared", None
        if previous.zone != zone:
            return "zone_changed", previous.zone
        distance = ((center[0] - previous.center[0]) ** 2 + (center[1] - previous.center[1]) ** 2) ** 0.5
        return ("stayed" if distance <= self.stopped_pixels else "moved"), previous.zone

    def expire(self, active_ids: set[str], now: float, timeout: float) -> list[str]:
        expired = []
        for object_id, state in self.states.items():
            if object_id not in active_ids and state.status == "active" and now - state.last_seen >= timeout:
                state.status = "lost"
                expired.append(object_id)
        return expired
