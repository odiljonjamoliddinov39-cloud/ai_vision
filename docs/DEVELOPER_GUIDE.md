# Developer Guide

New inference behavior must be added behind the canonical `LiveVisionPipeline`.
Adapters may replace YOLO or ByteTrack without changing rules or persistence.
Never call a detector from API, database, snapshot, analytics, or event modules.

Each detection requires camera/stream/frame IDs, both timestamps, pipeline and
detector versions, recognition source, and processing latency. Tests should use
fake adapters and timezone-aware timestamps. Run `pytest -q` and `git diff --check`
before every push.
