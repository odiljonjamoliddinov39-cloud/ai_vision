"""Deterministic count-once package rule engine."""
from typing import Dict, Optional

from .models import CountEvent, Line, Point, Polygon, RuleConfig, TrackObservation, TrackState

def _side(line: Line, point: Point) -> float:
    return ((line.end[0] - line.start[0]) * (point[1] - line.start[1])
            - (line.end[1] - line.start[1]) * (point[0] - line.start[0]))

def _crossed(line: Line, previous: Point, current: Point, direction: int) -> bool:
    before, after = _side(line, previous), _side(line, current)
    return (before * direction) <= 0 < (after * direction)

def _inside(point: Point, polygon: Polygon) -> bool:
    x, y = point
    contained = False
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y):
            intersection = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < intersection:
                contained = not contained
        previous = current
    return contained

class CountingRuleEngine:
    """Tracks each object through entry, zone, and exit exactly once."""

    def __init__(self, config: RuleConfig, inventory_rules=None) -> None:
        self.config = config
        self.inventory_rules = inventory_rules
        self._states: Dict[int, TrackState] = {}

    def evaluate_tracked(self, camera_id: str, detections, timestamp: float):
        """Canonical business-rule boundary for production tracked objects.

        The compatibility engine preserves identity/zone/direction parity while
        its rules are migrated; callers never invoke it directly.
        """
        if self.inventory_rules is None:
            return []
        return self.inventory_rules.process(camera_id, detections, timestamp)

    def state_for(self, track_id: int) -> TrackState:
        return self._states.get(track_id, TrackState.OUTSIDE)

    def evaluate(self, observation: TrackObservation) -> Optional[CountEvent]:
        if not self._eligible(observation):
            return None
        state = self.state_for(observation.track_id)
        if state is TrackState.FINISHED:
            return None
        if state is TrackState.OUTSIDE and _crossed(
            self.config.entry_line,
            observation.previous_center,
            observation.center,
            self.config.direction,
        ):
            state = TrackState.ENTERED
        if state is TrackState.ENTERED and _inside(
            observation.center, self.config.counting_zone
        ):
            state = TrackState.INSIDE
        if state is TrackState.INSIDE and _crossed(
            self.config.exit_line,
            observation.previous_center,
            observation.center,
            self.config.direction,
        ):
            state = TrackState.FINISHED
            self._states[observation.track_id] = state
            return CountEvent.from_observation(observation)
        self._states[observation.track_id] = state
        return None

    def _eligible(self, observation: TrackObservation) -> bool:
        if observation.class_id not in self.config.package_class_ids:
            return False
        if observation.confidence < self.config.minimum_confidence:
            return False
        if observation.track_age < self.config.minimum_track_age:
            return False
        return not any(_inside(observation.center, zone) for zone in self.config.ignore_zones)
