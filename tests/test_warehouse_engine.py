from dataclasses import dataclass

import pytest

from warehouse_engine.engine import WarehouseEngine
from warehouse_engine.rules import parse_task_prompt

# The warehouse-engine operations dashboard page was removed in the
# training-kiosk pivot (commit f7b0f55). Skipped (not deleted) so it can be
# re-enabled if the operator platform is restored.
_KIOSK_PIVOT = "Warehouse-engine dashboard page retired in the training-kiosk pivot (f7b0f55)."


@dataclass
class Detection:
    track_id: int
    class_name: str
    confidence: float
    box: tuple[int, int, int, int]
    inventory_name: str | None = None


def test_detector_observations_do_not_change_inventory_without_rule_event(tmp_path):
    engine = WarehouseEngine(
        {
            "db_path": str(tmp_path / "engine.db"),
            "minimum_confidence": 0.8,
            "counting_line": {"x1": 0, "y1": 100, "x2": 500, "y2": 100},
        }
    )

    first = engine.process(
        "Camera 1", [Detection(41, "box", 0.95, (10, 20, 60, 70))], 1.0
    )

    assert engine.inventory.stock == {}
    assert [event.event_type for event in first] == ["object_created"]


def test_line_crossing_changes_inventory_once_for_persistent_identity(tmp_path):
    accepted = []
    engine = WarehouseEngine(
        {
            "db_path": str(tmp_path / "engine.db"),
            "minimum_confidence": 0.8,
            "counting_line": {"x1": 0, "y1": 100, "x2": 500, "y2": 100},
        },
        movement_sink=lambda event, detection: accepted.append(event),
    )
    engine.process("Camera 1", [Detection(41, "box", 0.95, (10, 20, 60, 70))], 1.0)
    events = engine.process(
        "Camera 1", [Detection(41, "box", 0.95, (10, 90, 60, 140))], 2.0
    )
    engine.process(
        "Camera 1", [Detection(41, "box", 0.95, (10, 90, 60, 140))], 4.0
    )
    inventory_event = next(
        event for event in events if event.event_type == "inventory_increased"
    )
    duplicate_delta, duplicate_reason = engine.rules.inventory_delta(
        inventory_event.object_id, 0.95, "IN"
    )

    assert engine.inventory.stock["box"] == 1
    assert len(accepted) == 1
    assert any(event.event_type == "inventory_increased" for event in events)
    assert duplicate_delta == 0
    assert duplicate_reason == "duplicate_ignored"


def test_ai_task_builder_produces_engine_rule():
    task = parse_task_prompt("Count all baget boxes entering warehouse.")

    assert task["target_object"] == "baget boxes"
    assert task["zone"] == "Receiving"
    assert task["count_rule"] == "line_crossing"
    assert task["tracking"] == "persistent"


def test_main_routes_inventory_through_live_pipeline():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "main.py").read_text(
        encoding="utf-8"
    )

    assert "pipeline.process for name, pipeline in live_pipelines.items()" in source
    assert "warehouse_engine.process(" not in source
    assert "_process_warehouse_counting(" not in source.split('if __name__ == "__main__":')[0]


@pytest.mark.skip(reason=_KIOSK_PIVOT)
def test_dashboard_exposes_engine_operations_and_task_builder():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1] / "dashboard-v2" / "app.js"
    ).read_text(encoding="utf-8")

    assert 'catalogRequest("/api/warehouse-engine/overview?limit=100")' in source
    assert "Warehouse Intelligence Engine" in source
    assert "Movement timeline" in source
    assert "AI Task Builder" in source
    assert 'catalogRequest("/api/warehouse-engine/tasks/parse"' in source
    assert '{ id: "logs", label: "Logs", sub: "Engine actions" }' in source
    assert 'catalogRequest("/api/warehouse-engine/events?limit=500")' in source
    assert "Warehouse action logs" in source
