"""
detection/snapshot.py

Saves a snapshot image whenever a "trigger" class (e.g. person, car)
is detected, with a per-class cooldown so it doesn't spam the disk.

FR-5: Snapshot
"""

from __future__ import annotations

import os
import time

import cv2


class SnapshotSaver:
    def __init__(
        self,
        save_dir: str = "snapshots",
        trigger_classes: list[str] | None = None,
        cooldown_seconds: float = 5.0,
    ):
        self.save_dir = save_dir
        self.trigger_classes = set(trigger_classes) if trigger_classes else set()
        self.cooldown_seconds = cooldown_seconds
        self._last_saved: dict[str, float] = {}
        os.makedirs(self.save_dir, exist_ok=True)

    def maybe_save(self, camera_name: str, frame, detections) -> list[str]:
        """
        Checks detections against trigger classes / cooldown and saves a
        snapshot if warranted. Returns list of saved file paths (usually 0 or 1).
        """
        saved = []
        now = time.time()
        classes_present = {d.class_name for d in detections}

        triggered = classes_present & self.trigger_classes
        # also save on genuinely unknown/unexpected objects if no filter set
        if not self.trigger_classes and classes_present:
            triggered = classes_present

        for class_name in triggered:
            key = f"{camera_name}:{class_name}"
            last = self._last_saved.get(key, 0)
            if now - last < self.cooldown_seconds:
                continue

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            safe_camera = camera_name.replace(" ", "_")
            filename = f"{safe_camera}_{class_name}_{timestamp}.jpg"
            path = os.path.join(self.save_dir, filename)

            cv2.imwrite(path, frame)
            self._last_saved[key] = now
            saved.append(path)

        return saved
