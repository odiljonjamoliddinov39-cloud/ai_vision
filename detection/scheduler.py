"""Low-latency, bounded, multi-worker inference scheduling."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
import os
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
    queue_latency_ms: float
    sequence: int
    error: str | None = None


def resolve_worker_count(value: Any, camera_count: int, device: str = "cpu") -> int:
    """Resolve an integer or AUTO worker count without oversubscribing hardware."""
    camera_count = max(1, int(camera_count or 1))
    if isinstance(value, int) or (isinstance(value, str) and value.strip().isdigit()):
        return max(1, min(camera_count, int(value)))
    if str(value or "AUTO").strip().upper() != "AUTO":
        raise ValueError("detector_workers must be AUTO or a positive integer")
    if str(device).lower().startswith(("cuda", "mps")):
        return max(1, min(camera_count, int(os.getenv("AI_VISION_GPU_WORKERS", "1"))))
    cpu_count = os.cpu_count() or 1
    return max(1, min(camera_count, max(1, cpu_count // 2)))


class LatestFrameInferenceScheduler:
    """Process camera frames with bounded queues and per-camera ordering.

    ``latest`` mode discards queued superseded frames when a worker becomes
    available. ``fifo`` mode preserves queue order and rejects new work when
    the configured queue is full. A camera is never processed concurrently,
    which preserves ByteTrack's temporal state.
    """

    def __init__(
        self,
        processors: dict[str, Callable[[Any], list]],
        queue_size: int = 5,
        queue_mode: str = "latest",
        workers: Any = "AUTO",
        device: str = "cpu",
    ):
        self.processors = dict(processors)
        self.queue_size = max(1, int(queue_size))
        self.queue_mode = str(queue_mode).strip().lower()
        if self.queue_mode not in {"latest", "fifo"}:
            raise ValueError("queue_mode must be 'latest' or 'fifo'")
        self.worker_count = resolve_worker_count(workers, len(processors), device)
        self._condition = threading.Condition()
        self._queues = {name: deque() for name in processors}
        self._in_flight: set[str] = set()
        self._results: dict[str, InferenceResult] = {}
        self._submitted = {name: 0 for name in processors}
        self._completed = {name: 0 for name in processors}
        self._dropped = {name: 0 for name in processors}
        self._detections = {name: 0 for name in processors}
        self._duration_total_ms = {name: 0.0 for name in processors}
        self._queue_latency_total_ms = {name: 0.0 for name in processors}
        self._last_duration_ms = {name: 0.0 for name in processors}
        self._last_queue_latency_ms = {name: 0.0 for name in processors}
        self._last_inference_at = {name: 0.0 for name in processors}
        self._started_at = time.monotonic()
        self._sequence = 0
        self._closed = False
        self._threads = [
            threading.Thread(
                target=self._run,
                name=f"inference-worker-{index + 1}",
                daemon=True,
            )
            for index in range(self.worker_count)
        ]
        for thread in self._threads:
            thread.start()

    def submit(self, camera_name: str, frame: Any, frame_at: float | None = None) -> bool:
        if camera_name not in self.processors:
            return False
        with self._condition:
            if self._closed:
                return False
            queue = self._queues[camera_name]
            if len(queue) >= self.queue_size:
                if self.queue_mode == "fifo":
                    self._dropped[camera_name] += 1
                    return False
                queue.popleft()
                self._dropped[camera_name] += 1
            self._sequence += 1
            self._submitted[camera_name] += 1
            queue.append(
                (
                    frame,
                    frame_at if frame_at is not None else time.time(),
                    time.monotonic(),
                    self._sequence,
                )
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
                "queue_depth": len(self._queues.get(camera_name, ())),
                "queue_size": self.queue_size,
                "queue_mode": self.queue_mode,
                "worker_count": self.worker_count,
                "submitted_frames": self._submitted.get(camera_name, 0),
                "completed_inferences": completed,
                "dropped_frames": self._dropped.get(camera_name, 0),
                "inference_fps": round(completed / elapsed, 3),
                "tracking_fps": round(completed / elapsed, 3),
                "detection_count_per_sec": round(
                    self._detections.get(camera_name, 0) / elapsed, 3
                ),
                "last_inference_duration_ms": round(
                    self._last_duration_ms.get(camera_name, 0.0), 1
                ),
                "average_inference_duration_ms": round(
                    self._duration_total_ms.get(camera_name, 0.0) / completed, 1
                ) if completed else 0.0,
                "queue_latency_ms": round(
                    self._last_queue_latency_ms.get(camera_name, 0.0), 1
                ),
                "average_queue_latency_ms": round(
                    self._queue_latency_total_ms.get(camera_name, 0.0) / completed, 1
                ) if completed else 0.0,
                "inference_age_ms": (
                    round(max(0.0, time.time() - inference_at) * 1000)
                    if inference_at else None
                ),
                "last_inference_at": (
                    datetime.fromtimestamp(inference_at).isoformat(timespec="milliseconds")
                    if inference_at else None
                ),
            }

    def close(self) -> None:
        with self._condition:
            self._closed = True
            for queue in self._queues.values():
                queue.clear()
            self._condition.notify_all()
        current = threading.current_thread()
        for thread in self._threads:
            if thread is not current:
                thread.join(timeout=5.0)

    def _next_job(self):
        available = [
            name for name, queue in self._queues.items()
            if queue and name not in self._in_flight
        ]
        if not available:
            return None
        camera_name = min(available, key=lambda name: self._queues[name][0][2])
        queue = self._queues[camera_name]
        if self.queue_mode == "latest":
            dropped = max(0, len(queue) - 1)
            if dropped:
                self._dropped[camera_name] += dropped
            job = queue.pop()
            queue.clear()
        else:
            job = queue.popleft()
        self._in_flight.add(camera_name)
        return camera_name, job

    def _run(self) -> None:
        while True:
            with self._condition:
                job = self._next_job()
                while job is None and not self._closed:
                    self._condition.wait()
                    job = self._next_job()
                if self._closed:
                    return
                camera_name, (frame, frame_at, submitted_at, sequence) = job

            started = time.perf_counter()
            inference_at = time.time()
            queue_latency_ms = max(0.0, (time.monotonic() - submitted_at) * 1000)
            error = None
            try:
                detections = self.processors[camera_name](frame)
            except Exception as exc:
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
                queue_latency_ms=queue_latency_ms,
                sequence=sequence,
                error=error,
            )
            with self._condition:
                self._results[camera_name] = result
                self._completed[camera_name] += 1
                self._detections[camera_name] += len(detections)
                self._duration_total_ms[camera_name] += duration_ms
                self._queue_latency_total_ms[camera_name] += queue_latency_ms
                self._last_duration_ms[camera_name] = duration_ms
                self._last_queue_latency_ms[camera_name] = queue_latency_ms
                self._last_inference_at[camera_name] = inference_at
                self._in_flight.discard(camera_name)
                self._condition.notify_all()
