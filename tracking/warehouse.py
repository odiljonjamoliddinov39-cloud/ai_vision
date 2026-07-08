"""
tracking/warehouse.py

Turns raw zone enter/exit events (tracking/zones.py) into warehouse
business events, and flags the ones that look like theft:

  - an *item* class (box, suitcase, ...) entering a zone   => "item_in"
  - an *item* class leaving a zone                          => "item_out"
  - a person entering/leaving a zone                        => "person_in"/"person_out"

Suspicion rules applied to item_out events (all configurable):

  after_hours     — the item left the zone outside working hours.
  unattended      — the item left while no person was inside the zone
                    (an item can't walk out by itself: either the camera
                    missed the person or something is being pulled out
                    of view, e.g. through a window).
  bulk_removal    — N or more items left within a short window (a fast
                    sweep of shelves).

NOTE on classes: the stock COCO-trained YOLOv8 weights have no
"cardboard box" class; the closest built-ins are suitcase / backpack /
handbag. For real warehouse boxes, point detection.model_path at a
custom-trained model and list its class name (e.g. "box") in
warehouse.item_classes.

Pure Python on purpose (no cv2/torch) so the rules are unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class WarehouseEvent:
    zone_name: str
    camera_name: str
    track_id: int
    class_name: str
    event_type: str  # "item_in" | "item_out" | "person_in" | "person_out"
    at: float
    suspicious: bool = False
    reasons: list[str] = field(default_factory=list)
    persons_in_zone: int = 0


def _parse_hhmm(value: str) -> int:
    """'08:30' -> minutes since midnight."""
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


class WarehouseEventDetector:
    def __init__(
        self,
        item_classes: list[str] | None = None,
        person_class: str = "person",
        working_hours: dict | None = None,
        bulk_removal_count: int = 3,
        bulk_removal_window_seconds: float = 60.0,
        flag_unattended: bool = True,
    ):
        """
        Args:
            item_classes: class names treated as warehouse items.
            person_class: class name treated as a person.
            working_hours: {"start": "08:00", "end": "18:00"} local time,
                or None to disable the after-hours rule.
            bulk_removal_count / bulk_removal_window_seconds: N item_out
                events within the window flags them all as bulk removal.
            flag_unattended: flag item_out with no person in the zone.
        """
        self.item_classes = set(item_classes or ["box", "suitcase", "backpack", "handbag"])
        self.person_class = person_class
        self.working_hours = working_hours
        self.bulk_removal_count = bulk_removal_count
        self.bulk_removal_window_seconds = bulk_removal_window_seconds
        self.flag_unattended = flag_unattended

        # persons currently inside each (zone, camera)
        self._persons: dict[tuple[str, str], set[int]] = {}
        # recent item_out timestamps per (zone, camera) for the bulk rule
        self._recent_removals: dict[tuple[str, str], list[float]] = {}

    def _is_after_hours(self, at: float) -> bool:
        if not self.working_hours:
            return False
        start = _parse_hhmm(self.working_hours.get("start", "00:00"))
        end = _parse_hhmm(self.working_hours.get("end", "24:00"))
        t = datetime.fromtimestamp(at)
        minutes = t.hour * 60 + t.minute
        if start <= end:
            return not (start <= minutes < end)
        # overnight shift, e.g. 22:00-06:00
        return not (minutes >= start or minutes < end)

    def process(self, zone_events) -> list[WarehouseEvent]:
        """Consume ZoneEvents (tracking.zones.ZoneEvent) in order and
        return the corresponding WarehouseEvents, with suspicion flags."""
        out: list[WarehouseEvent] = []

        for ev in zone_events:
            key = (ev.zone_name, ev.camera_name)

            if ev.class_name == self.person_class:
                persons = self._persons.setdefault(key, set())
                if ev.event_type == "enter":
                    persons.add(ev.track_id)
                    event_type = "person_in"
                else:
                    persons.discard(ev.track_id)
                    event_type = "person_out"
                out.append(
                    WarehouseEvent(
                        zone_name=ev.zone_name,
                        camera_name=ev.camera_name,
                        track_id=ev.track_id,
                        class_name=ev.class_name,
                        event_type=event_type,
                        at=ev.at,
                        persons_in_zone=len(persons),
                    )
                )
                continue

            if ev.class_name not in self.item_classes:
                continue  # not a warehouse item (e.g. forklift, dog...)

            persons_in_zone = len(self._persons.get(key, set()))

            if ev.event_type == "enter":
                out.append(
                    WarehouseEvent(
                        zone_name=ev.zone_name,
                        camera_name=ev.camera_name,
                        track_id=ev.track_id,
                        class_name=ev.class_name,
                        event_type="item_in",
                        at=ev.at,
                        persons_in_zone=persons_in_zone,
                    )
                )
                continue

            # --- item_out: apply theft-suspicion rules ---
            reasons: list[str] = []
            if self._is_after_hours(ev.at):
                reasons.append("after_hours")
            if self.flag_unattended and persons_in_zone == 0:
                reasons.append("unattended")

            removals = self._recent_removals.setdefault(key, [])
            removals.append(ev.at)
            cutoff = ev.at - self.bulk_removal_window_seconds
            removals[:] = [t for t in removals if t >= cutoff]
            if len(removals) >= self.bulk_removal_count:
                reasons.append("bulk_removal")

            out.append(
                WarehouseEvent(
                    zone_name=ev.zone_name,
                    camera_name=ev.camera_name,
                    track_id=ev.track_id,
                    class_name=ev.class_name,
                    event_type="item_out",
                    at=ev.at,
                    suspicious=bool(reasons),
                    reasons=reasons,
                    persons_in_zone=persons_in_zone,
                )
            )

        return out
