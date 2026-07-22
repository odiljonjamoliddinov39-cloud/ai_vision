import os
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from detection.spatial import SpatialAnalyzer


@dataclass
class _Detection:
    class_name: str
    box: tuple[int, int, int, int]


def _analyzer():
    return SpatialAnalyzer(
        horizontal_fov_degrees=90.0,
        camera_height_m=1.2,
        horizon_y_ratio=0.28,
        unit_dimensions={
            "cardboard box": {
                "width_m": 0.45,
                "height_m": 0.35,
                "depth_m": 0.35,
            }
        },
    )


def test_spatial_analyzer_estimates_stack_dimensions_and_units():
    measurement = _analyzer().measure(
        frame_shape=(1080, 1920, 3),
        class_name="stack of cardboard boxes",
        box=(830, 380, 1100, 490),
    )

    assert measurement.object_type == "cuboid"
    assert measurement.inventory_name == "cardboard box"
    assert measurement.quantity == 8
    assert measurement.quantity_grid == (4, 2, 1)
    assert measurement.width_m == 1.73
    assert measurement.height_m == 0.7
    assert measurement.depth_m == 0.95
    assert measurement.distance_m == 6.14


def test_spatial_analyzer_keeps_single_box_quantity_at_one():
    measurement = _analyzer().measure(
        frame_shape=(1080, 1920, 3),
        class_name="cardboard box",
        box=(1306, 371, 1395, 504),
    )

    assert measurement.quantity == 1
    assert measurement.quantity_grid == (1, 1, 1)


def test_spatial_analyzer_enriches_detection_contract():
    detection = _Detection(
        class_name="stack of cardboard boxes",
        box=(830, 380, 1100, 490),
    )

    _analyzer().enrich(type("Frame", (), {"shape": (1080, 1920, 3)})(), [detection])

    assert detection.inventory_name == "cardboard box"
    assert detection.object_type == "cuboid"
    assert detection.quantity == 8


def test_spatial_analyzer_preserves_catalog_inventory_name():
    measurement = _analyzer().measure(
        frame_shape=(720, 1280, 3),
        class_name="box",
        box=(420, 220, 820, 650),
        inventory_name="Checked-in blue crate",
    )

    assert measurement.inventory_name == "Checked-in blue crate"
    assert measurement.width_m > 0
    assert measurement.height_m > 0
    assert measurement.depth_m > 0


def test_spatial_analyzer_uses_recognized_inventory_dimensions_for_quantity():
    analyzer = SpatialAnalyzer(
        horizontal_fov_degrees=90.0,
        camera_height_m=1.2,
        horizon_y_ratio=0.28,
        unit_dimensions={
            "Blue crate": {
                "width_m": 0.42,
                "height_m": 0.31,
                "depth_m": 0.28,
            },
            "cardboard box": {
                "width_m": 99.0,
                "height_m": 99.0,
                "depth_m": 99.0,
            },
        },
    )

    measurement = analyzer.measure(
        frame_shape=(1080, 1920, 3),
        class_name="stack of cardboard boxes",
        box=(830, 380, 1100, 490),
        inventory_name="Blue crate",
    )

    assert measurement.inventory_name == "Blue crate"
    assert measurement.quantity > 1
    assert measurement.quantity_grid[0] > 1
