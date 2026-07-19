"""
Monocular 3D estimates for a fixed warehouse camera.

Measurements use a calibrated ground-plane approximation. They are useful for
relative sizing and stack-unit estimates, but are not a replacement for a
stereo/depth camera when certified metric dimensions are required.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class SpatialMeasurement:
    object_type: str
    inventory_name: str
    quantity: int
    quantity_grid: tuple[int, int, int]
    width_m: float
    height_m: float
    depth_m: float
    distance_m: float
    method: str = "monocular_ground_plane"


class SpatialAnalyzer:
    def __init__(
        self,
        horizontal_fov_degrees: float = 90.0,
        camera_height_m: float = 1.2,
        horizon_y_ratio: float = 0.28,
        min_distance_m: float = 0.5,
        max_distance_m: float = 50.0,
        estimate_depth_layers: bool = False,
        max_units_per_detection: int = 200,
        unit_dimensions: dict | None = None,
    ):
        self.horizontal_fov_degrees = horizontal_fov_degrees
        self.camera_height_m = camera_height_m
        self.horizon_y_ratio = horizon_y_ratio
        self.min_distance_m = min_distance_m
        self.max_distance_m = max_distance_m
        self.estimate_depth_layers = estimate_depth_layers
        self.max_units_per_detection = max_units_per_detection
        self.unit_dimensions = unit_dimensions or {}

    @classmethod
    def from_config(cls, config: dict) -> "SpatialAnalyzer":
        return cls(
            horizontal_fov_degrees=float(config.get("horizontal_fov_degrees", 90.0)),
            camera_height_m=float(config.get("camera_height_m", 1.2)),
            horizon_y_ratio=float(config.get("horizon_y_ratio", 0.28)),
            min_distance_m=float(config.get("min_distance_m", 0.5)),
            max_distance_m=float(config.get("max_distance_m", 50.0)),
            estimate_depth_layers=bool(config.get("estimate_depth_layers", False)),
            max_units_per_detection=int(config.get("max_units_per_detection", 200)),
            unit_dimensions=config.get("unit_dimensions") or {},
        )

    def enrich(self, frame, detections) -> list[SpatialMeasurement]:
        measurements = []
        for detection in detections:
            measurement = self.measure(
                frame.shape,
                detection.class_name,
                detection.box,
                inventory_name=getattr(detection, "inventory_name", None),
            )
            for field, value in measurement.__dict__.items():
                setattr(detection, field, value)
            measurements.append(measurement)
        return measurements

    def measure(
        self,
        frame_shape,
        class_name: str,
        box: tuple[int, int, int, int],
        inventory_name: str | None = None,
    ) -> SpatialMeasurement:
        frame_height, frame_width = frame_shape[:2]
        x1, y1, x2, y2 = box
        pixel_width = max(1, x2 - x1)
        pixel_height = max(1, y2 - y1)

        focal_px = frame_width / (
            2.0 * math.tan(math.radians(self.horizontal_fov_degrees) / 2.0)
        )
        horizon_y = frame_height * self.horizon_y_ratio
        ground_offset_px = max(1.0, y2 - horizon_y)
        distance_m = focal_px * self.camera_height_m / ground_offset_px
        distance_m = min(self.max_distance_m, max(self.min_distance_m, distance_m))

        width_m = pixel_width * distance_m / focal_px
        height_m = pixel_height * distance_m / focal_px
        object_type, default_inventory_name, depth_ratio = _class_profile(class_name)
        inventory_name = inventory_name or default_inventory_name
        depth_m = max(0.05, width_m * depth_ratio)
        quantity, grid = self._estimate_quantity(
            class_name=class_name,
            inventory_name=default_inventory_name,
            width_m=width_m,
            height_m=height_m,
            depth_m=depth_m,
        )

        return SpatialMeasurement(
            object_type=object_type,
            inventory_name=inventory_name,
            quantity=quantity,
            quantity_grid=grid,
            width_m=round(width_m, 2),
            height_m=round(height_m, 2),
            depth_m=round(depth_m, 2),
            distance_m=round(distance_m, 2),
        )

    def _estimate_quantity(
        self,
        class_name: str,
        inventory_name: str,
        width_m: float,
        height_m: float,
        depth_m: float,
    ) -> tuple[int, tuple[int, int, int]]:
        if "stack" not in class_name.lower():
            return 1, (1, 1, 1)

        unit = self.unit_dimensions.get(inventory_name) or self.unit_dimensions.get(
            class_name
        )
        if not unit:
            return 1, (1, 1, 1)

        unit_width = max(0.01, float(unit.get("width_m", 1.0)))
        unit_height = max(0.01, float(unit.get("height_m", 1.0)))
        unit_depth = max(0.01, float(unit.get("depth_m", 1.0)))
        columns = max(1, round(width_m / unit_width))
        rows = max(1, round(height_m / unit_height))
        layers = max(1, round(depth_m / unit_depth)) if self.estimate_depth_layers else 1
        quantity = min(self.max_units_per_detection, columns * rows * layers)
        return quantity, (columns, rows, layers)


def _class_profile(class_name: str) -> tuple[str, str, float]:
    normalized = class_name.lower()
    if "box" in normalized or "carton" in normalized:
        return "cuboid", "cardboard box", 0.55
    if "sack" in normalized:
        return "deformable bag", "sack", 0.4
    if "bag" in normalized:
        return "deformable bag", "bag", 0.35
    if "pallet" in normalized:
        return "palletized load", "palletized item", 0.75
    if "package" in normalized:
        return "package", "package", 0.5
    return "unknown solid", class_name, 0.5
