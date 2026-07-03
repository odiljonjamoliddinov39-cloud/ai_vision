"""
database/event_log.py

Simple event logger for object detections. Writes human-readable
entries to a log file, in the style shown in the design doc:

    14:21
    Person detected
    Camera 2
    Confidence 98%
    -----------------

Phase 1 uses a flat text log; this can be swapped for SQLite/Postgres
later (see FR-6, and the "Database" row in the tech stack) without
changing the call site in main.py.

FR-6: Event Log
"""

from __future__ import annotations

import os
import time


class EventLogger:
    def __init__(self, log_dir: str = "logs", log_file: str = "events.log"):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_path = os.path.join(self.log_dir, log_file)

    def log_detections(self, camera_name: str, detections) -> None:
        if not detections:
            return

        timestamp = time.strftime("%H:%M")
        lines = []
        for det in detections:
            lines.append(timestamp)
            lines.append(f"{det.class_name.capitalize()} detected")
            lines.append(camera_name)
            lines.append(f"Confidence {det.confidence * 100:.0f}%")
            lines.append("-----------------")

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
