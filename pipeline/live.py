"""Canonical live path: detect -> track -> recognize -> rules -> count -> persist."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from counting import CountingEngine
from events.engine import EventEngine
from recognition import RecognitionEngine
from rules import ObjectRuleEngine, TrackObservation
from stream import LiveFrame
from utils.observability import ServiceError, log_operation


@dataclass(frozen=True)
class PipelineResult:
    detections: tuple
    event_ids: tuple[int, ...]
    latency_ms: float


class LiveVisionPipeline:
    """One-camera production pipeline with independently testable stages."""

    def __init__(self, *, camera_id: str, stream_id: str, processor,
                 rule_engine, event_engine: EventEngine, database,
                 pipeline_version: str, detector_version: str,
                 class_ids: dict[str, int], recognizer=None,
                 recognition_engine=None, counting_engine=None, logger=None):
        self.camera_id = camera_id
        self.stream_id = stream_id
        self.processor = processor
        self.recognition_engine = recognition_engine or RecognitionEngine(recognizer)
        self.rule_engine = getattr(rule_engine, "rules", rule_engine)
        if not isinstance(self.rule_engine, ObjectRuleEngine):
            raise TypeError("rule_engine must provide the rule-decision stage")
        self.counting_engine = counting_engine or getattr(
            rule_engine, "counter", CountingEngine(self.rule_engine.config)
        )
        self.event_engine = event_engine
        self.database = database
        self.pipeline_version = pipeline_version
        self.detector_version = detector_version
        self.class_ids = class_ids
        self.logger = logger or logging.getLogger("ai_vision.pipeline")
        self.last_result = PipelineResult((), (), 0.0)
        self._centers = {}
        self._ages = {}

    def process(self, image, frame_sequence: int, observed_at: float) -> list:
        frame = LiveFrame(
            self.camera_id, self.stream_id, uuid4(),
            datetime.fromtimestamp(observed_at, timezone.utc), image,
        )
        started = time.perf_counter()
        try:
            # The processor is detection + ByteTrack only. No business filter
            # is allowed before all model observations reach recognition.
            detections = list(self.processor.process(image, frame_sequence, observed_at))
            recognitions = self.recognition_engine.recognize(
                self.camera_id, image, detections
            )
            detection_ids: dict[int, int] = {}
            for index, (item, recognition) in enumerate(zip(detections, recognitions)):
                latency = (time.perf_counter() - started) * 1000
                class_id = int(getattr(
                    item, "class_id", self.class_ids.get(item.class_name, -1)
                ))
                record = {
                    "camera_id": frame.camera_id,
                    "stream_id": frame.stream_id,
                    "frame_uuid": str(frame.frame_uuid),
                    "frame_timestamp": frame.captured_at.isoformat(),
                    "detection_timestamp": datetime.now(timezone.utc).isoformat(),
                    "track_id": getattr(item, "track_id", None),
                    "class_id": class_id,
                    "confidence": float(item.confidence),
                    "bbox": list(item.box),
                    "pipeline_version": self.pipeline_version,
                    "detector_version": self.detector_version,
                    "recognition_source": recognition.source,
                    "processing_latency_ms": latency,
                }
                detection_id = self.database.record_detection(
                    self.event_engine.scan_run_id, record
                )
                detection_ids[index] = detection_id
                if hasattr(self.database, "record_recognition"):
                    self.database.record_recognition(
                        self.event_engine.scan_run_id, detection_id, recognition
                    )

            event_ids = []
            for index, (item, recognition) in enumerate(zip(detections, recognitions)):
                track_id = getattr(item, "track_id", None)
                if track_id is None:
                    continue
                center = (
                    (item.box[0] + item.box[2]) / 2,
                    (item.box[1] + item.box[3]) / 2,
                )
                previous = self._centers.get(track_id, center)
                self._centers[track_id] = center
                self._ages[track_id] = self._ages.get(track_id, 0) + 1
                class_id = int(getattr(
                    item, "class_id", self.class_ids.get(item.class_name, -1)
                ))
                observation = TrackObservation(
                    camera_id=self.camera_id,
                    stream_id=self.stream_id,
                    frame_uuid=str(frame.frame_uuid),
                    frame_timestamp=frame.captured_at,
                    detection_timestamp=datetime.now(timezone.utc),
                    track_id=track_id,
                    class_id=class_id,
                    confidence=float(item.confidence),
                    center=center,
                    previous_center=previous,
                    track_age=self._ages[track_id],
                    pipeline_version=self.pipeline_version,
                    detector_version=self.detector_version,
                    recognition_source=recognition.source,
                    processing_latency_ms=(time.perf_counter() - started) * 1000,
                    recognized_name=recognition.identity,
                    recognition_confidence=recognition.confidence,
                )
                decision = self.rule_engine.evaluate(observation)
                if hasattr(self.database, "record_rule_decision"):
                    self.database.record_rule_decision(
                        self.event_engine.scan_run_id, detection_ids[index], decision
                    )
                if not decision.keep:
                    continue
                count_event = self.counting_engine.evaluate(observation)
                if count_event is not None:
                    event_ids.append(self.event_engine.publish_count(
                        detection_ids[index], count_event, class_id
                    ))

            latency = (time.perf_counter() - started) * 1000
            self.last_result = PipelineResult(tuple(detections), tuple(event_ids), latency)
            log_operation(
                self.logger, request_id=str(frame.frame_uuid),
                camera_id=self.camera_id, frame_uuid=str(frame.frame_uuid),
                service="pipeline", processing_stage="complete",
                latency_ms=latency, status="ok", detections=len(detections),
                events=len(event_ids),
            )
            return detections
        except Exception as exc:
            raise ServiceError.from_exception(
                "PIPELINE_FAILED", "pipeline", exc, self.camera_id
            ) from exc

    def reset(self, reason="camera_reconnect"):
        self.processor.reset(reason)
        self.recognition_engine.reset(self.camera_id)
