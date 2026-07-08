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
from datetime import datetime
from pathlib import Path
import time

import cv2
import yaml
import os

from cameras.camera import load_cameras
from detection.detector import Detector
from detection.draw import draw_detections, draw_fps, draw_counts, draw_counting_line
from detection.snapshot import SnapshotSaver
from database.event_log import EventLogger
from database.tracking_db import TrackingDB
from database.warehouse_db import WarehouseDB
from tracking.line_counter import AppearanceCounter, LineCounter
from tracking.tracker import ObjectTracker, TrackedObject
from tracking.presence import PresenceTracker


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


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
    cameras = load_cameras(config["cameras"])
    if not cameras:
        _write_detection_health(
            "logs/detection_health.json",
            {
                "state": "error",
                "error": "No cameras could be opened. Check config/config.yaml.",
                "frames_read": 0,
                "last_frame_at": None,
                "last_detection_count": 0,
                "model_loaded": False,
            },
        )
        print("No cameras could be opened. Check config/config.yaml. Exiting.")
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

    # --- Warehouse stock counting MVP ---
    warehouse_cfg = config.get("warehouse_counting", {})
    warehouse_enabled = warehouse_cfg.get("enabled", False)
    warehouse_db = None
    warehouse_counters = {}
    reviewed_unknown_ids: set[tuple[str, int]] = set()
    if warehouse_enabled:
        warehouse_db = WarehouseDB(db_path=warehouse_cfg.get("db_path", "database/warehouse.db"))
        count_mode = warehouse_cfg.get("mode", "appearance")
        line = warehouse_cfg.get(
            "counting_line", {"x1": 100, "y1": 300, "x2": 900, "y2": 300}
        )
        warehouse_counters = {
            cam.name: (
                LineCounter(line=line, camera_id=cam.name)
                if count_mode == "line"
                else AppearanceCounter(camera_id=cam.name)
            )
            for cam in cameras
        }
        print(
            f"Warehouse counting enabled ({count_mode} mode). "
            f"Stock DB: {warehouse_db.db_path}"
        )

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

    prev_time = time.time()
    frame_number = 0
    dummy_positions = {cam.name: 0 for cam in cameras}

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

                if object_tracker is not None:
                    detections = object_tracker.update(frame)
                    last_tracked_count = len(detections)
                    check_ins = presence_tracker.update(cam.name, detections, now)
                    for event in check_ins:
                        tracking_db.record_check_in(
                            event.track_id, event.camera_name, event.class_name
                        )
                        print(
                            f"[{cam.name}] Check-in: #{event.track_id} {event.class_name}"
                        )
                elif detector.model is None:
                    detections = _demo_tracked_objects(dummy_positions[cam.name])
                    dummy_positions[cam.name] += 1
                    last_tracked_count = len(detections)
                else:
                    detections = detector.detect(frame)
                    last_tracked_count = 0

                last_detection_count = len(detections)

                draw_detections(frame, detections, box_thickness, font_scale)
                if display_cfg.get("show_fps", True):
                    draw_fps(frame, fps)
                draw_counts(frame, detections)

                if warehouse_enabled and warehouse_db is not None:
                    line = warehouse_cfg.get(
                        "counting_line", {"x1": 100, "y1": 300, "x2": 900, "y2": 300}
                    )
                    count_mode = warehouse_cfg.get("mode", "appearance")
                    if count_mode == "line":
                        draw_counting_line(frame, line)
                    _process_warehouse_counting(
                        camera_name=cam.name,
                        detections=detections,
                        warehouse_counter=warehouse_counters[cam.name],
                        warehouse_db=warehouse_db,
                        confidence_threshold=warehouse_cfg.get("confidence_threshold", 0.5),
                        reviewed_unknown_ids=reviewed_unknown_ids,
                        count_unknown=warehouse_cfg.get("count_low_confidence_as_unknown", True),
                        count_mode=count_mode,
                    )

                if snapshot_saver is not None:
                    saved = snapshot_saver.maybe_save(cam.name, frame, detections)
                    for path in saved:
                        print(f"[{cam.name}] Snapshot saved: {path}")

                if live_feed_enabled:
                    _write_live_frame(snapshots_dir, cam, frame)

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
                    "warehouse_counting_enabled": warehouse_enabled,
                    "warehouse_counting_mode": warehouse_cfg.get("mode", "appearance")
                    if warehouse_enabled
                    else None,
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
        for cam in cameras:
            cam.release()
        if not args.no_display:
            cv2.destroyAllWindows()
        print("Stopped.")


def _demo_tracked_objects(frame_index: int) -> list[TrackedObject]:
    y = min(520, 170 + frame_index * 5)
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


def _write_live_frame(snapshots_dir: str, cam, frame) -> None:
    try:
        ok, jpg = cv2.imencode(".jpg", frame)
        if not ok:
            return

        data = jpg.tobytes()
        latest_path = Path(snapshots_dir) / "latest.jpg"
        latest_path.write_bytes(data)

        if cam.slot_number is not None:
            (Path(snapshots_dir) / f"latest_slot_{cam.slot_number}.jpg").write_bytes(data)

        (Path(snapshots_dir) / f"latest_{_safe_live_feed_name(cam.name)}.jpg").write_bytes(data)
    except Exception:
        pass


def _safe_live_feed_name(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(value)).strip("_") or "camera"


def _process_warehouse_counting(
    camera_name: str,
    detections,
    warehouse_counter,
    warehouse_db: WarehouseDB,
    confidence_threshold: float,
    reviewed_unknown_ids: set[tuple[str, int]],
    count_unknown: bool,
    count_mode: str,
) -> None:
    tracked = [det for det in detections if hasattr(det, "track_id")]
    if not tracked:
        return

    for det in tracked:
        review_key = (camera_name, det.track_id)
        if (
            count_unknown
            and det.confidence < confidence_threshold
            and review_key not in reviewed_unknown_ids
        ):
            reviewed_unknown_ids.add(review_key)
            warehouse_db.record_unknown_item(
                tracking_id=det.track_id,
                confidence=det.confidence,
                screenshot_path=None,
                camera_id=camera_name,
            )

    countable = [det for det in tracked if det.confidence >= confidence_threshold]
    for event in warehouse_counter.update(countable):
        stock = warehouse_db.record_movement(
            product_name=event.product_name,
            direction=event.direction,
            camera_id=event.camera_id,
            tracking_id=event.tracking_id,
            confidence=event.confidence,
        )
        action = "recognized" if count_mode == "appearance" else f"crossed {event.direction}"
        print(
            f"[{event.camera_id}] {event.product_name} ID={event.tracking_id} "
            f"{action} | stock {event.product_name} = {stock}"
        )


if __name__ == "__main__":
    main()
