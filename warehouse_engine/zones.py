from __future__ import annotations


class ZoneEngine:
    def __init__(self, zones: list[dict] | None = None):
        self.zones = zones or []

    def locate(self, point: tuple[int, int]) -> str:
        for zone in self.zones:
            polygon = [tuple(vertex) for vertex in zone.get("polygon") or []]
            if len(polygon) >= 3 and _inside(point, polygon):
                return str(zone.get("name") or "Unassigned")
        return "Unassigned"


def _inside(point: tuple[int, int], polygon: list[tuple[int, int]]) -> bool:
    x, y = point
    inside = False
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y):
            crossing_x = (x2 - x1) * (y - y1) / max(1e-9, y2 - y1) + x1
            if x < crossing_x:
                inside = not inside
        previous = current
    return inside
