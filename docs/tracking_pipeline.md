# Detection and ByteTrack pipeline

The production path has one responsibility at each boundary:

```text
camera frame + sequence + timestamp
  -> shared Detector.detect(frame)
  -> normalized list[Detection]
  -> camera-local ByteTrackAdapter.update(detections, metadata)
  -> list[TrackedObject]
  -> presence, counting, database, and dashboard consumers
```

## State ownership

The `Detector` owns the single loaded Ultralytics model. It is shared by all
camera processors and performs inference exactly once for each scheduled frame.
The detector's lock protects that shared model from unsafe concurrent calls.

Every camera owns a separate `ByteTrackAdapter` and therefore a separate
Ultralytics `BYTETracker` instance. The adapter never calls `model.predict()` or
`model.track()`, never reloads weights, and never performs custom IoU matching.

## Ordering and lifecycle

The scheduler supplies a monotonically increasing sequence and capture time to
the camera processor. An adapter rejects a sequence that is not newer than its
last accepted sequence and increments `out_of_order_skips`. Empty detection
lists are still passed to ByteTrack so lost tracks age normally.

Tracker state is reset after a camera reconnect and when frame resolution
changes. Resetting one adapter cannot affect another camera.

## Configuration

`tracking.tracker_config` points to the authoritative ByteTrack YAML. Startup
fails clearly when the file is missing, malformed, lacks required keys, or has
a tracker type other than `bytetrack`. The deployment pins Ultralytics to the
API-compatible `8.4.x` range in `requirements-ai.txt`.

## Operations and troubleshooting

The detection health payload exposes `tracking_by_camera`. Important fields are
`last_sequence`, `updates`, `empty_updates`, `out_of_order_skips`, `resets`, and
`last_reset_reason`. Scheduler metrics beside it report queue depth, dropped
frames, inference latency, inference FPS, and tracking FPS.

If IDs churn, first check camera reconnect/resolution resets and dropped-frame
rate, then tune `config/warehouse_bytetrack.yaml`. If inference fails, inspect
the detector health separately; tracking contains no inference fallback.
