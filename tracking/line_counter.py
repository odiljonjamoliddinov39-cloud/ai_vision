"""
Virtual counting-line logic for warehouse stock movements.

A tracked object is counted once when its center crosses the configured
line. For a horizontal line, above -> below is IN and below -> above is
OUT. For a vertical line, left -> right is IN and right -> left is OUT.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LineCrossingEvent:
    tracking_id: int
    product_name: str
    confidence: float
    box: tuple[int, int, int, int]
    previous_position: tuple[int, int]
    current_position: tuple[int, int]
    direction: str
    camera_id: str


class LineCounter:
    def __init__(self, line: dict, camera_id: str):
        self.line = line
        self.camera_id = camera_id
        self.previous_positions: dict[int, tuple[int, int]] = {}
        self.counted_ids: set[int] = set()

    def update(self, tracked_objects) -> list[LineCrossingEvent]:
        events: list[LineCrossingEvent] = []

        for obj in tracked_objects:
            track_id = obj.track_id
            current = _box_center(obj.box)
            previous = self.previous_positions.get(track_id)
            self.previous_positions[track_id] = current

            if previous is None or track_id in self.counted_ids:
                continue

            direction = self._crossing_direction(previous, current)
            if direction is None:
                continue

            self.counted_ids.add(track_id)
            events.append(
                LineCrossingEvent(
                    tracking_id=track_id,
                    product_name=obj.class_name,
                    confidence=obj.confidence,
                    box=obj.box,
                    previous_position=previous,
                    current_position=current,
                    direction=direction,
                    camera_id=self.camera_id,
                )
            )

        return events

    def _crossing_direction(
        self, previous: tuple[int, int], current: tuple[int, int]
    ) -> str | None:
        x1 = int(self.line["x1"])
        y1 = int(self.line["y1"])
        x2 = int(self.line["x2"])
        y2 = int(self.line["y2"])

        if y1 == y2:
            if previous[1] < y1 <= current[1]:
                return "IN"
            if previous[1] > y1 >= current[1]:
                return "OUT"
            return None

        if x1 == x2:
            if previous[0] < x1 <= current[0]:
                return "IN"
            if previous[0] > x1 >= current[0]:
                return "OUT"
            return None

        prev_side = _line_side(previous, x1, y1, x2, y2)
        current_side = _line_side(current, x1, y1, x2, y2)
        if prev_side == 0 or current_side == 0 or prev_side == current_side:
            return None

        return "IN" if prev_side < current_side else "OUT"


def _box_center(box: tuple[int, int, int, int]) -> tuple[int, int]:
    x1, y1, x2, y2 = box
    return ((x1 + x2) // 2, (y1 + y2) // 2)


def _line_side(point: tuple[int, int], x1: int, y1: int, x2: int, y2: int) -> int:
    value = (x2 - x1) * (point[1] - y1) - (y2 - y1) * (point[0] - x1)
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0
