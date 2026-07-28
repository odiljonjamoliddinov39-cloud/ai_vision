from __future__ import annotations

import uuid


class IdentityEngine:
    """Maps temporary camera tracker IDs to persistent warehouse object IDs."""

    def __init__(self, recovery_seconds: float = 30.0, recovery_iou: float = 0.35):
        self.recovery_seconds = float(recovery_seconds)
        self.recovery_iou = float(recovery_iou)
        self.track_map: dict[tuple[str, int], str] = {}
        self.objects: dict[str, dict] = {}

    def resolve(
        self,
        camera_id: str,
        track_id: int,
        class_name: str,
        box: tuple[int, int, int, int],
        now: float,
    ) -> tuple[str, bool, bool]:
        key = (camera_id, int(track_id))
        mapped = self.track_map.get(key)
        if mapped:
            self.objects[mapped].update(box=box, last_seen=now, active=True)
            return mapped, False, False

        candidates = [
            (_iou(box, value["box"]), object_id)
            for object_id, value in self.objects.items()
            if value["camera_id"] == camera_id
            and value["class_name"] == class_name
            and now - value["last_seen"] <= self.recovery_seconds
        ]
        if candidates:
            score, object_id = max(candidates)
            if score >= self.recovery_iou:
                self.track_map[key] = object_id
                self.objects[object_id].update(box=box, last_seen=now, active=True)
                return object_id, False, True

        object_id = f"P{uuid.uuid4().hex[:12].upper()}"
        self.track_map[key] = object_id
        self.objects[object_id] = {
            "camera_id": camera_id,
            "class_name": class_name,
            "box": box,
            "last_seen": now,
            "active": True,
        }
        return object_id, True, False


def _iou(first, second) -> float:
    x1, y1 = max(first[0], second[0]), max(first[1], second[1])
    x2, y2 = min(first[2], second[2]), min(first[3], second[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    first_area = max(0, first[2] - first[0]) * max(0, first[3] - first[1])
    second_area = max(0, second[2] - second[0]) * max(0, second[3] - second[1])
    union = first_area + second_area - intersection
    return intersection / union if union else 0.0
