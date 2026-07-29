"""Pure corrective-wiring policies shared by the detector runtime and tests."""

from __future__ import annotations

from typing import Any, Iterable


OBJECT_PROPOSAL_CLASS = "object proposal"


def is_object_proposal(detection: Any) -> bool:
    class_name = str(getattr(detection, "class_name", "") or "").strip().lower()
    object_type = str(getattr(detection, "object_type", "") or "").strip().lower()
    return OBJECT_PROPOSAL_CLASS in {class_name, object_type}


def is_verified_business_detection(detection: Any) -> bool:
    """Allow named detector classes, but require recognition for proposals."""
    if not is_object_proposal(detection):
        return True
    return bool(str(getattr(detection, "inventory_name", "") or "").strip())


def business_detections(detections: Iterable[Any]) -> list[Any]:
    return [
        detection
        for detection in detections
        if is_verified_business_detection(detection)
    ]


def detection_accounting(detections: Iterable[Any]) -> dict[str, int]:
    items = list(detections)
    return {
        "proposal_count": sum(1 for item in items if is_object_proposal(item)),
        "verified_detection_count": sum(
            1 for item in items if is_verified_business_detection(item)
        ),
    }


def runtime_health_fields(
    *,
    tracking_engine: str,
    tracker_config_applied: bool,
    active_model: str | None,
    frame_width: int | None,
    frame_height: int | None,
    inference_by_camera: dict[str, dict[str, Any]],
    proposal_count_by_camera: dict[str, int],
    verified_detection_count_by_camera: dict[str, int],
) -> dict[str, Any]:
    return {
        "tracking_engine": tracking_engine,
        "tracker_config_applied": bool(tracker_config_applied),
        "active_model": active_model,
        "frame_width": frame_width,
        "frame_height": frame_height,
        "inference_fps": round(
            sum(
                max(0.0, float(metrics.get("inference_fps") or 0.0))
                for metrics in inference_by_camera.values()
            ),
            3,
        ),
        "proposal_count": sum(
            max(0, int(count)) for count in proposal_count_by_camera.values()
        ),
        "verified_detection_count": sum(
            max(0, int(count))
            for count in verified_detection_count_by_camera.values()
        ),
    }


def audit_snapshot_triggers(
    trigger_classes: Iterable[str] | None,
    active_prompts: Iterable[str] | None,
) -> dict[str, Any]:
    configured = _clean_names(trigger_classes)
    prompts = _clean_names(active_prompts)
    prompt_keys = {value.lower() for value in prompts}
    reachable = [value for value in configured if value.lower() in prompt_keys]
    unreachable = [value for value in configured if value.lower() not in prompt_keys]
    return {
        "status": "mismatch" if unreachable else "ok",
        "configured_triggers": configured,
        "active_detector_prompts": prompts,
        "reachable_triggers": reachable,
        "unreachable_triggers": unreachable,
    }


def audit_warehouse_coordinates(
    engine_config: dict[str, Any],
    frame_dimensions_by_camera: dict[str, dict[str, int]],
) -> dict[str, Any]:
    """Report coordinates outside real frames without modifying configuration."""
    if not frame_dimensions_by_camera:
        return {
            "status": "pending",
            "mismatch_count": 0,
            "cameras": {},
        }

    camera_audits: dict[str, Any] = {}
    mismatch_count = 0
    for camera_name, dimensions in frame_dimensions_by_camera.items():
        width = max(0, int(dimensions.get("width") or 0))
        height = max(0, int(dimensions.get("height") or 0))
        mismatches: list[str] = []
        line_results = []

        configured_lines: list[tuple[str, Any]] = []
        default_line = engine_config.get("counting_line")
        if default_line:
            configured_lines.append(("default", default_line))
        for configured_camera, line in (engine_config.get("counting_lines") or {}).items():
            if str(configured_camera) == str(camera_name):
                configured_lines.append((str(configured_camera), line))

        for label, line in configured_lines:
            outside = _line_outside_frame(line, width, height)
            if outside:
                mismatches.append(
                    f"counting_line[{label}] outside {width}x{height}: {outside}"
                )
            line_results.append(
                {
                    "name": label,
                    "coordinates": dict(line),
                    "compatible": not outside,
                    "outside_coordinates": outside,
                }
            )

        zone_results = []
        for zone in engine_config.get("zones") or []:
            zone_name = str(zone.get("name") or "unnamed")
            polygon = zone.get("polygon") or []
            outside = _polygon_outside_frame(polygon, width, height)
            if outside:
                mismatches.append(
                    f"zone[{zone_name}] outside {width}x{height}: {outside}"
                )
            zone_results.append(
                {
                    "name": zone_name,
                    "polygon": polygon,
                    "compatible": not outside,
                    "outside_points": outside,
                }
            )

        mismatch_count += len(mismatches)
        camera_audits[str(camera_name)] = {
            "frame_width": width,
            "frame_height": height,
            "counting_lines": line_results,
            "zones": zone_results,
            "mismatches": mismatches,
        }

    return {
        "status": "mismatch" if mismatch_count else "ok",
        "mismatch_count": mismatch_count,
        "cameras": camera_audits,
    }


def _clean_names(values: Iterable[str] | None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        normalized = " ".join(str(value).split()).strip()
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            cleaned.append(normalized)
    return cleaned


def _line_outside_frame(
    line: dict[str, Any], width: int, height: int
) -> list[dict[str, int]]:
    outside = []
    for x_key, y_key in (("x1", "y1"), ("x2", "y2")):
        x = int(line.get(x_key, 0))
        y = int(line.get(y_key, 0))
        if not _point_inside_frame(x, y, width, height):
            outside.append({"x": x, "y": y})
    return outside


def _polygon_outside_frame(
    polygon: Iterable[Iterable[Any]], width: int, height: int
) -> list[list[int]]:
    outside: list[list[int]] = []
    for point in polygon:
        values = list(point)
        if len(values) < 2:
            continue
        x, y = int(values[0]), int(values[1])
        if not _point_inside_frame(x, y, width, height):
            outside.append([x, y])
    return outside


def _point_inside_frame(x: int, y: int, width: int, height: int) -> bool:
    # Polygon boundaries may equal width/height; values beyond them mismatch.
    return width > 0 and height > 0 and 0 <= x <= width and 0 <= y <= height
