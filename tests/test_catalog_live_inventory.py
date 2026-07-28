import json

from api import server


def test_saved_item_prompts_are_added_to_yolo_vocabulary(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "CATALOG_PROMPTS_PATH", tmp_path / "catalog_prompts.json")
    server._catalog_save_item_prompts(
        "warehouse-a",
        "checked-in-1",
        ["long bakery carton", "Baget package"],
    )

    prompts = server._catalog_detection_prompts(
        [
            {
                "id": "checked-in-1",
                "scope_id": "warehouse-a",
                "name": "Baget Box",
            }
        ],
        "warehouse-a",
    )

    assert "Baget Box" in prompts
    assert "long bakery carton" in prompts
    assert "Baget package" in prompts


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
    assert 'data-acc-form="catalog-prompts"' in source
    assert "YOLO detection prompts" in source
    assert "YOLO scanned" in source


def test_catalog_yolo_scans_all_loaded_camera_frames_by_default():
    source = (server.ROOT / "api" / "server.py").read_text(encoding="utf-8")

    assert 'CATALOG_RECOGNITION_MAX_FRAMES", "100"' in source
    assert '"camera_count": len(frames)' in source
    assert '"detection_count": 0' in source


def test_live_recognition_is_one_minute_and_results_keep_detection_time():
    backend = (server.ROOT / "api" / "server.py").read_text(encoding="utf-8")
    frontend = (server.ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")

    assert "CATALOG_LIVE_RUN_DURATION_SECONDS = 60" in backend
    assert 'enriched.setdefault("detected_at", _now_iso())' in backend
    assert "entry.detected_at || result.completed_at" in frontend
    assert "formatCatalogTime(entry.detected_at)" in frontend


def test_catalog_yolo_reads_each_persistent_stream_manager_frame():
    source = (server.ROOT / "api" / "server.py").read_text(encoding="utf-8")

    assert "def _catalog_live_frame_image(" in source
    assert "_get_stream_manager().latest_frame_bytes(" in source
    assert "frame = _catalog_live_frame_image(" in source


def test_catalog_matching_accepts_realistic_moved_crop_similarity():
    backend = (server.ROOT / "api" / "server.py").read_text(encoding="utf-8")
    frontend = (server.ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")

    assert 'CATALOG_CROP_SIMILARITY_THRESHOLD", "0.70"' in backend
    assert 'scan["cached_candidate_count"]' in backend
    assert 'scan["catalog_scores"]' in backend
    assert "Best catalog similarity" in frontend


def test_catalog_recognition_runs_reference_proposals_before_optional_prompt_detector():
    root = Path(__file__).resolve().parents[1]
    backend = (root / "api" / "server.py").read_text(encoding="utf-8")
    frontend = (root / "dashboard-v2" / "app.js").read_text(encoding="utf-8")

    assert "def _catalog_class_agnostic_boxes(" in backend
    assert "def _catalog_class_agnostic_candidates(" in backend
    assert 'scan["proposal_source"] = "class_agnostic_reference"' in backend
    assert 'CATALOG_RUN_PROMPT_DETECTOR", "false"' in backend
    assert 'scan["prompt_detector_skipped"] = True' in backend
    assert "CATALOG_PROPOSAL_MIN_PER_CAMERA" in backend
    assert 'CATALOG_PROPOSAL_SIMILARITY_THRESHOLD", "0.88"' in backend
    assert "class-agnostic fallback generated" in frontend


def test_one_click_product_learning_is_hot_loaded_into_counting_pipeline():
    root = Path(__file__).resolve().parents[1]
    backend = (root / "api" / "server.py").read_text(encoding="utf-8")
    frontend = (root / "dashboard-v2" / "app.js").read_text(encoding="utf-8")
    tracker = (root / "tracking" / "tracker.py").read_text(encoding="utf-8")
    main = (root / "main.py").read_text(encoding="utf-8")
    config = (root / "config" / "config.yaml").read_text(encoding="utf-8")

    assert "/api/catalog/learning/start" in backend
    assert "/api/catalog/learning/{session_id}" in backend
    assert "/api/catalog/learning/save" in backend
    assert "PRODUCT_FINGERPRINTS_PATH" in backend
    assert "Learn New Product" in frontend
    assert "Save and start counting" in frontend
    assert "camera_name: cameraName" in frontend
    assert 'input[name="learned-view"]:checked' in frontend
    assert "view_indices: viewIndices" in frontend
    assert "camera_name: str" in backend
    assert "view_indices: list[int]" in backend
    assert "existing_item_id: str | None" in backend
    assert 'session["existing_match"]' in backend
    assert "Existing manual product found" in frontend
    assert "existing_item_id: existingItemId" in frontend
    assert 'CATALOG_EXISTING_PRODUCT_SIMILARITY_THRESHOLD", "0.82"' in backend
    assert 'existing_matches[0]["matching_view_count"] >= 2' in backend
    assert "matchingViewIndices" in frontend
    assert "object_proposal_boxes(frame)" in tracker
    assert "learned_detections = [" in main
    assert "catalog_only: true" in config
