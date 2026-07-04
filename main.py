"""
main.py

AI Vision Assistant - Phase 1 MVP entry point.

What this does (Version 0.1 milestone + Phase 1 extras):
  1. Connects to one or more webcam / RTSP cameras.        (FR-1)
  2. Runs YOLO object detection on every frame.             (FR-2)
  3. Draws bounding boxes, labels, confidence, FPS.         (FR-3)
  4. Shows live per-class object counts.                    (FR-4)
  5. Saves snapshots when trigger classes appear.           (FR-5)
  6. Logs detection events to a text log.                   (FR-6)

Run:
    python main.py
    python main.py --config config/config.yaml
    python main.py --no-display

Press "q" in any camera window to quit.
"""

from __future__ import annotations

import argparse
import time

import cv2
import yaml
import os

from cameras.camera import load_cameras
from detection.detector import Detector
from detection.draw import draw_detections, draw_fps, draw_counts
from detection.snapshot import SnapshotSaver
from database.event_log import EventLogger


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="AI Vision Assistant - MVP")
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

                detections = detector.detect(frame)

                draw_detections(frame, detections, box_thickness, font_scale)
                if display_cfg.get("show_fps", True):
                    draw_fps(frame, fps)
                draw_counts(frame, detections)

                if snapshot_saver is not None:
                    saved = snapshot_saver.maybe_save(cam.name, frame, detections)
                    for path in saved:
                        print(f"[{cam.name}] Snapshot saved: {path}")

                # write latest frame for live feed (MJPEG / frequent updates)
                if live_feed_enabled:
                    try:
                        # overwrite latest.jpg for quick UI refresh
                        latest_path = os.path.join(snapshots_dir, "latest.jpg")
                        _, jpg = cv2.imencode('.jpg', frame)
                        with open(latest_path, 'wb') as f:
                            f.write(jpg.tobytes())
                    except Exception:
                        pass

                if event_logger is not None:
                    event_logger.log_detections(cam.name, detections)

                if not args.no_display:
                    cv2.imshow(f"{window_prefix} {cam.name}", frame)

            if not any_frame:
                print("No frames available from any camera. Retrying...")
                time.sleep(1)

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
