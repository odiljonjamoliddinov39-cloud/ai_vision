"""
main.py

AI Vision Assistant entry point.

What this does:
  1. Reads frames published by Stream Manager.                (FR-1)
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

from cameras.camera import load_cameras
from streams.frame_source import load_processing_cameras
from detection.detector import Detector
from detection.scheduler import LatestFrameInferenceScheduler
from detection.camera_processor import CameraVisionProcessor
from detection.draw import draw_detections, draw_fps, draw_counts, draw_counting_line
from detection.spatial import SpatialAnalyzer
from detection.snapshot import SnapshotSaver
from database.event_log import EventLogger
from database.tracking_db import TrackingDB
from database.warehouse_db import WarehouseDB
from tracking.tracker import TrackedObject
from tracking.bytetrack_adapter import ByteTrackAdapter
from tracking.presence import PresenceTracker
from recognition.product_recognizer import ProductRecognizer
from warehouse_engine import WarehouseEngine


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _resolve_target_fps(value) -> float:
    """AUTO/zero means run continuously at sustainable hardware speed."""
    if value is None or str(value).strip().upper() == "AUTO":
        return 0.0
    target = float(value)
    return max(0.0, target)


def _performance_metrics() -> dict:
    metrics = {"cpu_usage_percent": None, "gpu_usage_percent": None}
    try:
        import psutil

        metrics["cpu_usage_percent"] = round(float(psutil.cpu_percent()), 1)
    except Exception:
        pass
    try:
        import pynvml

        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        metrics["gpu_usage_percent"] = round(
            float(pynvml.nvmlDeviceGetUtilizationRates(handle).gpu), 1
        )
    except Exception:
        pass
    return metrics


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

    # --- Frame source (V2 stream-first architecture) ---
    #
    # The API server starts the Stream Manager and sets AI_VISION_STREAM_FIRST=1.
    # YOLO consumes the Stream Manager's cross-process frame buffers instead of
    # opening RTSP/NVR connections directly. Direct camera loading is reserved for an
    # explicit local developer override and is not used by the backend path.
    snap_cfg = config.get("snapshots", {})
    snapshots_dir = snap_cfg.get("save_dir", "snapshots")
    direct_camera_override = os.getenv("AI_VISION_ALLOW_DIRECT_CAMERA", "0") == "1"
    stream_first = os.getenv("AI_VISION_STREAM_FIRST", "1") != "0" or not direct_camera_override
    if stream_first:
        cameras = load_processing_cameras(config["cameras"], snapshot_dir=snapshots_dir)
    else:
        print("WARNING: direct camera mode is enabled for local development only.")
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
        iou_threshold=det_cfg.get("iou_threshold", 0.55),
        max_detections=det_cfg.get("max_detections", 300),
        compile_model=det_cfg.get("compile", False),
        fallback_model_path=det_cfg.get("fallback_model_path"),
    )
    if detector.model is None:
        print("Using deterministic dummy detector. Starting demo run...")
    else:
        model_health = detector.health()
        print(
            "Ultralytics model loaded: "
            f"{model_health['active_model']} on {model_health['device']}"
            + (" (fallback)" if model_health["fallback_used"] else "")
        )
        print("Starting live detection... (press 'q' to quit)")

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
    object_trackers = {}
    presence_tracker = None
    tracking_db = None

    if tracking_enabled and detector.model is not None:
        object_trackers = {
            cam.name: ByteTrackAdapter(
                camera_name=cam.name,
                tracker_config=track_cfg.get(
                    "tracker_config", "config/warehouse_bytetrack.yaml"
                ),
            )
            for cam in cameras
        }
        presence_tracker = PresenceTracker(
            grace_period_seconds=track_cfg.get("grace_period_seconds", 5.0)
        )
        tracking_db = TrackingDB(db_path=track_cfg.get("db_path", "database/tracking.db"))
        print(
            f"Tracking enabled ({track_cfg.get('tracker_config', 'bytetrack.yaml')}), "
            f"grace period {track_cfg.get('grace_period_seconds', 5.0)}s."
        )

    # --- Warehouse Intelligence Engine ---
    warehouse_cfg = config.get("warehouse_counting", {})
    engine_cfg = {**warehouse_cfg, **config.get("warehouse_engine", {})}
    warehouse_enabled = engine_cfg.get("enabled", warehouse_cfg.get("enabled", False))
    warehouse_db = None
    warehouse_engine = None
    if warehouse_enabled:
        warehouse_db = WarehouseDB(db_path=warehouse_cfg.get("db_path", "database/warehouse.db"))

        def accepted_movement_sink(event, detection):
            warehouse_db.record_movement(
                product_name=event.product_name,
                direction="IN" if event.inventory_delta > 0 else "OUT",
                camera_id=event.camera_id,
                tracking_id=getattr(detection, "track_id", None),
                confidence=event.confidence,
                quantity=abs(event.inventory_delta),
                object_type=getattr(detection, "object_type", None),
                dimensions_m=(
                    getattr(detection, "width_m", None),
                    getattr(detection, "height_m", None),
                    getattr(detection, "depth_m", None),
                )
                if all(
                    getattr(detection, field, None) is not None
                    for field in ("width_m", "height_m", "depth_m")
                )
                else None,
                distance_m=getattr(detection, "distance_m", None),
                quantity_grid=getattr(detection, "quantity_grid", (1, 1, 1)),
                measurement_method=getattr(detection, "method", None),
            )
        warehouse_engine = WarehouseEngine(
            {
                **engine_cfg,
                "db_path": engine_cfg.get("engine_db_path", "database/warehouse_engine.db"),
                "minimum_confidence": engine_cfg.get(
                    "minimum_confidence",
                    warehouse_cfg.get("confidence_threshold", 0.8),
                ),
            },
            movement_sink=accepted_movement_sink,
        )
        print(
            "Warehouse Intelligence Engine enabled. "
            f"Engine DB: {warehouse_engine.database.path}; "
            f"compatibility stock DB: {warehouse_db.db_path}"
        )

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
    snapshot_saver = None
    if snap_cfg.get("enabled", True):
        snapshot_saver = SnapshotSaver(
            save_dir=snap_cfg.get("save_dir", "snapshots"),
            trigger_classes=snap_cfg.get("trigger_classes"),
            cooldown_seconds=snap_cfg.get("cooldown_seconds", 5),
        )
    # ensure snapshots dir exists for live feed
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
    last_frame_seen_at = 0.0
    last_detection_count = 0
    last_tracked_count = 0
    last_frame_at = None
    last_spatial_objects = []
    last_spatial_objects_by_camera = {}
    last_detections_by_camera = {}
    inference_by_camera = {}

    prev_time = time.time()
    frame_number = 0
    dummy_positions = {cam.name: 0 for cam in cameras}

    # Capture stays independent from inference. Bounded per-camera queues keep
    # latency controlled while allowing FIFO operation when completeness matters.
    target_detection_fps = _resolve_target_fps(det_cfg.get("target_fps", "AUTO"))
    min_detection_interval = 1.0 / target_detection_fps if target_detection_fps > 0 else 0.0
    stale_after_ms = int(det_cfg.get("stale_after_ms", 3000))
    max_concurrent_cameras = int(det_cfg.get("max_concurrent_cameras", 0) or 0)
    inference_camera_names = (
        {cam.name for cam in cameras[:max_concurrent_cameras]}
        if max_concurrent_cameras > 0
        else {cam.name for cam in cameras}
    )
    last_detection_at = {cam.name: 0.0 for cam in cameras}
    camera_frame_counts = {cam.name: 0 for cam in cameras}
    camera_stream_interrupted = {cam.name: False for cam in cameras}
    camera_fps_started_at = time.monotonic()
    camera_processors = {
        cam.name: CameraVisionProcessor(
            cam.name, detector, object_trackers.get(cam.name)
        )
        for cam in cameras
        if cam.name in inference_camera_names and detector.model is not None
    }
    processors = {
        name: processor.process for name, processor in camera_processors.items()
    }
    inference_scheduler = (
        LatestFrameInferenceScheduler(
            processors,
            queue_size=det_cfg.get("queue_size", 5),
            queue_mode=det_cfg.get("queue_mode", "latest"),
            workers=det_cfg.get("detector_workers", "AUTO"),
            device=detector.device,
        )
        if processors
        else None
    )

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
                    camera_stream_interrupted[cam.name] = True
                    continue
                if camera_stream_interrupted[cam.name]:
                    processor = camera_processors.get(cam.name)
                    if processor is not None:
                        processor.reset("camera_reconnect")
                    camera_stream_interrupted[cam.name] = False
                any_frame = True
                last_frame_seen_at = now
                frames_read += 1
                camera_frame_counts[cam.name] += 1
                last_frame_at = datetime.now().isoformat(timespec="seconds")
                frame_at = time.time()

                should_infer = (
                    cam.name in inference_camera_names
                    and (
                        min_detection_interval <= 0
                        or now - last_detection_at.get(cam.name, 0.0) >= min_detection_interval
                    )
                )

                inference_result = None
                if inference_scheduler is not None and cam.name in processors:
                    if should_infer:
                        inference_scheduler.submit(cam.name, frame, frame_at=frame_at)
                        last_detection_at[cam.name] = now
                    inference_result = inference_scheduler.take_result(cam.name)

                if inference_result is not None:
                    frame = inference_result.frame
                    downstream_objects, tracked_objects = _route_inference_objects(
                        inference_result,
                        tracking_enabled=cam.name in object_trackers,
                    )
                    inference_age_ms = max(
                        0, round((time.time() - inference_result.inference_at) * 1000)
                    )
                    frame_age_ms = max(
                        0, round((time.time() - inference_result.frame_at) * 1000)
                    )
                    result_is_stale = frame_age_ms > stale_after_ms
                    camera_elapsed = max(0.001, time.monotonic() - camera_fps_started_at)
                    inference_by_camera[cam.name] = {
                        **inference_scheduler.metrics(cam.name),
                        "camera_fps": round(camera_frame_counts[cam.name] / camera_elapsed, 3),
                        "frame_at": datetime.fromtimestamp(
                            inference_result.frame_at
                        ).isoformat(timespec="milliseconds"),
                        "inference_at": datetime.fromtimestamp(
                            inference_result.inference_at
                        ).isoformat(timespec="milliseconds"),
                        "frame_age_ms": frame_age_ms,
                        "inference_age_ms": inference_age_ms,
                        "stale": result_is_stale,
                        "error": inference_result.error,
                    }
                elif detector.model is None:
                    tracked_objects = _demo_tracked_objects(dummy_positions[cam.name])
                    downstream_objects = tracked_objects
                    dummy_positions[cam.name] += 1
                    last_tracked_count = len(tracked_objects)
                    result_is_stale = False
                else:
                    metrics = (
                        inference_scheduler.metrics(cam.name)
                        if inference_scheduler is not None and cam.name in processors
                        else {
                            "queue_depth": 0,
                            "dropped_frames": 0,
                            "inference_fps": 0.0,
                            "inference_age_ms": None,
                        }
                    )
                    camera_elapsed = max(0.001, time.monotonic() - camera_fps_started_at)
                    inference_by_camera[cam.name] = {
                        **metrics,
                        "camera_fps": round(camera_frame_counts[cam.name] / camera_elapsed, 3),
                        "frame_at": datetime.fromtimestamp(frame_at).isoformat(
                            timespec="milliseconds"
                        ),
                        "frame_age_ms": 0,
                        "stale": True,
                        "error": None,
                    }
                    last_detections_by_camera[cam.name] = []
                    continue

                if cam.name in object_trackers:
                    last_tracked_count = len(tracked_objects)
                    check_ins = presence_tracker.update(
                        cam.name, tracked_objects, inference_result.inference_at
                    )
                    for event in check_ins:
                        tracking_db.record_check_in(
                            event.track_id, event.camera_name, event.class_name
                        )
                        print(
                            f"[{cam.name}] Check-in: #{event.track_id} {event.class_name}"
                        )
                else:
                    last_tracked_count = 0

                last_detection_count = len(downstream_objects)
                if product_recognizer is not None:
                    product_recognizer.annotate(cam.name, frame, downstream_objects)
                # Class-agnostic proposals are observations, never inventory by
                # themselves. Only a learned catalog fingerprint may promote a
                # tracked proposal into a countable warehouse object.
                for detection in downstream_objects:
                    if (
                        detection.class_name == "object proposal"
                        and getattr(detection, "inventory_name", None)
                    ):
                        detection.confidence = max(float(detection.confidence), 0.85)

                if spatial_analyzer is not None:
                    measurements = spatial_analyzer.enrich(frame, downstream_objects)
                    last_spatial_objects = [
                        {
                            **measurement.__dict__,
                            "quantity_grid": list(measurement.quantity_grid),
                        }
                        for measurement in measurements
                    ]
                    last_spatial_objects_by_camera[cam.name] = last_spatial_objects

                last_detections_by_camera[cam.name] = [
                    _serialize_detection(obj, frame) for obj in downstream_objects
                ]

                draw_detections(frame, downstream_objects, box_thickness, font_scale)
                if display_cfg.get("show_fps", True):
                    draw_fps(frame, fps)
                draw_counts(frame, downstream_objects)

                if warehouse_engine is not None and not result_is_stale:
                    line = engine_cfg.get(
                        "counting_line", {"x1": 100, "y1": 300, "x2": 900, "y2": 300}
                    )
                    if line:
                        draw_counting_line(frame, line)
                    learned_detections = [
                        detection
                        for detection in downstream_objects
                        if getattr(detection, "inventory_name", None)
                    ]
                    engine_events = warehouse_engine.process(
                        camera_id=cam.name,
                        detections=learned_detections,
                        timestamp=inference_result.inference_at,
                    )
                    for engine_event in engine_events:
                        if engine_event.inventory_delta:
                            print(
                                f"[{cam.name}] {engine_event.event_type}: "
                                f"{engine_event.object_id} {engine_event.product_name} "
                                f"delta={engine_event.inventory_delta}"
                            )

                if snapshot_saver is not None:
                    saved = snapshot_saver.maybe_save(
                        cam.name, frame, downstream_objects
                    )
                    for path in saved:
                        print(f"[{cam.name}] Snapshot saved: {path}")

                if live_feed_enabled and not stream_first:
                    _write_live_frame(
                        snapshots_dir,
                        cam,
                        frame,
                        width=int(display_cfg.get("live_frame_width", 480)),
                        jpeg_quality=int(display_cfg.get("live_frame_jpeg_quality", 42)),
                    )

                if event_logger is not None:
                    event_logger.log_detections(cam.name, downstream_objects)

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

            frames_recent = last_frame_seen_at > 0 and (time.time() - last_frame_seen_at) < max(
                5.0, min_detection_interval * 3.0
            )

            if not any_frame and not frames_recent:
                print("No frames available from any camera. Retrying...")
                time.sleep(1)
            elif not any_frame:
                time.sleep(0.05)

            _write_detection_health(
                health_path,
                {
                    "state": "running",
                    "error": None
                    if any_frame or frames_recent
                    else "No frames available from any camera.",
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
                    "detector": detector.health(),
                    "tracking_enabled": bool(object_trackers) or detector.model is None,
                    "tracking_by_camera": {
                        name: tracker.health() for name, tracker in object_trackers.items()
                    },
                    "warehouse_counting_enabled": warehouse_enabled,
                    "warehouse_counting_mode": warehouse_cfg.get("mode", "appearance")
                    if warehouse_enabled
                    else None,
                    "product_recognition_enabled": product_recognizer is not None,
                    "product_recognition_provider": recognition_cfg.get("provider")
                    if product_recognizer is not None
                    else None,
                    "spatial_analysis_enabled": spatial_analyzer is not None,
                    "last_spatial_objects": last_spatial_objects,
                    "last_spatial_objects_by_camera": last_spatial_objects_by_camera,
                    "last_detections_by_camera": last_detections_by_camera,
                    "inference_by_camera": inference_by_camera,
                    "performance": _performance_metrics(),
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
        if inference_scheduler is not None:
            inference_scheduler.close()
        for cam in cameras:
            cam.release()
        if product_recognizer is not None:
            product_recognizer.close()
        if not args.no_display:
            cv2.destroyAllWindows()
        print("Stopped.")


def _demo_tracked_objects(frame_index: int) -> list[TrackedObject]:
    y = min(520, 170 + frame_index * 5)
    return [TrackedObject(track_id=1, class_name="box", confidence=0.95, box=(430, y, 530, y + 80))]


def _serialize_detection(det, frame) -> dict:
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = getattr(det, "box", (0, 0, 0, 0))
    payload = {
        "timestamp": datetime.now().isoformat(timespec="milliseconds"),
        "frame_width": width,
        "frame_height": height,
        "class_id": getattr(det, "class_id", None),
        "class_name": getattr(det, "class_name", "object"),
        "inventory_name": getattr(det, "inventory_name", None),
        "confidence": float(getattr(det, "confidence", 0.0)),
        "track_id": getattr(det, "track_id", None),
        "bbox": {
            "x1": float(x1),
            "y1": float(y1),
            "x2": float(x2),
            "y2": float(y2),
        },
    }
    for field in (
        "object_type",
        "quantity",
        "quantity_grid",
        "width_m",
        "height_m",
        "depth_m",
        "distance_m",
        "method",
    ):
        if hasattr(det, field):
            value = getattr(det, field)
            payload[field] = list(value) if field == "quantity_grid" else value
    return payload


def _route_inference_objects(
    inference_result, tracking_enabled: bool
) -> tuple[list, list | None]:
    """Return the scheduler output unchanged for all downstream consumers.

    A camera processor with tracking enabled has already run ByteTrack, so its
    result is the final tracked-object list. With tracking disabled, the same
    result contains raw detections and must remain usable by non-tracking
    consumers without inventing track IDs.
    """
    if tracking_enabled:
        tracked_objects = inference_result.detections
        return tracked_objects, tracked_objects
    raw_detections = inference_result.detections
    return raw_detections, None


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
