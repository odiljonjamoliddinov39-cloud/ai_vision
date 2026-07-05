"""
tracking/presence.py

Phase 4: Memory of who entered/exited and for how long.

Turns the raw, per-frame track IDs coming out of tracking/tracker.py
into discrete "check-in" / "check-out" events:

  - A track_id seen for the first time on a camera => check-in.
  - A track_id that stops appearing for longer than `grace_period_seconds`
    => check-out (the grace period absorbs brief detector misses/occlusion
    so a person blinking out for one frame doesn't register as leaving
    and immediately re-entering).

This module has no dependency on OpenCV/YOLO/torch at all — it only
deals in plain (track_id, class_name, camera_name, timestamp) tuples,
so it's easy to unit test and easy to swap the underlying tracker later.

FR-Phase4: Occupancy / dwell-time tracking
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class _ActiveTrack:
    class_name: str
    first_seen: float
    last_seen: float


@dataclass
class PresenceEvent:
    track_id: int
    camera_name: str
    class_name: str
    event_type: str  # "check_in" | "check_out"
    at: float  # time.time() timestamp


class PresenceTracker:
    def __init__(self, grace_period_seconds: float = 5.0):
        """
        Args:
            grace_period_seconds: how long a track_id may go unseen before
                it's considered "checked out". Set higher for cameras with
                frequent brief occlusions, lower for snappier exit detection.
        """
        self.grace_period_seconds = grace_period_seconds
        # keyed by (camera_name, track_id)
        self._active: dict[tuple[str, int], _ActiveTrack] = {}

    def update(self, camera_name: str, tracked_objects, now: float | None = None) -> list[PresenceEvent]:
        """
        Call once per frame per camera with the currently visible tracked
        objects (anything with .track_id / .class_name, e.g.
        tracking.tracker.TrackedObject). Returns any check_in events that
        just happened. Call `expire()` separately (e.g. once per loop, not
        per-camera) to surface check_out events for tracks that dropped out.
        """
        now = now if now is not None else time.time()
        events: list[PresenceEvent] = []

        for obj in tracked_objects:
            key = (camera_name, obj.track_id)
            existing = self._active.get(key)
            if existing is None:
                self._active[key] = _ActiveTrack(
                    class_name=obj.class_name, first_seen=now, last_seen=now
                )
                events.append(
                    PresenceEvent(
                        track_id=obj.track_id,
                        camera_name=camera_name,
                        class_name=obj.class_name,
                        event_type="check_in",
                        at=now,
                    )
                )
            else:
                existing.last_seen = now

        return events

    def expire(self, now: float | None = None) -> list[PresenceEvent]:
        """
        Surfaces check_out events for any track not seen within the grace
        period, across all cameras. Should be called once per main loop
        iteration (after update() has been called for every camera).
        """
        now = now if now is not None else time.time()
        events: list[PresenceEvent] = []
        stale_keys = []

        for (camera_name, track_id), active in self._active.items():
            if now - active.last_seen > self.grace_period_seconds:
                stale_keys.append((camera_name, track_id))
                events.append(
                    PresenceEvent(
                        track_id=track_id,
                        camera_name=camera_name,
                        class_name=active.class_name,
                        event_type="check_out",
                        at=now,
                    )
                )

        for key in stale_keys:
            del self._active[key]

        return events

    def active_count(self) -> int:
        return len(self._active)
