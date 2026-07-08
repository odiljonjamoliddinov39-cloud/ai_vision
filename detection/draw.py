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
        spatial_label = _spatial_label(det)

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, box_thickness)

        labels = [label] + ([spatial_label] if spatial_label else [])
        text_sizes = [
            cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)[0]
            for text in labels
        ]
        text_w = max(size[0] for size in text_sizes)
        text_h = max(size[1] for size in text_sizes)
        panel_height = (text_h + 5) * len(labels) + 3
        label_x = min(max(0, x1), max(0, frame.shape[1] - text_w - 6))
        panel_top = max(0, y1 - panel_height)
        cv2.rectangle(
            frame,
            (label_x, panel_top),
            (label_x + text_w + 6, min(frame.shape[0] - 1, panel_top + panel_height)),
            color,
            -1,
        )
        for index, text in enumerate(labels):
            cv2.putText(
                frame,
                text,
                (label_x + 3, panel_top + text_h + 2 + index * (text_h + 5)),
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
    counts = Counter()
    for detection in detections:
        name = getattr(detection, "inventory_name", None) or detection.class_name
        counts[name] += max(1, int(getattr(detection, "quantity", 1)))
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


def _spatial_label(detection) -> str | None:
    width = getattr(detection, "width_m", None)
    height = getattr(detection, "height_m", None)
    depth = getattr(detection, "depth_m", None)
    distance = getattr(detection, "distance_m", None)
    if None in (width, height, depth, distance):
        return None

    quantity = max(1, int(getattr(detection, "quantity", 1)))
    object_type = getattr(detection, "object_type", None) or "object"
    estimated = f"~{width:.2f}x{height:.2f}x{depth:.2f}m @ {distance:.1f}m"
    return f"x{quantity} {object_type} | {estimated}"


def draw_counting_line(frame, line: dict, label: str = "COUNT LINE"):
    start = (int(line["x1"]), int(line["y1"]))
    end = (int(line["x2"]), int(line["y2"]))
    cv2.line(frame, start, end, (0, 255, 255), 2)
    cv2.putText(
        frame,
        label,
        (start[0], max(20, start[1] - 10)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return frame
