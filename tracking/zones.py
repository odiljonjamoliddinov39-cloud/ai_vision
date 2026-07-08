"""
tracking/zones.py

Zone-based object counting: "how many boxes are inside the warehouse
zone right now", not just "how many boxes are somewhere in the frame".

A Zone is a named polygon on a camera's image (normalized 0-1
coordinates so the same config works at any resolution; `polygon: null`
means the whole frame). Each tracked object is tested by its
bottom-center point — where the object touches the floor — which is far
more robust than the box center for deciding "inside the warehouse".

To avoid flapping (an object straddling the zone edge generating a
storm of enter/exit events), state only flips after the object has been
on the other side for `min_frames` consecutive updates.

Like tracking/presence.py this module deliberately has no OpenCV/YOLO
dependency: it deals only in plain track tuples, so it's easy to unit
test.
"""

from __future__ import annotations

from dataclasses import dataclass, field


def point_in_polygon(x: float, y: float, polygon: list[tuple[float, float]]) -> bool:
    """Ray-casting point-in-polygon test. Polygon is a list of (x, y)
    vertices; edges wrap around from the last vertex to the first."""
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if (yi > y) != (yj > y):
            x_cross = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_cross:
                inside = not inside
        j = i
    return inside


@dataclass
class Zone:
    name: str
    camera_name: str
    # Normalized (0-1) polygon vertices, or None for the entire frame.
    polygon: list[tuple[float, float]] | None = None

    def contains(self, x_norm: float, y_norm: float) -> bool:
        if self.polygon is None:
            return 0.0 <= x_norm <= 1.0 and 0.0 <= y_norm <= 1.0
        return point_in_polygon(x_norm, y_norm, self.polygon)


@dataclass
class ZoneEvent:
    zone_name: str
    camera_name: str
    track_id: int
    class_name: str
    event_type: str  # "enter" | "exit"
    at: float  # time.time() timestamp


@dataclass
class _TrackZoneState:
    class_name: str
    inside: bool
    # consecutive updates the object has spent on the opposite side of
    # its current state; state flips once this reaches min_frames
    flip_streak: int = 0
    last_seen: float = 0.0


class ZoneMonitor:
    """
    Feed it the tracked objects for a camera once per frame; it emits
    ZoneEvents when an object durably enters or leaves a zone, and can
    report live per-zone per-class counts at any time.
    """

    def __init__(self, zones: list[Zone], min_frames: int = 3, lost_after_seconds: float = 5.0):
        """
        Args:
            zones: zones to monitor (each bound to one camera by name).
            min_frames: consecutive frames on the other side of the zone
                boundary required before an enter/exit event fires.
            lost_after_seconds: a track unseen for this long is treated as
                having exited whatever zones it was inside (e.g. the
                tracker lost it, or it left the camera's view entirely).
        """
        self.zones = zones
        self.min_frames = max(1, min_frames)
        self.lost_after_seconds = lost_after_seconds
        # state per (zone_name, camera_name, track_id)
        self._state: dict[tuple[str, str, int], _TrackZoneState] = {}

    def update(
        self, camera_name: str, tracked_objects, now: float, frame_size: tuple[int, int] | None = None
    ) -> list[ZoneEvent]:
        """
        Args:
            camera_name: which camera these objects came from.
            tracked_objects: anything with .track_id/.class_name/.box
                (pixel coords) — e.g. tracking.tracker.TrackedObject.
            now: current timestamp.
            frame_size: (width, height) in pixels, used to normalize box
                coordinates. Required if any zone has a polygon.
        Returns newly fired enter/exit events.
        """
        events: list[ZoneEvent] = []
        camera_zones = [z for z in self.zones if z.camera_name == camera_name]
        if not camera_zones:
            return events

        for zone in camera_zones:
            for obj in tracked_objects:
                x1, y1, x2, y2 = obj.box
                if frame_size:
                    w, h = frame_size
                    # bottom-center: where the object meets the floor
                    x_norm = ((x1 + x2) / 2) / max(w, 1)
                    y_norm = y2 / max(h, 1)
                else:
                    x_norm, y_norm = (x1 + x2) / 2, y2

                inside_now = zone.contains(x_norm, y_norm)
                key = (zone.name, camera_name, obj.track_id)
                state = self._state.get(key)

                if state is None:
                    # First sighting: adopt current side immediately. An
                    # object first seen inside the zone counts as entering
                    # (it appeared there), one first seen outside doesn't.
                    self._state[key] = _TrackZoneState(
                        class_name=obj.class_name, inside=inside_now, last_seen=now
                    )
                    if inside_now:
                        events.append(
                            ZoneEvent(zone.name, camera_name, obj.track_id, obj.class_name, "enter", now)
                        )
                    continue

                state.last_seen = now
                state.class_name = obj.class_name
                if inside_now == state.inside:
                    state.flip_streak = 0
                    continue

                state.flip_streak += 1
                if state.flip_streak >= self.min_frames:
                    state.inside = inside_now
                    state.flip_streak = 0
                    events.append(
                        ZoneEvent(
                            zone.name,
                            camera_name,
                            obj.track_id,
                            obj.class_name,
                            "enter" if inside_now else "exit",
                            now,
                        )
                    )

        return events

    def expire(self, now: float) -> list[ZoneEvent]:
        """Emit exit events for tracks that vanished while inside a zone
        (tracker lost them / they left the camera view). Call once per
        main-loop iteration."""
        events: list[ZoneEvent] = []
        stale = []
        for key, state in self._state.items():
            if now - state.last_seen > self.lost_after_seconds:
                stale.append(key)
                if state.inside:
                    zone_name, camera_name, track_id = key
                    events.append(
                        ZoneEvent(zone_name, camera_name, track_id, state.class_name, "exit", now)
                    )
        for key in stale:
            del self._state[key]
        return events

    def counts(self) -> dict[str, dict[str, int]]:
        """Live occupancy: {zone_name: {class_name: count}} of objects
        currently inside each zone."""
        result: dict[str, dict[str, int]] = {}
        for (zone_name, _camera, _track_id), state in self._state.items():
            if not state.inside:
                continue
            per_class = result.setdefault(zone_name, {})
            per_class[state.class_name] = per_class.get(state.class_name, 0) + 1
        # zones with nobody inside still appear, with empty counts
        for zone in self.zones:
            result.setdefault(zone.name, {})
        return result

    def occupants(self, zone_name: str) -> list[tuple[int, str]]:
        """(track_id, class_name) currently inside the given zone."""
        return [
            (track_id, state.class_name)
            for (zname, _cam, track_id), state in self._state.items()
            if zname == zone_name and state.inside
        ]


def load_zones(zone_configs: list[dict] | None, default_camera: str | None = None) -> list[Zone]:
    """Build Zone objects from config entries like:
        zones:
          - name: Warehouse
            camera: Camera 1
            polygon: [[0.1, 0.2], [0.9, 0.2], [0.9, 0.95], [0.1, 0.95]]
    `polygon: null` (or omitted) means the whole frame.
    """
    zones: list[Zone] = []
    for entry in zone_configs or []:
        polygon = entry.get("polygon")
        zones.append(
            Zone(
                name=entry.get("name", "Zone"),
                camera_name=entry.get("camera", default_camera or "Camera 1"),
                polygon=[tuple(p) for p in polygon] if polygon else None,
            )
        )
    return zones
