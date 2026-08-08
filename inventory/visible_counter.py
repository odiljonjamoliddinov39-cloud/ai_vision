"""Rule-driven counting of target products visible in one live frame."""
from __future__ import annotations

from dataclasses import dataclass


Box = tuple[int, int, int, int]
Point = tuple[float, float]


@dataclass(frozen=True)
class InventoryCandidate:
    index: int
    box: Box
    detector_class: str
    detector_confidence: float
    recognized_name: str
    recognition_confidence: float
    recognition_source: str


@dataclass(frozen=True)
class InventoryDecision:
    candidate: InventoryCandidate
    accepted: bool
    reason: str


@dataclass(frozen=True)
class InventoryResult:
    decisions: tuple[InventoryDecision, ...]

    @property
    def raw_detection_count(self) -> int:
        return len(self.decisions)

    @property
    def accepted(self) -> tuple[InventoryDecision, ...]:
        return tuple(item for item in self.decisions if item.accepted)

    @property
    def rejected(self) -> tuple[InventoryDecision, ...]:
        return tuple(item for item in self.decisions if not item.accepted)

    @property
    def final_inventory_count(self) -> int:
        return len(self.accepted)


def _normalize(value: str) -> str:
    return " ".join(str(value).replace("_", " ").split()).casefold()


def _inside(point: Point, polygon: tuple[Point, ...]) -> bool:
    if not polygon:
        return True
    x, y = point
    contained = False
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y):
            boundary_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < boundary_x:
                contained = not contained
        previous = current
    return contained


def _iou(first: Box, second: Box) -> float:
    x1, y1 = max(first[0], second[0]), max(first[1], second[1])
    x2, y2 = min(first[2], second[2]), min(first[3], second[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    first_area = max(0, first[2] - first[0]) * max(0, first[3] - first[1])
    second_area = max(0, second[2] - second[0]) * max(0, second[3] - second[1])
    union = first_area + second_area - intersection
    return intersection / union if union else 0.0


class VisibleInventoryCounter:
    """Counts accepted target detections in a frame without movement state."""

    def __init__(self, *, target_product: str, minimum_confidence: float = 0.5,
                 minimum_area_px: int = 64, duplicate_iou: float = 0.65,
                 inventory_roi: tuple[Point, ...] = (),
                 ignore_zones: tuple[tuple[Point, ...], ...] = ()) -> None:
        self.target_product = _normalize(target_product)
        self.minimum_confidence = float(minimum_confidence)
        self.minimum_area_px = int(minimum_area_px)
        self.duplicate_iou = float(duplicate_iou)
        self.inventory_roi = inventory_roi
        self.ignore_zones = ignore_zones

    def evaluate(self, candidates: list[InventoryCandidate]) -> InventoryResult:
        decisions: dict[int, InventoryDecision] = {}
        eligible: list[InventoryCandidate] = []
        for candidate in candidates:
            x1, y1, x2, y2 = candidate.box
            center = ((x1 + x2) / 2, (y1 + y2) / 2)
            if _normalize(candidate.recognized_name) != self.target_product:
                decisions[candidate.index] = InventoryDecision(candidate, False, "target_mismatch")
            elif min(candidate.detector_confidence, candidate.recognition_confidence) < self.minimum_confidence:
                decisions[candidate.index] = InventoryDecision(candidate, False, "confidence_below_minimum")
            elif max(0, x2 - x1) * max(0, y2 - y1) < self.minimum_area_px:
                decisions[candidate.index] = InventoryDecision(candidate, False, "object_too_small")
            elif not _inside(center, self.inventory_roi):
                decisions[candidate.index] = InventoryDecision(candidate, False, "outside_inventory_roi")
            elif any(_inside(center, zone) for zone in self.ignore_zones):
                decisions[candidate.index] = InventoryDecision(candidate, False, "inside_ignore_zone")
            else:
                eligible.append(candidate)

        kept: list[InventoryCandidate] = []
        for candidate in sorted(
            eligible,
            key=lambda item: min(item.detector_confidence, item.recognition_confidence),
            reverse=True,
        ):
            if any(_iou(candidate.box, existing.box) >= self.duplicate_iou for existing in kept):
                decisions[candidate.index] = InventoryDecision(candidate, False, "duplicate_overlap")
            else:
                kept.append(candidate)
                decisions[candidate.index] = InventoryDecision(candidate, True, "accepted")
        return InventoryResult(tuple(decisions[index] for index in sorted(decisions)))
