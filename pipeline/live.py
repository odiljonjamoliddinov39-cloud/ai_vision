"""Single production path: live frame -> YOLO -> ByteTrack -> rules -> events -> DB."""
from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from uuid import uuid4

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
    """Scheduler-compatible canonical pipeline for exactly one camera."""
    def __init__(self, *, camera_id: str, stream_id: str, processor,
                 rule_engine: CountingRuleEngine, event_engine: EventEngine,
                 database, pipeline_version: str, detector_version: str,
                 class_ids: dict[str, int], recognizer=None, logger=None):
        self.camera_id = camera_id
        self.stream_id = stream_id
        self.processor = processor
        self.rule_engine = rule_engine
        self.event_engine = event_engine
        self.database = database
        self.pipeline_version = pipeline_version
        self.detector_version = detector_version
        self.class_ids = class_ids
        self.recognizer = recognizer
        self.logger = logger or logging.getLogger("ai_vision.pipeline")
        self.last_result = PipelineResult((), (), 0.0)
        self._centers = {}
        self._ages = {}

    def process(self, image, frame_sequence: int, observed_at: float) -> list:
        frame = LiveFrame(self.camera_id, self.stream_id, uuid4(),
                          datetime.fromtimestamp(observed_at, timezone.utc), image)
        started = time.perf_counter()
        try:
            detections = list(self.processor.process(image, frame_sequence, observed_at))
            if self.recognizer is not None:
                self.recognizer.annotate(self.camera_id, image, detections)
            detection_ids = {}
            for item in detections:
                latency = (time.perf_counter() - started) * 1000
                class_id = int(getattr(item, "class_id", self.class_ids.get(item.class_name, -1)))
                record = {
                    "camera_id": frame.camera_id, "stream_id": frame.stream_id,
                    "frame_uuid": str(frame.frame_uuid), "frame_timestamp": frame.captured_at.isoformat(),
                    "detection_timestamp": datetime.now(timezone.utc).isoformat(),
                    "track_id": getattr(item, "track_id", None), "class_id": class_id,
                    "confidence": float(item.confidence), "bbox": list(item.box),
                    "pipeline_version": self.pipeline_version, "detector_version": self.detector_version,
                    "recognition_source": "detector", "processing_latency_ms": latency,
                }
                detection_ids[getattr(item, "track_id", None)] = self.database.record_detection(
                    self.event_engine.scan_run_id, record
                )
            event_ids = []
            inventory_events = self.rule_engine.evaluate_tracked(self.camera_id, detections, observed_at)
            for event in inventory_events:
                payload = asdict(event) if is_dataclass(event) else dict(event)
                track_id = next((getattr(d, "track_id", None) for d in detections
                                 if str(getattr(d, "track_id", "")) in str(payload.get("object_id", ""))), None)
                payload.update({"camera_id": self.camera_id, "stream_id": self.stream_id,
                                "frame_uuid": str(frame.frame_uuid), "track_id": track_id,
                                "class_id": next((getattr(d, "class_id", -1) for d in detections
                                                  if getattr(d, "track_id", None) == track_id), -1)})
                event_ids.append(self.event_engine.publish(detection_ids.get(track_id), payload))
            if not inventory_events:
                for item in detections:
                    track_id = getattr(item, "track_id", None)
                    if track_id is None:
                        continue
                    center = ((item.box[0] + item.box[2]) / 2, (item.box[1] + item.box[3]) / 2)
                    previous = self._centers.get(track_id, center)
                    self._centers[track_id] = center
                    self._ages[track_id] = self._ages.get(track_id, 0) + 1
                    now = datetime.now(timezone.utc)
                    class_id = int(getattr(item, "class_id", self.class_ids.get(item.class_name, -1)))
                    decision = self.rule_engine.evaluate(TrackObservation(
                        camera_id=self.camera_id, stream_id=self.stream_id,
                        frame_uuid=str(frame.frame_uuid), frame_timestamp=frame.captured_at,
                        detection_timestamp=now, track_id=track_id, class_id=class_id,
                        confidence=float(item.confidence), center=center, previous_center=previous,
                        track_age=self._ages[track_id], pipeline_version=self.pipeline_version,
                        detector_version=self.detector_version, recognition_source=(
                            "recognition" if getattr(item, "inventory_name", None) else "detector"
                        ), processing_latency_ms=(time.perf_counter() - started) * 1000,
                    ))
                    if decision:
                        event_ids.append(self.event_engine.publish_count(
                            detection_ids.get(track_id), decision, class_id
                        ))
            latency = (time.perf_counter() - started) * 1000
            self.last_result = PipelineResult(tuple(detections), tuple(event_ids), latency)
            log_operation(self.logger, request_id=str(frame.frame_uuid), camera_id=self.camera_id,
                          frame_uuid=str(frame.frame_uuid), service="pipeline", processing_stage="complete",
                          latency_ms=latency, status="ok", detections=len(detections), events=len(event_ids))
            return detections
        except Exception as exc:
            raise ServiceError.from_exception("PIPELINE_FAILED", "pipeline", exc, self.camera_id) from exc

    def reset(self, reason="camera_reconnect"):
        self.processor.reset(reason)
