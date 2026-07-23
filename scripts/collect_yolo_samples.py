"""Collect YOLO training samples from AI Vision live snapshots.

This helper bootstraps a custom dataset from the current detector state:

- reads `logs/detection_health.json`
- finds the latest saved frame for each camera/slot
- converts matching detection bounding boxes into YOLO labels
- copies the frame and label file into `datasets/baget_box`

Generated labels are intentionally best-effort. Review them in a labeling tool
before final training when accuracy matters.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
from typing import Any


DEFAULT_MATCH_TERMS = [
    "baget box",
    "baguette box",
    "stack of baget boxes",
    "cardboard box",
    "carton box",
    "box",
    "stack of cardboard boxes",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def normalize(value: Any) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).split())


def safe_camera_name(value: Any) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(value or "")).strip("_") or "camera"


def read_health(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Detection health file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return data


def live_frame_paths(snapshot_dir: Path, slot: int | None = None, camera: str | None = None) -> list[Path]:
    paths: list[Path] = []
    if slot is not None:
        paths.append(snapshot_dir / f"latest_stream_slot_{slot}.jpg")
        paths.append(snapshot_dir / f"latest_slot_{slot}.jpg")
    if camera:
        safe_name = safe_camera_name(camera)
        paths.append(snapshot_dir / f"latest_stream_{safe_name}.jpg")
        paths.append(snapshot_dir / f"latest_{safe_name}.jpg")
    paths.append(snapshot_dir / "latest_stream.jpg")
    paths.append(snapshot_dir / "latest.jpg")
    return paths


def image_size(path: Path) -> tuple[int, int]:
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python-headless is required to collect YOLO samples.") from exc

    frame = cv2.imread(str(path))
    if frame is None:
        raise ValueError(f"Could not read image: {path}")
    height, width = frame.shape[:2]
    return int(width), int(height)


def detection_matches(detection: dict[str, Any], match_terms: list[str], min_confidence: float) -> bool:
    try:
        confidence = float(detection.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    if confidence < min_confidence:
        return False

    labels = [
        normalize(detection.get("inventory_name")),
        normalize(detection.get("class_name")),
        normalize(detection.get("object_type")),
    ]
    labels = [label for label in labels if label]
    terms = [normalize(term) for term in match_terms if normalize(term)]
    return any(label == term or label in term or term in label for label in labels for term in terms)


def yolo_box(detection: dict[str, Any], width: int, height: int) -> str | None:
    bbox = detection.get("bbox") or {}
    try:
        x1 = float(bbox["x1"])
        y1 = float(bbox["y1"])
        x2 = float(bbox["x2"])
        y2 = float(bbox["y2"])
    except (KeyError, TypeError, ValueError):
        return None

    x1 = max(0.0, min(float(width), x1))
    y1 = max(0.0, min(float(height), y1))
    x2 = max(0.0, min(float(width), x2))
    y2 = max(0.0, min(float(height), y2))
    if x2 <= x1 or y2 <= y1:
        return None

    x_center = ((x1 + x2) / 2.0) / width
    y_center = ((y1 + y2) / 2.0) / height
    box_width = (x2 - x1) / width
    box_height = (y2 - y1) / height
    return f"0 {x_center:.6f} {y_center:.6f} {box_width:.6f} {box_height:.6f}"


def camera_slots(health: dict[str, Any]) -> dict[str, int | None]:
    slots: dict[str, int | None] = {}
    for camera in health.get("cameras") or []:
        name = str(camera.get("name") or "")
        slot = camera.get("slot_number")
        try:
            slots[name] = int(slot) if slot is not None else None
        except (TypeError, ValueError):
            slots[name] = None
    return slots


def collect_samples(args: argparse.Namespace) -> list[Path]:
    health = read_health(Path(args.health))
    snapshot_dir = Path(args.snapshot_dir)
    dataset_dir = Path(args.dataset)
    image_dir = dataset_dir / "images" / args.split
    label_dir = dataset_dir / "labels" / args.split
    image_dir.mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)

    slots = camera_slots(health)
    by_camera = health.get("last_detections_by_camera") or {}
    if not isinstance(by_camera, dict):
        raise ValueError("Detection health does not contain last_detections_by_camera.")

    match_terms = [term.strip() for term in args.match.split(",") if term.strip()]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved: list[Path] = []
    for camera_name, detections in sorted(by_camera.items()):
        if args.camera and normalize(args.camera) not in normalize(camera_name):
            continue
        matched = [
            detection
            for detection in detections or []
            if isinstance(detection, dict)
            and detection_matches(detection, match_terms, args.min_confidence)
        ]
        if not matched:
            continue

        frame_path = next(
            (
                path
                for path in live_frame_paths(snapshot_dir, slot=slots.get(str(camera_name)), camera=str(camera_name))
                if path.exists()
            ),
            None,
        )
        if frame_path is None:
            print(f"Skipping {camera_name}: no live frame found.")
            continue

        width, height = image_size(frame_path)
        labels = [box for detection in matched if (box := yolo_box(detection, width, height))]
        if not labels:
            print(f"Skipping {camera_name}: matched detections had no valid bbox.")
            continue

        stem = f"{timestamp}_{safe_camera_name(camera_name)}"
        target_image = image_dir / f"{stem}{frame_path.suffix.lower()}"
        target_label = label_dir / f"{stem}.txt"
        counter = 2
        while target_image.exists() or target_label.exists():
            stem = f"{timestamp}_{safe_camera_name(camera_name)}_{counter}"
            target_image = image_dir / f"{stem}{frame_path.suffix.lower()}"
            target_label = label_dir / f"{stem}.txt"
            counter += 1

        if args.dry_run:
            print(f"Would save {target_image} with {len(labels)} labels.")
            continue

        shutil.copy2(frame_path, target_image)
        target_label.write_text("\n".join(labels) + "\n", encoding="utf-8")
        saved.append(target_image)
        print(f"Saved {target_image} with {len(labels)} labels.")
    return saved


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(description="Collect YOLO samples from current AI Vision detections.")
    parser.add_argument("--health", default=str(root / "logs" / "detection_health.json"))
    parser.add_argument("--snapshot-dir", default=str(root / "snapshots"))
    parser.add_argument("--dataset", default=str(root / "datasets" / "baget_box"))
    parser.add_argument("--split", choices=["train", "val"], default="train")
    parser.add_argument("--camera", default=None, help="Optional substring filter for camera name.")
    parser.add_argument("--match", default=",".join(DEFAULT_MATCH_TERMS), help="Comma-separated detection labels to collect.")
    parser.add_argument("--min-confidence", type=float, default=0.05)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    collected = collect_samples(parse_args())
    print(f"Collected {len(collected)} sample(s).")
