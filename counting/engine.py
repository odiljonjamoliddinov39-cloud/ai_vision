"""Count approved objects once after entry/zone/exit progression."""
from __future__ import annotations

from rules.models import CountEvent, RuleConfig, TrackObservation, TrackState


def _side(line, point) -> float:
    return ((line.end[0] - line.start[0]) * (point[1] - line.start[1])
            - (line.end[1] - line.start[1]) * (point[0] - line.start[0]))


def _crossed(line, previous, current, direction: int) -> bool:
    before, after = _side(line, previous), _side(line, current)
    return (before * direction) <= 0 < (after * direction)


def _inside(point, polygon) -> bool:
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


class CountingEngine:
    """Owns track history and count-once state; it performs no filtering."""

    def __init__(self, config: RuleConfig) -> None:
        self.config = config
        self._states: dict[int, TrackState] = {}

    def state_for(self, track_id: int) -> TrackState:
        return self._states.get(track_id, TrackState.OUTSIDE)

    def evaluate(self, observation: TrackObservation) -> CountEvent | None:
        state = self.state_for(observation.track_id)
        if state is TrackState.FINISHED:
            return None
        if state is TrackState.OUTSIDE and _crossed(
            self.config.entry_line, observation.previous_center,
            observation.center, self.config.direction,
        ):
            state = TrackState.ENTERED
        if state is TrackState.ENTERED and _inside(
            observation.center, self.config.counting_zone
        ):
            state = TrackState.INSIDE
        if state is TrackState.INSIDE and _crossed(
            self.config.exit_line, observation.previous_center,
            observation.center, self.config.direction,
        ):
            self._states[observation.track_id] = TrackState.FINISHED
            return CountEvent.from_observation(observation)
        self._states[observation.track_id] = state
        return None
