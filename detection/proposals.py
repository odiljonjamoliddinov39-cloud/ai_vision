"""Class-agnostic object proposals for learned-product recognition."""

from __future__ import annotations

import os


def box_iou(first: tuple[int, int, int, int], second: tuple[int, int, int, int]) -> float:
    x1, y1 = max(first[0], second[0]), max(first[1], second[1])
    x2, y2 = min(first[2], second[2]), min(first[3], second[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    if not intersection:
        return 0.0
    first_area = max(1, (first[2] - first[0]) * (first[3] - first[1]))
    second_area = max(1, (second[2] - second[0]) * (second[3] - second[1]))
    return intersection / max(1, first_area + second_area - intersection)


def object_proposal_boxes(frame) -> list[tuple[int, int, int, int]]:
    import cv2

    height, width = frame.shape[:2]
    if height < 32 or width < 32:
        return []
    scale = min(1.0, 960.0 / max(height, width))
    working = cv2.resize(frame, (int(width * scale), int(height * scale))) if scale < 1 else frame
    gray = cv2.GaussianBlur(cv2.cvtColor(working, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    edges = cv2.morphologyEx(
        cv2.Canny(gray, 35, 110),
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9)),
        iterations=2,
    )
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    frame_area = float(gray.shape[0] * gray.shape[1])
    ranked = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = float(w * h)
        ratio = area / frame_area
        fill = float(cv2.contourArea(contour)) / max(1.0, area)
        aspect = w / max(1.0, float(h))
        if ratio < 0.0015 or ratio > 0.65 or w < 24 or h < 24 or fill < 0.08 or not 0.15 <= aspect <= 6.5:
            continue
        inverse = 1.0 / scale
        pad_x, pad_y = max(4, int(w * 0.04)), max(4, int(h * 0.04))
        ranked.append(
            (
                ratio * (0.5 + fill),
                (
                    max(0, int((x - pad_x) * inverse)),
                    max(0, int((y - pad_y) * inverse)),
                    min(width, int((x + w + pad_x) * inverse)),
                    min(height, int((y + h + pad_y) * inverse)),
                ),
            )
        )
    maximum = max(1, min(int(os.getenv("LIVE_PROPOSAL_MAX_PER_CAMERA", "12")), 30))
    selected = []
    for _, box in sorted(ranked, reverse=True):
        if any(box_iou(box, existing) >= 0.40 for existing in selected):
            continue
        selected.append(box)
        if len(selected) >= maximum:
            break
    return selected
