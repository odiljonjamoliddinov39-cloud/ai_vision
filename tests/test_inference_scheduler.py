import threading
import time

from detection.scheduler import LatestFrameInferenceScheduler, resolve_worker_count


def _wait_for(predicate, timeout=2):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_latest_mode_processes_newest_without_unbounded_backlog():
    release = threading.Event()
    seen = []

    def process(frame, _sequence, _observed_at):
        seen.append(frame)
        if frame == "first":
            release.wait(2)
        return [frame]

    scheduler = LatestFrameInferenceScheduler(
        {"camera": process}, queue_size=5, queue_mode="latest", workers=1
    )
    try:
        scheduler.submit("camera", "first")
        assert _wait_for(lambda: seen == ["first"])
        scheduler.submit("camera", "old")
        scheduler.submit("camera", "middle")
        scheduler.submit("camera", "newest")
        release.set()
        assert _wait_for(lambda: len(seen) == 2)
        assert seen == ["first", "newest"]
        assert scheduler.metrics("camera")["dropped_frames"] == 2
    finally:
        scheduler.close()


def test_fifo_mode_preserves_order_and_rejects_overflow():
    release = threading.Event()
    seen = []

    def process(frame, _sequence, _observed_at):
        seen.append(frame)
        if frame == 1:
            release.wait(2)
        return [frame]

    scheduler = LatestFrameInferenceScheduler(
        {"camera": process}, queue_size=2, queue_mode="fifo", workers=1
    )
    try:
        assert scheduler.submit("camera", 1)
        assert _wait_for(lambda: seen == [1])
        assert scheduler.submit("camera", 2)
        assert scheduler.submit("camera", 3)
        assert not scheduler.submit("camera", 4)
        release.set()
        assert _wait_for(lambda: seen == [1, 2, 3])
        assert scheduler.metrics("camera")["dropped_frames"] == 1
    finally:
        scheduler.close()


def test_workers_parallelize_cameras_but_not_one_camera():
    active = 0
    peak = 0
    lock = threading.Lock()

    def process(frame, _sequence, _observed_at):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return [frame]

    scheduler = LatestFrameInferenceScheduler(
        {"one": process, "two": process}, queue_mode="fifo", workers=2
    )
    try:
        scheduler.submit("one", 1)
        scheduler.submit("two", 2)
        assert _wait_for(lambda: scheduler.metrics("one")["completed_inferences"] == 1)
        assert _wait_for(lambda: scheduler.metrics("two")["completed_inferences"] == 1)
        assert peak == 2
    finally:
        scheduler.close()


def test_metrics_include_latency_duration_rate_and_worker_configuration():
    scheduler = LatestFrameInferenceScheduler(
        {"camera": lambda frame, _sequence, _observed_at: [frame, frame]}, workers=1
    )
    try:
        scheduler.submit("camera", "frame")
        assert _wait_for(lambda: scheduler.metrics("camera")["completed_inferences"] == 1)
        metrics = scheduler.metrics("camera")
        assert metrics["worker_count"] == 1
        assert metrics["queue_mode"] == "latest"
        assert metrics["average_inference_duration_ms"] >= 0
        assert metrics["average_queue_latency_ms"] >= 0
        assert metrics["detection_count_per_sec"] > 0
    finally:
        scheduler.close()


def test_auto_worker_count_is_bounded_by_camera_count(monkeypatch):
    monkeypatch.setattr("detection.scheduler.os.cpu_count", lambda: 16)
    assert resolve_worker_count("AUTO", 3, "cpu") == 3
    assert resolve_worker_count("AUTO", 3, "cuda:0") == 1
