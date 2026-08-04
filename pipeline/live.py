"""Canonical RTSP -> detection/tracking -> rules -> events/database pipeline."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from events.engine import EventEngine
from rules import CountingRuleEngine, TrackObservation
from stream import LiveFrame
from utils.observability import ServiceError, log_operation


@dataclass(frozen=True)
class PipelineResult:
    detections: tuple
    event_ids: tuple[int, ...]
    latency_ms: float


class LiveVisionPipeline:
    """One execution path. Detector/tracker adapters are injected interfaces."""
    def __init__(self, *, tracker, rule_engine: CountingRuleEngine, event_engine: EventEngine,
                 database, pipeline_version: str, detector_version: str,
                 class_ids: dict[str, int], logger: logging.Logger | None = None):
        self.tracker = tracker
        self.rule_engine = rule_engine
        self.event_engine = event_engine
        self.database = database
        self.pipeline_version = pipeline_version
        self.detector_version = detector_version
        self.class_ids = class_ids
        self.logger = logger or logging.getLogger("ai_vision.pipeline")
        self._previous_centers: dict[int, tuple[float, float]] = {}
        self._track_ages: dict[int, int] = {}

    def process(self, frame: LiveFrame) -> PipelineResult:
        if not isinstance(frame, LiveFrame):
            raise ServiceError("INVALID_FRAME_SOURCE", "pipeline accepts LiveFrame only", "pipeline")
        started = time.perf_counter()
        try:
            tracked = tuple(self.tracker.update(frame.image))
            event_ids = []
            for item in tracked:
                center = ((item.box[0] + item.box[2]) / 2, (item.box[1] + item.box[3]) / 2)
                previous = self._previous_centers.get(item.track_id, center)
                age = self._track_ages.get(item.track_id, 0) + 1
                self._previous_centers[item.track_id] = center
                self._track_ages[item.track_id] = age
                now = datetime.now(timezone.utc)
                latency = (time.perf_counter() - started) * 1000
                class_id = self.class_ids.get(item.class_name, -1)
                record = {
                    "camera_id": frame.camera_id, "stream_id": frame.stream_id,
                    "frame_uuid": str(frame.frame_uuid), "frame_timestamp": frame.captured_at.isoformat(),
                    "detection_timestamp": now.isoformat(), "track_id": item.track_id,
                    "class_id": class_id, "confidence": item.confidence, "bbox": list(item.box),
                    "pipeline_version": self.pipeline_version, "detector_version": self.detector_version,
                    "recognition_source": "detector", "processing_latency_ms": latency,
                }
                detection_id = self.database.record_detection(self.event_engine.scan_run_id, record)
                observation = TrackObservation(
                    camera_id=frame.camera_id, stream_id=frame.stream_id, frame_uuid=str(frame.frame_uuid),
                    frame_timestamp=frame.captured_at, detection_timestamp=now, track_id=item.track_id,
                    class_id=class_id, confidence=item.confidence, center=center, previous_center=previous,
                    track_age=age, pipeline_version=self.pipeline_version,
                    detector_version=self.detector_version, recognition_source="detector",
                    processing_latency_ms=latency,
                )
                event = self.rule_engine.evaluate(observation)
                if event:
                    event_ids.append(self.event_engine.publish_count(detection_id, event, class_id))
            latency = (time.perf_counter() - started) * 1000
            log_operation(self.logger, request_id=str(frame.frame_uuid), camera_id=frame.camera_id,
                          frame_uuid=str(frame.frame_uuid), service="pipeline", processing_stage="complete",
                          latency_ms=latency, status="ok", detections=len(tracked), events=len(event_ids))
            return PipelineResult(tracked, tuple(event_ids), latency)
        except ServiceError:
            raise
        except Exception as exc:
            raise ServiceError.from_exception("PIPELINE_FAILED", "pipeline", exc, frame.camera_id) from exc
