"""
Warehouse stock movement counters.

A tracked object is counted once when its center crosses the configured
line. For a horizontal line, above -> below is IN and below -> above is
OUT. For a vertical line, left -> right is IN and right -> left is OUT.
Appearance mode is simpler: a tracked object is checked in once when it
is confidently recognized by the camera.
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
    quantity: int = 1
    object_type: str | None = None
    dimensions_m: tuple[float, float, float] | None = None
    distance_m: float | None = None
    quantity_grid: tuple[int, int, int] = (1, 1, 1)
    measurement_method: str | None = None


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
                    product_name=getattr(obj, "inventory_name", None) or obj.class_name,
                    confidence=obj.confidence,
                    box=obj.box,
                    previous_position=previous,
                    current_position=current,
                    direction=direction,
                    camera_id=self.camera_id,
                    **_spatial_event_fields(obj),
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


class AppearanceCounter:
    def __init__(self, camera_id: str, duplicate_iou_threshold: float = 0.3):
        self.camera_id = camera_id
        self.duplicate_iou_threshold = duplicate_iou_threshold
        self.counted_ids: set[int] = set()
        self.counted_objects: list[tuple[str, tuple[int, int, int, int]]] = []
        self.track_to_object: dict[int, int] = {}

    def update(self, tracked_objects) -> list[LineCrossingEvent]:
        events: list[LineCrossingEvent] = []

        for obj in tracked_objects:
            existing_index = self.track_to_object.get(obj.track_id)
            if existing_index is not None:
                self.counted_objects[existing_index] = (obj.class_name, obj.box)
                continue

            duplicate_index = self._find_spatial_duplicate(obj)
            self.counted_ids.add(obj.track_id)
            if duplicate_index is not None:
                self.track_to_object[obj.track_id] = duplicate_index
                self.counted_objects[duplicate_index] = (obj.class_name, obj.box)
                continue

            object_index = len(self.counted_objects)
            self.counted_objects.append((obj.class_name, obj.box))
            self.track_to_object[obj.track_id] = object_index
            center = _box_center(obj.box)
            events.append(
                LineCrossingEvent(
                    tracking_id=obj.track_id,
                    product_name=getattr(obj, "inventory_name", None) or obj.class_name,
                    confidence=obj.confidence,
                    box=obj.box,
                    previous_position=center,
                    current_position=center,
                    direction="IN",
                    camera_id=self.camera_id,
                    **_spatial_event_fields(obj),
                )
            )

        return events

    def _find_spatial_duplicate(self, obj) -> int | None:
        for index, (class_name, box) in enumerate(self.counted_objects):
            if class_name != obj.class_name:
                continue
            if _box_iou(box, obj.box) >= self.duplicate_iou_threshold:
                return index
        return None


def _box_center(box: tuple[int, int, int, int]) -> tuple[int, int]:
    x1, y1, x2, y2 = box
    return ((x1 + x2) // 2, (y1 + y2) // 2)


def _box_iou(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
) -> float:
    x1 = max(first[0], second[0])
    y1 = max(first[1], second[1])
    x2 = min(first[2], second[2])
    y2 = min(first[3], second[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    if intersection == 0:
        return 0.0

    first_area = max(0, first[2] - first[0]) * max(0, first[3] - first[1])
    second_area = max(0, second[2] - second[0]) * max(0, second[3] - second[1])
    union = first_area + second_area - intersection
    return intersection / union if union else 0.0


def _spatial_event_fields(obj) -> dict:
    width = getattr(obj, "width_m", None)
    height = getattr(obj, "height_m", None)
    depth = getattr(obj, "depth_m", None)
    dimensions = None
    if width is not None and height is not None and depth is not None:
        dimensions = (width, height, depth)
    return {
        "quantity": max(1, int(getattr(obj, "quantity", 1))),
        "object_type": getattr(obj, "object_type", None),
        "dimensions_m": dimensions,
        "distance_m": getattr(obj, "distance_m", None),
        "quantity_grid": getattr(obj, "quantity_grid", (1, 1, 1)),
        "measurement_method": getattr(obj, "method", None),
    }


def _line_side(point: tuple[int, int], x1: int, y1: int, x2: int, y2: int) -> int:
    value = (x2 - x1) * (point[1] - y1) - (y2 - y1) * (point[0] - x1)
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0
