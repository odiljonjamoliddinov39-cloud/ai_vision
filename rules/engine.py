"""Business filtering for recognized tracked objects.

This module never counts. It only returns KEEP or IGNORE decisions.
"""
from __future__ import annotations

from .models import RuleConfig, RuleDecision, TrackObservation


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


class ObjectRuleEngine:
    """Evaluates whether a recognized observation is eligible for counting."""

    def __init__(self, config: RuleConfig) -> None:
        self.config = config

    def evaluate(self, observation: TrackObservation) -> RuleDecision:
        normalize = lambda value: " ".join(value.replace("_", " ").split()).casefold()
        recognized = normalize(observation.recognized_name or "")
        targets = {normalize(name) for name in self.config.target_products}
        if targets and recognized not in targets:
            return RuleDecision("ignore", "product_not_selected", observation)
        if not targets and observation.class_id not in self.config.package_class_ids:
            return RuleDecision("ignore", "class_not_allowed", observation)
        if observation.confidence < self.config.minimum_confidence:
            return RuleDecision("ignore", "confidence_below_minimum", observation)
        if observation.track_age < self.config.minimum_track_age:
            return RuleDecision("ignore", "track_too_young", observation)
        if any(_inside(observation.center, zone) for zone in self.config.ignore_zones):
            return RuleDecision("ignore", "inside_ignore_zone", observation)
        return RuleDecision("keep", "approved", observation)


class CountingRuleEngine:
    """Backward-compatible façade; new production code uses separate engines."""

    def __init__(self, config: RuleConfig, inventory_rules=None) -> None:
        from counting.engine import CountingEngine

        self.config = config
        self.rules = ObjectRuleEngine(config)
        self.counter = CountingEngine(config)

    def evaluate_tracked(self, camera_id: str, detections, timestamp: float):
        return []

    def state_for(self, track_id: int):
        return self.counter.state_for(track_id)

    def evaluate(self, observation: TrackObservation):
        decision = self.rules.evaluate(observation)
        return self.counter.evaluate(observation) if decision.keep else None
