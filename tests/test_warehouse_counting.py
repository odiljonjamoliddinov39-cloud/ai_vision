import os
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.warehouse_db import WarehouseDB
from tracking.line_counter import AppearanceCounter, LineCounter


@dataclass
class _FakeTrackedObject:
    track_id: int
    class_name: str = "box"
    confidence: float = 0.9
    box: tuple = (0, 0, 20, 20)


def test_line_counter_counts_once_on_horizontal_crossing():
    counter = LineCounter(
        line={"x1": 0, "y1": 100, "x2": 200, "y2": 100},
        camera_id="Camera 1",
    )

    first = counter.update([_FakeTrackedObject(track_id=7, box=(40, 80, 60, 100))])
    second = counter.update([_FakeTrackedObject(track_id=7, box=(40, 100, 60, 120))])
    third = counter.update([_FakeTrackedObject(track_id=7, box=(40, 120, 60, 140))])

    assert first == []
    assert len(second) == 1
    assert second[0].direction == "IN"
    assert third == []


def test_warehouse_db_records_in_and_out_movements(tmp_path):
    db = WarehouseDB(db_path=str(tmp_path / "warehouse.db"))

    assert db.record_movement("box", "IN", "Camera 1", 1, 0.9) == 1
    assert db.record_movement("box", "OUT", "Camera 1", 2, 0.9) == 0
    db.record_unknown_item(3, 0.2, None, "Camera 1")

    stock = db.get_all_stock()
    assert stock[0]["name"] == "box"
    assert stock[0]["current_stock"] == 0

    assert db.movement_counts() == {"IN": 1, "OUT": 1}

    movements = db.recent_movements(limit=10)
    assert len(movements) == 2
    assert movements[0]["direction"] == "OUT"
    assert movements[1]["direction"] == "IN"


def test_appearance_counter_counts_first_confident_sighting_once():
    counter = AppearanceCounter(camera_id="Camera 1")
    obj = _FakeTrackedObject(track_id=10, class_name="box")

    first = counter.update([obj])
    second = counter.update([obj])

    assert len(first) == 1
    assert first[0].direction == "IN"
    assert first[0].product_name == "box"
    assert second == []


def test_appearance_counter_suppresses_overlapping_tracker_id_change():
    counter = AppearanceCounter(camera_id="Camera 1")

    first = counter.update(
        [_FakeTrackedObject(track_id=2, class_name="box", box=(100, 100, 300, 300))]
    )
    reassigned = counter.update(
        [_FakeTrackedObject(track_id=32, class_name="box", box=(108, 104, 305, 304))]
    )
    separate = counter.update(
        [_FakeTrackedObject(track_id=33, class_name="box", box=(400, 100, 600, 300))]
    )

    assert len(first) == 1
    assert reassigned == []
    assert len(separate) == 1
