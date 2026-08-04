# Backend Refactor Report

## Completed

- Added a single typed live-frame pipeline boundary.
- Added deterministic entry/zone/exit count-once rules.
- Added durable scan, detection, event, and count tables.
- Enforced complete detection traceability to a live frame.
- Added structured service errors and JSON operation logs.
- Separated stream, rules, events, analytics, and notification domains.
- Added focused pipeline, source-provenance, persistence, and failure tests.
- Documented architecture, API, configuration, deployment, and development.
- Removed the detector-only and legacy appearance/line counting execution branches.

## Verification

- 91 automated tests pass.
- Python compilation and `git diff --check` pass.
- The focused pipeline tests prove snapshot inputs are rejected and each track is counted once.

## Remaining operational risks

Accuracy and throughput still depend on real Baget training data, camera placement,
GPU capacity, and production PostgreSQL/RTSP load tests. These cannot be established
by source refactoring alone and must be measured with site hardware.
