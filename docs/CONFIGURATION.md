# Configuration Guide

All operational tuning belongs in `config/config.yaml` or environment variables.
Production must use a real YOLO model, RTSP cameras stored in the camera database,
and `DATABASE_URL` for PostgreSQL.

Key groups are `detection`, `tracking`, `pipeline`, `counting_rules`, `recognition`,
`stream`, `snapshots`, and `logging`. Confidence/IoU thresholds, image size,
timeouts, retries, worker/queue sizes, reconnect delay, and snapshot policy must
not be hardcoded in services.

Snapshots are historical evidence. No configuration can select them as inference
inputs because the canonical pipeline accepts `LiveFrame(source="live_rtsp")` only.
