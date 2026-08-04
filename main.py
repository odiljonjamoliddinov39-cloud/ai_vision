"""
main.py

AI Vision Assistant entry point.

What this does:
  1. Connects to one or more webcam / RTSP cameras.          (FR-1)
  2. Runs YOLO object detection on every frame.               (FR-2)
  3. Draws bounding boxes, labels, confidence, FPS.           (FR-3)
  4. Shows live per-class object counts.                      (FR-4)
  5. Saves snapshots when trigger classes appear.             (FR-5)
  6. Logs detection events to a text log.                     (FR-6)
  7. Tracks per-object identity across frames (ByteTrack).    (Phase 3)
  8. Records check-in/check-out events + dwell time to SQLite. (Phase 4)

Tracking is on by default (see `tracking.enabled` in config.yaml) but
can be turned off to fall back to plain per-frame detection with no
persistent IDs and no occupancy database.

Run:
    python main.py
    python main.py --config config/config.yaml
    python main.py --no-display

Press "q" in any camera window to quit.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import time
from uuid import uuid4

import cv2
import yaml

from cameras.camera import load_cameras
from detection.detector import Detector
from detection.draw import draw_detections, draw_fps, draw_counts
from detection.spatial import SpatialAnalyzer
from detection.snapshot import SnapshotSaver
from database.camera_db import CameraDB
from database.event_log import EventLogger
from database.tracking_db import TrackingDB
from tracking.tracker import ObjectTracker, TrackedObject
from tracking.presence import PresenceTracker
from recognition.product_recognizer import ProductRecognizer
from database.vision_db import VisionDB
from events import EventEngine
from pipeline import LiveVisionPipeline
from rules import CountingRuleEngine, Line, RuleConfig
from stream import LiveFrame


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_camera_configs_from_db() -> list[dict]:
    db_path = os.getenv("CAMERA_DB_PATH", "database/cameras.db")
    db = CameraDB(db_path=db_path)
    cameras = db.list_active_cameras(include_secret=True)
    return [
        {
            "name": str(camera["name"]),
            "source": camera["stream_url"],
            "slot_number": camera.get("slot_number"),
        }
        for camera in cameras
    ]


def main():
    parser = argparse.ArgumentParser(description="AI Vision Assistant")
    parser.add_argument(
        "--config", default="config/config.yaml", help="Path to config.yaml"
    )
    parser.add_argument(
        "--no-display",
        action="store_true",
        help="Run detection without opening OpenCV windows.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="Stop after N frames. 0 means keep running.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    display_cfg = config.get("display", {})

    # --- Cameras (FR-1) ---
    cameras = load_cameras(load_camera_configs_from_db())
    if not cameras:
        _write_detection_health(
            "logs/detection_health.json",
            {
                "state": "error",
                "error": "No active cameras found in the camera database.",
                "frames_read": 0,
                "last_frame_at": None,
                "last_detection_count": 0,
                "model_loaded": False,
            },
        )
        print("No active cameras found in the camera database. Exiting.")
        return

    if args.no_display:
        print("Running in headless mode. GUI windows are disabled.")

    # --- Detector (FR-2) ---
    det_cfg = config["detection"]
    print(f"Loading model: {det_cfg['model_path']} ...")
    detector = Detector(
        model_path=det_cfg["model_path"],
        confidence_threshold=det_cfg.get("confidence_threshold", 0.5),
        device=det_cfg.get("device", "cpu"),
        classes=det_cfg.get("classes"),
        class_prompts=det_cfg.get("class_prompts"),
        image_size=det_cfg.get("image_size", 640),
        class_agnostic_nms=det_cfg.get("class_agnostic_nms", False),
    )
    if detector.model is None:
        print("Using deterministic dummy detector. Starting demo run...")
    else:
        print("Model loaded. Starting live detection... (press 'q' to quit)")

    spatial_cfg = config.get("spatial_analysis", {})
    spatial_analyzer = (
        SpatialAnalyzer.from_config(spatial_cfg)
        if spatial_cfg.get("enabled", False)
        else None
    )
    if spatial_analyzer is not None:
        print(
            "Monocular 3D sizing enabled "
            f"(camera height {spatial_analyzer.camera_height_m:.2f}m, "
            f"horizontal FOV {spatial_analyzer.horizontal_fov_degrees:.1f}deg)."
        )

    # --- Tracking (Phase 3) + occupancy (Phase 4) ---
    track_cfg = config.get("tracking", {})
    tracking_enabled = track_cfg.get("enabled", True)
    object_tracker = None
    presence_tracker = None
    tracking_db = None

    if tracking_enabled and detector.model is not None:
        object_tracker = ObjectTracker(
            model=detector.model,
            confidence_threshold=det_cfg.get("confidence_threshold", 0.5),
            device=det_cfg.get("device", "cpu"),
            classes=track_cfg.get("classes", det_cfg.get("classes")),
            tracker_config=track_cfg.get("tracker_config", "bytetrack.yaml"),
            image_size=det_cfg.get("image_size", 640),
            class_agnostic_nms=det_cfg.get("class_agnostic_nms", False),
        )
        presence_tracker = PresenceTracker(
            grace_period_seconds=track_cfg.get("grace_period_seconds", 5.0)
        )
        tracking_db = TrackingDB(db_path=track_cfg.get("db_path", "database/tracking.db"))
        print(
            f"Tracking enabled ({track_cfg.get('tracker_config', 'bytetrack.yaml')}), "
            f"grace period {track_cfg.get('grace_period_seconds', 5.0)}s."
        )

    # The dummy adapter is still useful for smoke tests, but it enters through
    # the exact same typed live-frame pipeline as production ByteTrack.
    if object_tracker is None and detector.model is None:
        object_tracker = _DemoTracker()

    if object_tracker is None:
        raise RuntimeError("tracking must be enabled: detector-only inference paths are unsupported")

    # --- Product recognition knowledge engine ---
    recognition_cfg = config.get("recognition", {})
    product_recognizer = None
    if recognition_cfg.get("enabled", False):
        try:
            product_recognizer = ProductRecognizer.from_config(recognition_cfg)
            print(
                "Product recognition enabled "
                f"({recognition_cfg.get('provider', 'gemini')} provider, "
                f"local DB: {recognition_cfg.get('db_path', 'database/products.db')})."
            )
        except Exception as exc:
            # Recognition is intentionally non-critical. Detection and live video
            # must continue even if the provider/key/config is wrong.
            print(f"Product recognition disabled due to configuration error: {exc}")
            product_recognizer = None

    # --- Snapshots (FR-5) ---
    snap_cfg = config.get("snapshots", {})
    snapshot_saver = None
    if snap_cfg.get("enabled", True):
        snapshot_saver = SnapshotSaver(
            save_dir=snap_cfg.get("save_dir", "snapshots"),
            trigger_classes=snap_cfg.get("trigger_classes"),
            cooldown_seconds=snap_cfg.get("cooldown_seconds", 5),
        )
    # ensure snapshots dir exists for live feed
    snapshots_dir = snap_cfg.get("save_dir", "snapshots")
    os.makedirs(snapshots_dir, exist_ok=True)
    live_feed_enabled = display_cfg.get("live_feed_enabled", True)

    # --- Event log (FR-6) ---
    log_cfg = config.get("logging", {})
    event_logger = None
    if log_cfg.get("enabled", True):
        event_logger = EventLogger(
            log_dir=log_cfg.get("log_dir", "logs"),
            log_file=log_cfg.get("log_file", "events.log"),
        )

    display_cfg = config.get("display", {})
    box_thickness = display_cfg.get("box_thickness", 2)
    font_scale = display_cfg.get("font_scale", 0.6)
    window_prefix = display_cfg.get("window_prefix", "AI Vision -")
    health_path = log_cfg.get("health_file", "logs/detection_health.json")
    frames_read = 0
    last_detection_count = 0
    last_tracked_count = 0
    last_frame_at = None
    last_spatial_objects = []

    pipeline_cfg = config.get("pipeline", {})
    rule_cfg = config.get("counting_rules", {})
    vision_db = VisionDB(pipeline_cfg.get("database_path", "database/vision.db"))
    target_class_id = int(rule_cfg.get("target_class_id", 0))
    target_class = str(rule_cfg.get("target_class", "baget_box"))
    counting_zone = tuple(tuple(point) for point in rule_cfg.get(
        "counting_zone", [[0, 180], [1000, 180], [1000, 500], [0, 500]]
    ))
    entry = rule_cfg.get("entry_line", [[0, 180], [1000, 180]])
    exit_line = rule_cfg.get("exit_line", [[0, 500], [1000, 500]])
    scan_runs = {}
    pipelines = {}
    for cam in cameras:
        stream_id = f"rtsp:{cam.name}"
        scan_id = vision_db.start_scan(stream_id, cam.name)
        scan_runs[cam.name] = scan_id
        rules = RuleConfig(
            package_class_ids=frozenset({target_class_id}), counting_zone=counting_zone,
            entry_line=Line(tuple(entry[0]), tuple(entry[1])),
            exit_line=Line(tuple(exit_line[0]), tuple(exit_line[1])),
            minimum_confidence=float(rule_cfg.get("minimum_confidence", 0.35)),
            minimum_track_age=int(rule_cfg.get("minimum_track_age", 4)),
            direction=int(rule_cfg.get("direction", 1)),
        )
        pipelines[cam.name] = LiveVisionPipeline(
            tracker=object_tracker, rule_engine=CountingRuleEngine(rules),
            event_engine=EventEngine(vision_db, scan_id), database=vision_db,
            pipeline_version=str(pipeline_cfg.get("version", "1.0.0")),
            detector_version=str(pipeline_cfg.get("detector_version", "unknown")),
            class_ids={target_class: target_class_id, "box": target_class_id},
        )

    prev_time = time.time()
    frame_number = 0

    try:
        while True:
            now = time.time()
            elapsed = now - prev_time
            fps = 1.0 / elapsed if elapsed > 0 else 0.0
            prev_time = now

            any_frame = False
            for cam in cameras:
                frame = cam.read()
                if frame is None:
                    continue
                any_frame = True
                frames_read += 1
                last_frame_at = datetime.now().isoformat(timespec="seconds")

                live_frame = LiveFrame(
                    camera_id=cam.name, stream_id=f"rtsp:{cam.name}", frame_uuid=uuid4(),
                    captured_at=datetime.now(timezone.utc), image=frame,
                )
                pipeline_result = pipelines[cam.name].process(live_frame)
                detections = list(pipeline_result.detections)
                last_tracked_count = len(detections)
                if presence_tracker is not None:
                    check_ins = presence_tracker.update(cam.name, detections, now)
                    for event in check_ins:
                        tracking_db.record_check_in(
                            event.track_id, event.camera_name, event.class_name
                        )
                        print(
                            f"[{cam.name}] Check-in: #{event.track_id} {event.class_name}"
                        )
                last_detection_count = len(detections)
                if spatial_analyzer is not None:
                    measurements = spatial_analyzer.enrich(frame, detections)
                    last_spatial_objects = [
                        {
                            **measurement.__dict__,
                            "quantity_grid": list(measurement.quantity_grid),
                        }
                        for measurement in measurements
                    ]

                if product_recognizer is not None:
                    product_recognizer.annotate(cam.name, frame, detections)

                draw_detections(frame, detections, box_thickness, font_scale)
                if display_cfg.get("show_fps", True):
                    draw_fps(frame, fps)
                draw_counts(frame, detections)

                if snapshot_saver is not None:
                    saved = snapshot_saver.maybe_save(cam.name, frame, detections)
                    for path in saved:
                        print(f"[{cam.name}] Snapshot saved: {path}")

                if live_feed_enabled:
                    _write_live_frame(
                        snapshots_dir,
                        cam,
                        frame,
                        width=int(display_cfg.get("live_frame_width", 480)),
                        jpeg_quality=int(display_cfg.get("live_frame_jpeg_quality", 42)),
                    )

                if event_logger is not None:
                    event_logger.log_detections(cam.name, detections)

                if not args.no_display:
                    cv2.imshow(f"{window_prefix} {cam.name}", frame)

            if presence_tracker is not None:
                check_outs = presence_tracker.expire(now)
                for event in check_outs:
                    result = tracking_db.record_check_out(
                        event.track_id, event.camera_name, event.class_name
                    )
                    duration_str = (
                        f"{result.duration_seconds:.1f}s"
                        if result.duration_seconds is not None
                        else "unknown"
                    )
                    print(
                        f"[{event.camera_name}] Check-out: #{event.track_id} "
                        f"{event.class_name} (dwell {duration_str})"
                    )

            if not any_frame:
                print("No frames available from any camera. Retrying...")
                time.sleep(1)

            _write_detection_health(
                health_path,
                {
                    "state": "running",
                    "error": None if any_frame else "No frames available from any camera.",
                    "camera_count": len(cameras),
                    "cameras": [
                        {"name": cam.name, "slot_number": cam.slot_number}
                        for cam in cameras
                    ],
                    "frames_read": frames_read,
                    "last_frame_at": last_frame_at,
                    "last_detection_count": last_detection_count,
                    "last_tracked_count": last_tracked_count,
                    "model_loaded": detector.model is not None,
                    "tracking_enabled": object_tracker is not None or detector.model is None,
                    "warehouse_counting_enabled": True,
                    "warehouse_counting_mode": "canonical_rule_engine",
                    "product_recognition_enabled": product_recognizer is not None,
                    "product_recognition_provider": recognition_cfg.get("provider")
                    if product_recognizer is not None
                    else None,
                    "spatial_analysis_enabled": spatial_analyzer is not None,
                    "last_spatial_objects": last_spatial_objects,
                    "live_feed_enabled": live_feed_enabled,
                    "event_logging_enabled": event_logger is not None,
                    "snapshot_enabled": snapshot_saver is not None,
                    "updated_at": datetime.now().isoformat(timespec="seconds"),
                },
            )

            frame_number += 1
            if args.max_frames and frame_number >= args.max_frames:
                break

            if not args.no_display and cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        for camera_name, scan_id in scan_runs.items():
            vision_db.finish_scan(scan_id, frames=frames_read, detections=frames_read, status="completed")
        for cam in cameras:
            cam.release()
        if product_recognizer is not None:
            product_recognizer.close()
        if not args.no_display:
            cv2.destroyAllWindows()
        print("Stopped.")


class _DemoTracker:
    def __init__(self):
        self.frame_index = 0

    def update(self, frame) -> list[TrackedObject]:
        y = min(520, 170 + self.frame_index * 5)
        self.frame_index += 1
        return [TrackedObject(track_id=1, class_name="box", confidence=0.95, box=(430, y, 530, y + 80))]


def _write_detection_health(path: str, payload: dict) -> None:
    health_path = Path(path)
    health_path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, indent=2)
    tmp_path = health_path.with_name(f"{health_path.stem}.{os.getpid()}.tmp")

    for _ in range(3):
        try:
            tmp_path.write_text(data, encoding="utf-8")
            tmp_path.replace(health_path)
            return
        except PermissionError:
            time.sleep(0.05)

    # Windows can briefly lock files read by the API process. A direct write
    # is safer than crashing the detector; the API already tolerates short
    # JSON read races.
    health_path.write_text(data, encoding="utf-8")


def _write_live_frame(
    snapshots_dir: str,
    cam,
    frame,
    width: int = 320,
    jpeg_quality: int = 28,
) -> None:
    try:
        output = frame
        width = max(240, min(int(width), 960))
        jpeg_quality = max(20, min(int(jpeg_quality), 85))
        frame_height, frame_width = frame.shape[:2]
        if frame_width > width:
            height = max(1, int(frame_height * (width / frame_width)))
            output = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)

        ok, jpg = cv2.imencode(
            ".jpg",
            output,
            [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality],
        )
        if not ok:
            return

        data = jpg.tobytes()
        if cam.slot_number is not None:
            _write_atomic_bytes(Path(snapshots_dir) / f"latest_slot_{cam.slot_number}.jpg", data)

        _write_atomic_bytes(Path(snapshots_dir) / f"latest_{_safe_live_feed_name(cam.name)}.jpg", data)
    except Exception:
        pass


def _write_atomic_bytes(path: Path, data: bytes) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def _safe_live_feed_name(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(value)).strip("_") or "camera"


if __name__ == "__main__":
    main()
