from database.vision_db import VisionDB


def test_live_detection_and_count_are_persistent_and_traceable(tmp_path):
    db = VisionDB(str(tmp_path / "vision.db"))
    scan_id = db.start_scan("stream-1", "camera-1", "block-a")
    detection = {
        "camera_id": "camera-1", "stream_id": "stream-1", "frame_uuid": "frame-1",
        "frame_timestamp": "2026-08-05T00:00:00+00:00",
        "detection_timestamp": "2026-08-05T00:00:00.010000+00:00",
        "track_id": 7, "class_id": 0, "confidence": 0.91, "bbox": [1, 2, 3, 4],
        "pipeline_version": "1", "detector_version": "yolo", "recognition_source": "detector",
        "processing_latency_ms": 10.0,
    }
    detection_id = db.record_detection(scan_id, detection)
    event_id = db.record_count(scan_id, detection_id, detection, "block-a")
    db.finish_scan(scan_id, frames=1, detections=1)
    with db.db.connect() as conn:
        event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        count = conn.execute("SELECT * FROM counts WHERE event_id = ?", (event_id,)).fetchone()
        scan = conn.execute("SELECT * FROM scan_runs WHERE id = ?", (scan_id,)).fetchone()
    assert event["frame_uuid"] == "frame-1"
    assert count["quantity"] == 1
    assert scan["status"] == "completed"


def test_detection_rejects_missing_trace_fields(tmp_path):
    db = VisionDB(str(tmp_path / "vision.db"))
    scan_id = db.start_scan("stream-1", "camera-1")
    try:
        db.record_detection(scan_id, {"camera_id": "camera-1"})
    except ValueError as exc:
        assert "missing detection trace fields" in str(exc)
    else:
        raise AssertionError("missing trace fields were accepted")
