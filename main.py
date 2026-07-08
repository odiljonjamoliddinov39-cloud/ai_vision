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
  9. Counts objects inside warehouse zones and recognizes
     item-in / item-out events, flagging suspicious removals
     (after-hours, unattended, bulk).                          (Phase 5)

Cameras are read by a background grabber thread that always hands over
the *newest* frame, so slow YOLO inference no longer causes the live
view to lag behind reality (frames that can't be processed in time are
dropped instead of queueing up).

Run:
    python main.py
    python main.py --config config/config.yaml
    python main.py --no-display

Press "q" in any camera window to quit.
"""

from __future__ import annotations

import argparse
import json
import time

import cv2
import yaml
import os

from cameras.camera import load_cameras
from detection.detector import Detector
from detection.draw import draw_detections, draw_fps, draw_counts, draw_zones
from detection.snapshot import SnapshotSaver
from database.event_log import EventLogger
from database.tracking_db import TrackingDB
from tracking.tracker import ObjectTracker
from tracking.presence import PresenceTracker
from tracking.zones import ZoneMonitor, load_zones
from tracking.warehouse import WarehouseEventDetector


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def write_atomic(path: str, data: bytes) -> None:
    """Write via a temp file + rename so readers (the MJPEG endpoint)
    never see a half-written JPEG."""
    tmp_path = path + ".tmp"
    with open(tmp_path, "wb") as f:
        f.write(data)
    os.replace(tmp_path, path)


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
    args = parser.parse_args()

    config = load_config(args.config)
    display_cfg = config.get("display", {})

    # --- Cameras (FR-1) ---
    cameras = load_cameras(config["cameras"])
    if not cameras:
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
    )
    print("Model loaded. Starting live detection... (press 'q' to quit)")

    # --- Tracking (Phase 3) + occupancy (Phase 4) ---
    track_cfg = config.get("tracking", {})
    tracking_enabled = track_cfg.get("enabled", True)
    object_tracker = None
    presence_tracker = None
    tracking_db = None

    if tracking_enabled:
        object_tracker = ObjectTracker(
            model=detector.model,
            confidence_threshold=det_cfg.get("confidence_threshold", 0.5),
            device=det_cfg.get("device", "cpu"),
            classes=track_cfg.get("classes", det_cfg.get("classes")),
            tracker_config=track_cfg.get("tracker_config", "bytetrack.yaml"),
        )
        presence_tracker = PresenceTracker(
            grace_period_seconds=track_cfg.get("grace_period_seconds", 5.0)
        )
        tracking_db = TrackingDB(db_path=track_cfg.get("db_path", "database/tracking.db"))
        print(
            f"Tracking enabled ({track_cfg.get('tracker_config', 'bytetrack.yaml')}), "
            f"grace period {track_cfg.get('grace_period_seconds', 5.0)}s."
        )

    # --- Warehouse zones + event recognition (Phase 5) ---
    wh_cfg = config.get("warehouse", {})
    zone_monitor = None
    warehouse_detector = None
    zone_status_path = wh_cfg.get("status_file", "logs/zone_status.json")
    last_status_write = 0.0

    if tracking_enabled and wh_cfg.get("enabled", True):
        default_camera = cameras[0].name
        zones = load_zones(config.get("zones"), default_camera=default_camera)
        if not zones:
            # No zones configured: watch the whole frame of every camera.
            zones = load_zones(
                [{"name": f"{cam.name} area", "camera": cam.name} for cam in cameras]
            )
        zone_monitor = ZoneMonitor(
            zones,
            min_frames=wh_cfg.get("min_frames", 3),
            lost_after_seconds=track_cfg.get("grace_period_seconds", 5.0),
        )
        warehouse_detector = WarehouseEventDetector(
            item_classes=wh_cfg.get("item_classes"),
            person_class=wh_cfg.get("person_class", "person"),
            working_hours=wh_cfg.get("working_hours"),
            bulk_removal_count=wh_cfg.get("bulk_removal_count", 3),
            bulk_removal_window_seconds=wh_cfg.get("bulk_removal_window_seconds", 60.0),
            flag_unattended=wh_cfg.get("flag_unattended", True),
        )
        os.makedirs(os.path.dirname(zone_status_path) or ".", exist_ok=True)
        print(
            f"Warehouse events enabled: zones={[z.name for z in zones]}, "
            f"items={sorted(warehouse_detector.item_classes)}"
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
    jpeg_quality = int(display_cfg.get("live_feed_jpeg_quality", 80))

    # --- Event log (FR-6) ---
    log_cfg = config.get("logging", {})
    event_logger = None
    if log_cfg.get("enabled", True):
        event_logger = EventLogger(
            log_dir=log_cfg.get("log_dir", "logs"),
            log_file=log_cfg.get("log_file", "events.log"),
        )

    box_thickness = display_cfg.get("box_thickness", 2)
    font_scale = display_cfg.get("font_scale", 0.6)
    window_prefix = display_cfg.get("window_prefix", "AI Vision -")

    prev_time = time.time()

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

                if object_tracker is not None:
                    detections = object_tracker.update(frame)
                    check_ins = presence_tracker.update(cam.name, detections, now)
                    for event in check_ins:
                        tracking_db.record_check_in(
                            event.track_id, event.camera_name, event.class_name
                        )
                        print(
                            f"[{cam.name}] Check-in: #{event.track_id} {event.class_name}"
                        )
                else:
                    detections = detector.detect(frame)

                # --- zone events (Phase 5) ---
                if zone_monitor is not None:
                    h, w = frame.shape[:2]
                    zone_events = zone_monitor.update(
                        cam.name, detections, now, frame_size=(w, h)
                    )
                    for wh_event in warehouse_detector.process(zone_events):
                        tracking_db.record_zone_event(
                            zone_name=wh_event.zone_name,
                            camera_name=wh_event.camera_name,
                            track_id=wh_event.track_id,
                            class_name=wh_event.class_name,
                            event_type=wh_event.event_type,
                            suspicious=wh_event.suspicious,
                            reasons=wh_event.reasons,
                            persons_in_zone=wh_event.persons_in_zone,
                        )
                        flag = (
                            f"  << SUSPICIOUS ({', '.join(wh_event.reasons)})"
                            if wh_event.suspicious
                            else ""
                        )
                        print(
                            f"[{cam.name}] {wh_event.event_type}: #{wh_event.track_id} "
                            f"{wh_event.class_name} in {wh_event.zone_name}{flag}"
                        )

                draw_detections(frame, detections, box_thickness, font_scale)
                if zone_monitor is not None:
                    cam_zones = [z for z in zone_monitor.zones if z.camera_name == cam.name]
                    draw_zones(frame, cam_zones, zone_monitor.counts())
                if display_cfg.get("show_fps", True):
                    draw_fps(frame, fps)
                draw_counts(frame, detections)

                if snapshot_saver is not None:
                    saved = snapshot_saver.maybe_save(cam.name, frame, detections)
                    for path in saved:
                        print(f"[{cam.name}] Snapshot saved: {path}")

                # write latest frame for live feed (MJPEG)
                if live_feed_enabled:
                    try:
                        ok, jpg = cv2.imencode(
                            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]
                        )
                        if ok:
                            write_atomic(
                                os.path.join(snapshots_dir, "latest.jpg"),
                                jpg.tobytes(),
                            )
                    except Exception:
                        pass

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

            if zone_monitor is not None:
                for wh_event in warehouse_detector.process(zone_monitor.expire(now)):
                    tracking_db.record_zone_event(
                        zone_name=wh_event.zone_name,
                        camera_name=wh_event.camera_name,
                        track_id=wh_event.track_id,
                        class_name=wh_event.class_name,
                        event_type=wh_event.event_type,
                        suspicious=wh_event.suspicious,
                        reasons=wh_event.reasons,
                        persons_in_zone=wh_event.persons_in_zone,
                    )
                    flag = (
                        f"  << SUSPICIOUS ({', '.join(wh_event.reasons)})"
                        if wh_event.suspicious
                        else ""
                    )
                    print(
                        f"[{wh_event.camera_name}] {wh_event.event_type}: "
                        f"#{wh_event.track_id} {wh_event.class_name} "
                        f"in {wh_event.zone_name}{flag}"
                    )

                # publish live zone counts for the API/dashboard (~1x per second)
                if now - last_status_write >= 1.0:
                    last_status_write = now
                    try:
                        status = {
                            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                            "zones": zone_monitor.counts(),
                        }
                        write_atomic(
                            zone_status_path,
                            json.dumps(status, indent=2).encode("utf-8"),
                        )
                    except Exception:
                        pass

            if not any_frame:
                # The grabber threads hand out each frame only once; a short
                # sleep is enough — a 1s sleep here would add visible lag.
                time.sleep(0.005)

            if not args.no_display and cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        for cam in cameras:
            cam.release()
        if not args.no_display:
            cv2.destroyAllWindows()
        print("Stopped.")


if __name__ == "__main__":
    main()
