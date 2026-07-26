import threading
import time

from detection.scheduler import LatestFrameInferenceScheduler


def test_scheduler_keeps_only_latest_pending_frame():
    release = threading.Event()
    seen = []

    def process(frame):
        seen.append(frame)
        if frame == "first":
            release.wait(2)
        return [frame]

    scheduler = LatestFrameInferenceScheduler({"camera": process})
    try:
        scheduler.submit("camera", "first")
        deadline = time.time() + 1
        while time.time() < deadline and seen != ["first"]:
            time.sleep(0.01)
        scheduler.submit("camera", "old")
        scheduler.submit("camera", "newest")
        release.set()

        deadline = time.time() + 2
        while time.time() < deadline and len(seen) < 2:
            time.sleep(0.01)

        assert seen == ["first", "newest"]
        assert scheduler.metrics("camera")["dropped_frames"] == 1
        assert scheduler.metrics("camera")["queue_depth"] == 0
    finally:
        scheduler.close()


def test_scheduler_isolates_camera_processors_and_results():
    scheduler = LatestFrameInferenceScheduler(
        {
            "one": lambda frame: [f"one:{frame}"],
            "two": lambda frame: [f"two:{frame}"],
        }
    )
    try:
        scheduler.submit("one", 1)
        scheduler.submit("two", 2)
        results = {}
        deadline = time.time() + 2
        while time.time() < deadline and len(results) < 2:
            for name in ("one", "two"):
                result = scheduler.take_result(name)
                if result is not None:
                    results[name] = result
            time.sleep(0.01)

        assert results["one"].detections == ["one:1"]
        assert results["two"].detections == ["two:2"]
        assert results["one"].sequence != results["two"].sequence
    finally:
        scheduler.close()
