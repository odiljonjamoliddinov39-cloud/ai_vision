import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

import api.server as server
from database.vision_config_db import VisionConfigDB


def _camera(camera_id, block_id, slot, name, active=True):
    return {
        "id": camera_id,
        "camera_id": camera_id,
        "camera_name": name,
        "block_id": block_id,
        "slot_number": slot,
        "is_active": active,
    }


def _scan_dependencies(monkeypatch):
    monkeypatch.setattr(
        server, "_scan_products",
        lambda: [{"id": 5, "name": "Baget Box"}],
    )


def test_scan_products_falls_back_to_warehouse_database(monkeypatch):
    class BrokenProducts:
        def list_products(self):
            raise RuntimeError("legacy recognition schema")

    rows = type("Rows", (), {
        "fetchall": lambda self: [{"id": 9, "name": "Baget Box", "category": "box"}]
    })()
    connection = type("Connection", (), {
        "__enter__": lambda self: self,
        "__exit__": lambda self, *args: None,
        "execute": lambda self, *args: rows,
    })()
    database = type("DB", (), {"connect": lambda self: connection})()
    warehouse = type("Warehouse", (), {"db": database})()

    monkeypatch.setattr(server, "_scan_product_database", lambda: BrokenProducts())
    monkeypatch.setattr(server, "WarehouseDB", lambda path: warehouse)

    assert server._scan_products() == [
        {"id": 9, "name": "Baget Box", "category": "box"}
    ]


def test_scan_products_falls_back_when_recognition_catalog_is_empty(monkeypatch):
    class EmptyProducts:
        def list_products(self):
            return []

    rows = type("Rows", (), {
        "fetchall": lambda self: [{"id": 3, "name": "Bread Tray", "category": "tray"}]
    })()
    connection = type("Connection", (), {
        "__enter__": lambda self: self,
        "__exit__": lambda self, *args: None,
        "execute": lambda self, *args: rows,
    })()
    database = type("DB", (), {"connect": lambda self: connection})()
    warehouse = type("Warehouse", (), {"db": database})()

    monkeypatch.setattr(server, "_scan_product_database", lambda: EmptyProducts())
    monkeypatch.setattr(server, "WarehouseDB", lambda path: warehouse)

    assert server._scan_products() == [
        {"id": 3, "name": "Bread Tray", "category": "tray"}
    ]
    monkeypatch.setattr(
        server, "VisionDB",
        lambda path: type("Audit", (), {"record_operator_action": lambda self, *args: 1})(),
    )


def test_block_camera_endpoint_returns_only_assigned_cameras(tmp_path, monkeypatch):
    vision_path = str(tmp_path / "vision.db")
    block = VisionConfigDB(vision_path).create_block("Warehouse A")
    other = VisionConfigDB(vision_path).create_block("Packaging")
    monkeypatch.setenv("VISION_DB_PATH", vision_path)
    monkeypatch.setattr(
        server,
        "_camera_operations_payload",
        lambda: [
            _camera(1, block["id"], 1, "Camera 1"),
            _camera(2, block["id"], 2, "Camera 2"),
            _camera(3, other["id"], 3, "Camera 3"),
        ],
    )

    response = server.list_block_cameras(block["id"])

    assert [row["camera_id"] for row in response["data"]] == [1, 2]
    assert response["meta"]["block"]["name"] == "Warehouse A"


def test_scan_start_passes_only_selected_block_slots(monkeypatch):
    _scan_dependencies(monkeypatch)
    monkeypatch.setattr(
        server,
        "_camera_operations_payload",
        lambda: [
            _camera(1, 10, 4, "Warehouse Camera 1"),
            _camera(2, 10, 7, "Warehouse Camera 2"),
            _camera(3, 20, 9, "Packaging Camera"),
        ],
    )
    captured = {}

    def start(query, slots, block_id, camera_ids):
        captured.update(query=query, slots=slots, block_id=block_id, camera_ids=camera_ids)
        return {"status": "running"}

    monkeypatch.setattr(server, "_training_search_start", start)

    response = asyncio.run(
        server.start_block_scan(
            server.BlockScanStart(block_id=10, camera_ids=[1, 2], product_id=5)
        )
    )

    assert response == {"status": "running"}
    assert captured == {
        "query": "Baget Box",
        "slots": {4, 7},
        "block_id": 10,
        "camera_ids": [1, 2],
    }


def test_scan_start_rejects_camera_from_another_block(monkeypatch):
    _scan_dependencies(monkeypatch)
    monkeypatch.setattr(
        server,
        "_camera_operations_payload",
        lambda: [_camera(1, 10, 1, "Warehouse"), _camera(2, 20, 2, "Packaging")],
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            server.start_block_scan(
                server.BlockScanStart(block_id=10, camera_ids=[1, 2], product_id=5)
            )
        )

    assert error.value.status_code == 422
    assert "selected Block" in error.value.detail


def test_scan_worker_filters_active_streams_to_selected_slots(monkeypatch, tmp_path):
    states = []
    monkeypatch.setattr(server, "_catalog_health_snapshot", lambda: {})
    monkeypatch.setattr(
        server,
        "_training_camera_map",
        lambda health: {1: "Camera 1", 2: "Camera 2", 3: "Camera 3"},
    )
    monkeypatch.setattr(
        server,
        "_training_detection_context",
        lambda query: (None, {"detection_mode": "stock_closed_class"}),
    )
    monkeypatch.setattr(server, "_training_dataset_reference_embeddings", lambda: {})
    monkeypatch.setattr(server, "_training_search_write_state", lambda state, generation: states.append(state) or True)

    server._training_search_worker("", 1, {1, 3}, 10, [101, 103])

    assert states[-1]["diagnostics"]["total_active_cameras"] == 2
    assert states[-1]["progress"]["total"] == 2
    assert states[-1]["block_id"] == 10
    assert states[-1]["camera_ids"] == [101, 103]


def test_scan_ui_is_block_oriented_without_camera_checkboxes():
    source = (Path(__file__).parents[1] / "dashboard-v2" / "app.js").read_text(encoding="utf-8")
    section = source[
        source.index("async function renderTrainingAnalytics"):
        source.index("async function applySearchRow")
    ]

    assert 'api("/api/v1/blocks"' in section
    assert 'api("/api/v1/products"' in section
    assert "/api/v1/blocks/${blockId}/cameras" in section
    assert 'catalogRequest("/api/v1/scan/start"' in section
    assert "data-scan-block" in section
    assert "data-scan-product" in section
    assert "Optional object name" not in section
    assert "No cameras are assigned to this Block." in section
    assert "data-block-camera-checkbox" not in section
