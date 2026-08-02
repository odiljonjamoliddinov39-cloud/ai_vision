from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
    def __init__(self):
        self.calls = 0

    def detect(self, frame):
        self.calls += 1
        return [FakeDetection()]


class FakeTracker:
    def __init__(self):
        self.calls = 0

    def update(self, detections, frame_shape, frame_sequence, observed_at):
        self.calls += 1
        assert len(detections) == 1
        assert frame_shape == (48, 64, 3)
        return [FakeTrackedObject()]


def _scan(monkeypatch, tmp_path, match, gemini):
    detector = FakeDetector()
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
    rows, _ = server._training_scan_camera(1, "Loading Bay", "", detector, {"baget_box": [1.0]}, diagnostics, 0)
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


def test_scan_uses_naming_service_only_when_dataset_confidence_is_insufficient(monkeypatch, tmp_path):
    detector, tracker, _, rows = _scan(
        monkeypatch,
        tmp_path,
        ("uncertain", 0.31),
        ("Corrected Baget Box", 0.84),
    )

    assert detector.calls == 1
    assert tracker.calls == 1
    assert rows[0]["suggested_name"] == "Corrected Baget Box"
    assert rows[0]["confidence"] == 0.84
    assert rows[0]["source"] == "naming_service"


def test_analytics_ui_is_one_scan_workflow_without_fake_test_or_loading_state():
    source = (Path(__file__).parents[1] / "dashboard-v2" / "app.js").read_text(encoding="utf-8")

    assert "Scan Cameras" in source
    assert "Optional object name" in source
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


def test_legacy_instant_analytics_endpoint_is_removed():
    paths = {route.path for route in server.app.routes}
    assert "/api/training/analytics/run" not in paths
    assert "/api/training/search" in paths
    assert "/api/training/search/status" in paths
    assert "/api/training/search/export" in paths
