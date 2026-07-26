"""Latest-frame inference scheduling with bounded per-camera queues."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import threading
import time
from typing import Any, Callable


@dataclass
class InferenceResult:
    camera_name: str
    frame: Any
    detections: list
    frame_at: float
    inference_at: float
    duration_ms: float
    sequence: int
    error: str | None = None


class LatestFrameInferenceScheduler:
    """Run model work off the capture loop and drop superseded frames.

    Each camera owns exactly one pending slot. Submitting another frame before
    inference begins replaces the old frame instead of building latency.
    """

    def __init__(self, processors: dict[str, Callable[[Any], list]]):
        self.processors = dict(processors)
        self._condition = threading.Condition()
        self._pending: dict[str, tuple[Any, float, float, int]] = {}
        self._results: dict[str, InferenceResult] = {}
        self._submitted = {name: 0 for name in processors}
        self._completed = {name: 0 for name in processors}
        self._dropped = {name: 0 for name in processors}
        self._last_duration_ms = {name: 0.0 for name in processors}
        self._last_inference_at = {name: 0.0 for name in processors}
        self._started_at = time.monotonic()
        self._sequence = 0
        self._closed = False
        self._thread = threading.Thread(
            target=self._run,
            name="latest-frame-inference",
            daemon=True,
        )
        self._thread.start()

    def submit(self, camera_name: str, frame: Any, frame_at: float | None = None) -> bool:
        if camera_name not in self.processors:
            return False
        with self._condition:
            if self._closed:
                return False
            if camera_name in self._pending:
                self._dropped[camera_name] += 1
            self._sequence += 1
            self._submitted[camera_name] += 1
            self._pending[camera_name] = (
                frame,
                frame_at if frame_at is not None else time.time(),
                time.monotonic(),
                self._sequence,
            )
            self._condition.notify()
            return True

    def take_result(self, camera_name: str) -> InferenceResult | None:
        with self._condition:
            return self._results.pop(camera_name, None)

    def metrics(self, camera_name: str) -> dict[str, Any]:
        with self._condition:
            completed = self._completed.get(camera_name, 0)
            elapsed = max(0.001, time.monotonic() - self._started_at)
            inference_at = self._last_inference_at.get(camera_name, 0.0)
            return {
                "queue_depth": int(camera_name in self._pending),
                "submitted_frames": self._submitted.get(camera_name, 0),
                "completed_inferences": completed,
                "dropped_frames": self._dropped.get(camera_name, 0),
                "inference_fps": round(completed / elapsed, 3),
                "last_inference_duration_ms": round(
                    self._last_duration_ms.get(camera_name, 0.0), 1
                ),
                "inference_age_ms": (
                    round(max(0.0, time.time() - inference_at) * 1000)
                    if inference_at
                    else None
                ),
                "last_inference_at": (
                    datetime.fromtimestamp(inference_at).isoformat(timespec="milliseconds")
                    if inference_at
                    else None
                ),
            }

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._pending.clear()
            self._condition.notify_all()
        if self._thread is not threading.current_thread():
            self._thread.join(timeout=5.0)

    def _run(self) -> None:
        while True:
            with self._condition:
                while not self._pending and not self._closed:
                    self._condition.wait()
                if self._closed:
                    return
                camera_name = min(
                    self._pending,
                    key=lambda name: self._pending[name][2],
                )
                frame, frame_at, _submitted_at, sequence = self._pending.pop(camera_name)

            started = time.perf_counter()
            inference_at = time.time()
            error = None
            try:
                detections = self.processors[camera_name](frame)
            except Exception as exc:  # keep other cameras alive after model errors
                detections = []
                error = str(exc)
            duration_ms = (time.perf_counter() - started) * 1000
            result = InferenceResult(
                camera_name=camera_name,
                frame=frame,
                detections=detections,
                frame_at=frame_at,
                inference_at=inference_at,
                duration_ms=duration_ms,
                sequence=sequence,
                error=error,
            )
            with self._condition:
                self._results[camera_name] = result
                self._completed[camera_name] += 1
                self._last_duration_ms[camera_name] = duration_ms
                self._last_inference_at[camera_name] = inference_at
