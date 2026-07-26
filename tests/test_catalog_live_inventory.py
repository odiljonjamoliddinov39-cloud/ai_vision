import json

from api import server


def test_live_inventory_reports_unidentified_objects_by_camera(tmp_path, monkeypatch):
    class FakeCatalogDB:
        def list_items(self, _scope_id, active_only=False):
            return [{"id": "checked-in-1", "name": "Blue crate"}]

    health_path = tmp_path / "detection_health.json"
    health_path.write_text(
        json.dumps(
            {
                "cameras": [],
                "last_spatial_objects_by_camera": {
                    "NVR Main Camera 2": [
                        {"inventory_name": "Blue crate", "quantity": 3},
                        {"inventory_name": "Unknown carton", "quantity": 4},
                    ],
                    "NVR Main Camera 7": [
                        {"class_name": "unidentified object", "quantity": 2}
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(server, "_catalog_db", FakeCatalogDB())
    monkeypatch.setattr(server, "DETECTION_HEALTH_PATH", health_path)

    results = server._catalog_unidentified_current_frame("warehouse-a")

    assert results == [
        {
            "item_id": "checked-in-1",
            "item_name": "Unidentified",
            "quantity": 6,
            "confidence": 0.0,
            "dimensions_m": None,
            "measurement_method": "unidentified-detector-object",
            "camera_counts": [
                {"camera_name": "NVR Main Camera 2", "quantity": 4},
                {"camera_name": "NVR Main Camera 7", "quantity": 2},
            ],
            "_state_key": "__unidentified__",
        }
    ]


def test_dashboard_uses_persistent_live_recognition_session():
    source = (
        server.ROOT / "dashboard-v2" / "app.js"
    ).read_text(encoding="utf-8")

    assert 'catalogApiPath("/api/catalog/recognition/run-live")' in source
    assert 'catalogApiPath("/api/catalog/recognition/run-live/status")' in source
    assert "status.remaining_seconds" in source
    assert "entry.crop_url" in source
    assert "Scanning live feeds" in source
