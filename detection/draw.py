"""
detection/draw.py

Drawing helpers for bounding boxes, labels, FPS overlay, and
per-class object counts.

FR-3: Live Display
FR-4: Object Counting
"""

from __future__ import annotations

from collections import Counter

import cv2

# Deterministic color per class name so the same object type always
# gets the same box color across frames/cameras.
def _color_for_class(class_name: str) -> tuple:
    h = hash(class_name) % 0xFFFFFF
    return (h & 255, (h >> 8) & 255, (h >> 16) & 255)


def draw_detections(frame, detections, box_thickness: int = 2, font_scale: float = 0.6):
    for det in detections:
        x1, y1, x2, y2 = det.box
        color = _color_for_class(det.class_name)
        track_id = getattr(det, "track_id", None)
        prefix = f"#{track_id} " if track_id is not None else ""
        label = f"{prefix}{det.class_name} {det.confidence * 100:.0f}%"

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, box_thickness)

        (text_w, text_h), _ = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1
        )
        cv2.rectangle(
            frame, (x1, max(0, y1 - text_h - 8)), (x1 + text_w + 4, y1), color, -1
        )
        cv2.putText(
            frame,
            label,
            (x1 + 2, max(12, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
    return frame


def draw_fps(frame, fps: float):
    cv2.putText(
        frame,
        f"FPS: {fps:.1f}",
        (10, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 0),
        2,
        cv2.LINE_AA,
    )
    return frame


def draw_counts(frame, detections, origin=(10, 55)):
    counts = Counter(d.class_name for d in detections)
    x, y = origin
    for i, (class_name, count) in enumerate(sorted(counts.items())):
        cv2.putText(
            frame,
            f"{class_name}: {count}",
            (x, y + i * 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 0),
            2,
            cv2.LINE_AA,
        )
    return frame
