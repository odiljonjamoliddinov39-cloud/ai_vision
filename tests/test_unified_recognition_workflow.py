from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading
import time

import numpy as np

from api import server


@dataclass
class FakeDetection:
    box: tuple[int, int, int, int] = (5, 6, 35, 30)
    confidence: float = 0.88
    class_name: str = "baget_box"


@dataclass
class FakeTrackedObject:
    track_id: int = 17
    box: tuple[int, int, int, int] = (5, 6, 35, 30)
    confidence: float = 0.91
    class_name: str = "baget_box"
    inventory_name: str | None = None


class FakeDetector:
    def __init__(self, class_name="baget_box"):
        self.calls = 0
        self.class_name = class_name

    def detect(self, frame):
        self.calls += 1
        return [FakeDetection(class_name=self.class_name)]


class FakeTracker:
    def __init__(self):
        self.calls = 0

    def update(self, detections, frame_shape, frame_sequence, observed_at):
        self.calls += 1
        assert len(detections) == 1
        assert frame_shape == (48, 64, 3)
        return [FakeTrackedObject()]


def _scan(monkeypatch, tmp_path, match, gemini, class_name="baget_box"):
    detector = FakeDetector(class_name)
    tracker = FakeTracker()
    frame = np.full((48, 64, 3), 128, dtype=np.uint8)
    monkeypatch.setattr(server, "TRAINING_STAGING_DIR", tmp_path / "staging")
    monkeypatch.setattr(server, "_catalog_live_frame_image", lambda **kwargs: frame)
    monkeypatch.setattr(server, "_training_scan_tracker", lambda camera: tracker)
    monkeypatch.setattr(server, "_training_match_dataset", lambda crop, refs: match)
    gemini_suggestion = gemini if callable(gemini) else lambda crop: gemini
    monkeypatch.setattr(server, "_training_gemini_suggestion", gemini_suggestion)
    monkeypatch.setattr(server, "_read_yaml", lambda path: {"recognition": {"similarity_threshold": 0.62}})
    server._training_scan_sequences.clear()
    diagnostics = {"frames_read": 0, "detections": 0, "tracked": 0}
    rows, _, _ = server._training_scan_camera(1, "Loading Bay", "", detector, {"baget_box": [1.0]}, diagnostics, 0)
    return detector, tracker, diagnostics, rows


def test_scan_uses_yolo_and_bytetrack_once_and_prefers_local_dataset(monkeypatch, tmp_path):
    def unexpected_gemini(_crop):
        raise AssertionError("confident local dataset match must not call the naming service")

    detector, tracker, diagnostics, rows = _scan(
        monkeypatch,
        tmp_path,
        ("baget_box_stack_individual", 0.93),
        unexpected_gemini,
    )

    assert detector.calls == 1
    assert tracker.calls == 1
    assert diagnostics == {"frames_read": 1, "detections": 1, "tracked": 1}
    assert len(rows) == 1
    assert rows[0]["suggested_name"] == "baget_box_stack_individual"
    assert rows[0]["name"] == "baget_box_stack_individual"
    assert rows[0]["camera"] == "Loading Bay"
    assert rows[0]["track_id"] == 17
    assert rows[0]["confidence"] == 0.93
    assert rows[0]["source"] == "dataset"
    assert rows[0]["keep"] is True
    assert rows[0]["crop_url"].endswith("/crop_00.jpg")


def test_scan_uses_yolo_label_without_waiting_for_naming_service(monkeypatch, tmp_path):
    def unexpected_gemini(_crop):
        raise AssertionError("a useful YOLO label must not wait on the naming service")

    detector, tracker, _, rows = _scan(
        monkeypatch,
        tmp_path,
        ("uncertain", 0.31),
        unexpected_gemini,
    )

    assert detector.calls == 1
    assert tracker.calls == 1
    assert rows[0]["suggested_name"] == "baget_box"
    assert rows[0]["confidence"] == 0.88
    assert rows[0]["source"] == "yolo"


def test_scan_uses_naming_service_for_genuinely_unknown_detection(monkeypatch, tmp_path):
    _, _, _, rows = _scan(
        monkeypatch,
        tmp_path,
        ("uncertain", 0.31),
        ("Corrected Baget Box", 0.84),
        class_name="unknown object",
    )

    assert rows[0]["suggested_name"] == "Corrected Baget Box"
    assert rows[0]["confidence"] == 0.84
    assert rows[0]["source"] == "naming_service"


def test_empty_query_uses_broad_prompts_not_configured_single_prompt(monkeypatch):
    captured = []

    class OpenVocabularyModel:
        def set_classes(self, prompts):
            self.prompts = prompts

    detector = type("Detector", (), {"model": OpenVocabularyModel()})()
    monkeypatch.setattr(
        server,
        "_read_yaml",
        lambda path: {"detection": {"class_prompts": ["baget box"], "broad_discovery_prompts": ["person", "box"]}},
    )
    monkeypatch.setattr(server, "_training_detector", lambda prompts: captured.append(prompts) or detector)

    _, mode = server._training_detection_context("")

    assert captured == [["person", "box"]]
    assert captured[0] != ["baget box"]
    assert mode["broad_discovery"] is True
    assert mode["stock_closed_class"] is False


def test_nonempty_product_query_does_not_filter_universal_detector(monkeypatch):
    captured = []
    detector = type("Detector", (), {"model": type("Model", (), {"set_classes": lambda self, prompts: None})()})()
    monkeypatch.setattr(server, "_read_yaml", lambda path: {"detection": {"broad_discovery_prompts": ["person", "box", "forklift"]}})
    monkeypatch.setattr(server, "_training_detector", lambda prompts: captured.append(prompts) or detector)

    _, mode = server._training_detection_context("  Red Pallet  ")

    assert captured == [["person", "box", "forklift"]]
    assert mode["query_prompt"] == "Red Pallet"
    assert mode["detection_mode"] == "universal_detection"


def test_stale_snapshots_do_not_create_active_cameras(monkeypatch, tmp_path):
    for slot in range(1, 27):
        (tmp_path / f"latest_slot_{slot}.jpg").write_bytes(b"stale")
    monkeypatch.setattr(server, "SNAPSHOT_DIR", tmp_path)
    streams = [
        {"slot_number": slot, "name": f"Camera {slot}", "status": "online"}
        for slot in range(1, 8)
    ]
    monkeypatch.setattr(server, "_get_stream_manager", lambda: type("Manager", (), {"status": lambda self: {"streams": streams}})())

    cameras = server._training_camera_map({"cameras": [{"slot_number": 26, "name": "stale"}]})

    assert len(cameras) == 7
    assert set(cameras) == set(range(1, 8))


def test_raw_detection_is_returned_when_tracker_returns_no_tracks(monkeypatch, tmp_path):
    detector = FakeDetector()
    tracker = FakeTracker()
    tracker.update = lambda *args, **kwargs: []
    frame = np.full((48, 64, 3), 128, dtype=np.uint8)
    monkeypatch.setattr(server, "TRAINING_STAGING_DIR", tmp_path / "staging")
    monkeypatch.setattr(server, "_catalog_live_frame_image", lambda **kwargs: frame)
    monkeypatch.setattr(server, "_training_scan_tracker", lambda camera: tracker)
    monkeypatch.setattr(server, "_training_match_dataset", lambda crop, refs: ("baget_box", 0.9))
    monkeypatch.setattr(server, "_read_yaml", lambda path: {"recognition": {"similarity_threshold": 0.62}})

    rows, _, diagnostics = server._training_scan_camera(1, "Camera 1", "", detector, {}, None, 0)

    assert diagnostics["detections"] == 1
    assert diagnostics["tracked"] == 0
    assert len(rows) == 1
    assert rows[0]["track_id"] is None


def test_bounded_worker_pool_processes_all_cameras_and_reports_failures(monkeypatch, tmp_path):
    cameras = {slot: f"Camera {slot}" for slot in range(1, 8)}
    active = 0
    peak = 0
    lock = threading.Lock()

    def scan(slot, camera, *args, **kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.03)
        with lock:
            active -= 1
        reason = "no_frame" if slot in {2, 6} else "no_detections"
        return [], 0, {"frames_read": int(reason != "no_frame"), "detections": 0, "tracked": 0, "failure_reason": reason}

    states = []
    monkeypatch.setenv("AI_VISION_SEARCH_WORKERS", "3")
    monkeypatch.setattr(server, "_catalog_health_snapshot", lambda: {})
    monkeypatch.setattr(server, "_training_camera_map", lambda health: cameras)
    monkeypatch.setattr(server, "_training_detection_context", lambda query: (object(), {"detection_mode": "stock_closed_class"}))
    monkeypatch.setattr(server, "_training_dataset_reference_embeddings", lambda: {})
    monkeypatch.setattr(server, "_training_scan_camera", scan)
    monkeypatch.setattr(server, "TRAINING_STAGING_DIR", tmp_path)
    monkeypatch.setattr(server, "_training_search_write_state", lambda state, generation: states.append(state) or True)

    server._training_search_worker("", 1)

    final = states[-1]
    assert 1 < peak <= 3
    assert final["diagnostics"]["total_active_cameras"] == 7
    assert final["diagnostics"]["attempted_cameras"] == 7
    assert final["diagnostics"]["cameras_failed"] == 2
    assert final["diagnostics"]["cameras_completed"] == 5
    assert len(final["diagnostics"]["failures"]) == 2
    assert final["progress"] == {"done": 7, "total": 7}


def test_analytics_ui_is_one_scan_workflow_without_fake_test_or_loading_state():
    source = (Path(__file__).parents[1] / "dashboard-v2" / "app.js").read_text(encoding="utf-8")

    assert "Scan Cameras" in source
    assert "Target Product" in source
    assert "data-scan-product" in source
    assert "Optional object name" not in source
    assert "Object Preview" in source
    assert "Suggested Name" in source
    assert "Editable Final Name" in source
    assert "Track ID" in source
    assert "Save to Dataset" in source
    assert "Export to Excel" in source
    assert "data-run-test" not in source
    assert "data-test-results" not in source
    assert '"test.running": "Running..."' not in source
    assert "Instant detection test" not in source
    assert "diag.attempted_cameras ?? done" in source
    assert "diag.total_active_cameras ?? total" in source
    assert "Scanned ${d.cameras}" not in source


def test_legacy_instant_analytics_endpoint_is_removed():
    paths = {route.path for route in server.app.routes if hasattr(route, "path")}
    assert "/api/training/analytics/run" not in paths
    assert "/api/training/search" in paths
    assert "/api/training/search/status" in paths
    assert "/api/training/search/export" in paths
