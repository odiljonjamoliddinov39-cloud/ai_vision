"""Structured errors and JSON logging shared by all pipeline domains."""
from __future__ import annotations

import json
import logging
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass
class ServiceError(Exception):
    error_code: str
    message: str
    service: str
    camera_id: str | None = None
    timestamp: str = ""
    stacktrace: str | None = None

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        Exception.__init__(self, self.message)

    @classmethod
    def from_exception(cls, code: str, service: str, exc: Exception, camera_id: str | None = None):
        return cls(code, str(exc), service, camera_id, stacktrace="".join(traceback.format_exception(exc)))

    def to_dict(self) -> dict:
        return asdict(self)


def log_operation(logger: logging.Logger, *, request_id: str, camera_id: str | None,
                  frame_uuid: str | None, service: str, processing_stage: str,
                  latency_ms: float, status: str, **details) -> None:
    logger.info(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(), "request_id": request_id,
        "camera_id": camera_id, "frame_uuid": frame_uuid, "service": service,
        "processing_stage": processing_stage, "latency_ms": round(latency_ms, 3),
        "status": status, **details,
    }, default=str, separators=(",", ":")))
