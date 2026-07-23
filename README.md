# AI Vision Assistant — Phase 1 MVP

## AI Vision V2 Architecture

AI Vision V2 is device-first and stream-first:

```text
Network device
-> Discovery Engine
-> Stream Manager
-> Live Dashboard
-> YOLO Analytics
-> Detection metadata / Tracking / Events / Database
```

The normal connection flow starts from only a device IP address or hostname.
Users do not enter RTSP URLs, stream paths, vendors, or connection types in
the dashboard. The Discovery Engine scans reachable services, fingerprints the
device, and enumerates channels through ONVIF-first/provider fallback logic.

`streams/manager.py` owns video-source connections and publishes clean live
frames to `snapshots/latest_stream_slot_N.jpg`. The dashboard reads those
frames through `/api/live_frame?slot=N` or `/api/v2/channels/{channel_id}/live`.
YOLO is a secondary consumer: when the API starts analytics, `main.py` runs
with `AI_VISION_STREAM_FIRST=1` and reads Stream Manager frame files instead
of opening the RTSP/NVR stream directly.

V2 API flow:

```bash
curl -X POST http://localhost:8000/api/v2/devices/discover \
  -H "Content-Type: application/json" \
  -d '{"host":"82.192.242.82"}'

curl -X POST http://localhost:8000/api/v2/devices/1/authenticate \
  -H "Content-Type: application/json" \
  -d '{"protocol":"rtsp","port":554,"username":"USER","password":"PASS","channel_count":4}'

curl -X POST http://localhost:8000/api/v2/channels/1/stream/start
curl -X POST http://localhost:8000/api/v2/channels/1/analytics/start
```

Run and verify:

```bash
uvicorn api.server:app --reload --host 0.0.0.0 --port 8000
python -m pytest tests/test_v2_stream_architecture.py tests/test_discovery.py tests/test_live_feed_refresh.py tests/test_camera_connection.py -q
```

Real-time camera object detection with bounding boxes, live counts,
snapshots, and an event log. Built as the foundation for the full
roadmap (tracking → memory → alerts → voice assistant) described in
the Technical Design doc.

## What's included (Version 0.1 + Phase 1 extras)

- **FR-1 Camera Connection** — `cameras/camera.py`: USB webcam or RTSP
  CCTV, multiple cameras, auto-reconnect on dropped streams.
- **FR-2 Object Detection** — `detection/detector.py`: YOLOv8 via
  Ultralytics, per-frame detection with confidence scores.
- **FR-3 Live Display** — `detection/draw.py` + `main.py`: live feed,
  FPS counter, bounding boxes, labels, confidence.
- **FR-4 Object Counting** — live per-class counts overlaid on frame.
- **FR-5 Snapshot** — `detection/snapshot.py`: auto-saves an image
  when a trigger class (e.g. person, car) appears, with a cooldown.
- **FR-6 Event Log** — `database/event_log.py`: appends detection
  events to `logs/events.log` in the format from the design doc.

## Project structure

```
ai_vision/
├── cameras/        # camera connection (USB / RTSP)
├── detection/       # YOLO detector, drawing, snapshots
├── tracking/         # (Phase 3 — object tracking, empty for now)
├── ai/                # (Phase 2 — AI reasoning / assistant, empty for now)
├── speech/          # (Phase 2 — STT/TTS, empty for now)
├── database/       # event logging (SQLite/Postgres later)
├── api/                # (Phase 2+ — FastAPI backend, empty for now)
├── dashboard/    # (Phase 2+ — Streamlit/React dashboard, empty for now)
├── config/          # config.yaml
├── models/          # YOLO model weights (.pt) go here
├── logs/               # events.log written here
├── snapshots/     # auto-saved detection images
├── tests/             # unit tests
└── main.py           # entry point
```

Empty folders contain a `.gitkeep` so the structure survives being
zipped/committed even before those phases are built.

## Setup

1. **Python**: 3.10+ recommended.

2. **Install dependencies:**

   ```bash
   python -m venv venv
   source venv/bin/activate        # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Model weights**: the config points to `models/yolov8n.pt`
   (the smallest, fastest YOLOv8 model — good for CPU). You don't need
   to download it manually — Ultralytics will fetch it automatically
   into that path the first time you run the app, as long as you have
   an internet connection. If you'd rather grab it yourself or use a
   different size (`yolov8s.pt`, `yolov8m.pt`, ...), see
   https://docs.ultralytics.com/models/yolov8/.

   To train a detector for your own warehouse object class, such as
   `baget box`, see `docs/yolo_training.md`.

4. **Configure your camera(s)** in `config/config.yaml`:

   ```yaml
   cameras:
     - name: "Camera 1"
       source: "dummy"   # use "dummy" when no physical camera is available
5. **Run it:**

   ```bash
   python main.py
   ```

   If your environment has no display, run:

   ```bash
   python main.py --no-display
   ```

   A window opens per camera showing live detections when display is available. Press **q** to quit.

   To verify the warehouse stock-counting flow without a physical camera
   or YOLO weights, run the deterministic demo:

   ```bash
   python main.py --config config/demo.yaml --no-display --max-frames 40
   ```

   This uses a synthetic tracked box crossing the counting line and writes
   stock movements to `database/warehouse.db`.

6. **Run the JavaScript control panel:**

   ```bash
   uvicorn api.server:app --reload --host 0.0.0.0 --port 8000
   ```

   Open `http://localhost:8000` to start/stop/restart detection, edit
   the main detection settings, and inspect recent logs/snapshots.

## Configuration reference (`config/config.yaml`)

| Section       | Key                     | Meaning                                              |
|---------------|-------------------------|-------------------------------------------------------|
| `cameras`     | `source`                | `0,1,2...` for USB, or an `rtsp://` URL              |
| `detection`   | `model_path`            | Path to YOLO weights                                  |
| `detection`   | `confidence_threshold`  | Minimum confidence to keep a detection (0–1)          |
| `detection`   | `device`                | `"cpu"` or `"cuda"`                                    |
| `detection`   | `classes`                | `null` for all classes, or a list like `["person"]`   |
| `spatial_analysis` | `camera_height_m`  | Camera lens height above the floor                     |
| `spatial_analysis` | `horizon_y_ratio`  | Horizon row divided by frame height                    |
| `spatial_analysis` | `horizontal_fov_degrees` | Camera horizontal field of view                  |
| `spatial_analysis` | `unit_dimensions`  | Known unit dimensions used for stack quantity estimates |
| `snapshots`   | `trigger_classes`        | Classes that trigger an auto-saved image              |
| `snapshots`   | `cooldown_seconds`       | Minimum gap between snapshots of the same class       |
| `logging`     | `log_file`                | Where detection events are appended                    |

### Monocular 3D estimates

The live feed and recognition dashboard show estimated object type,
distance, `W x H x D`, and stack quantity. Stack quantity is calculated
from the calibrated view and the configured dimensions of one unit. The
default keeps depth layers at one because a single CCTV image cannot see
hidden layers reliably. Set `estimate_depth_layers: true` only after
calibrating against known stacks.

For accurate metric sizing, measure the lens height, tune the horizon to
the camera view, and enter the real box or sack dimensions. Certified
measurements require a stereo or depth camera.

## Troubleshooting

- **"Could not open camera source"**: for USB cameras, try index `1`
  or `2` if `0` doesn't work (some systems have multiple video
  devices registered). For RTSP, double check the URL works in VLC
  first (`Media → Open Network Stream`).
- **Low FPS on CPU**: lower `detection.image_size`, use a smaller model,
  lower your camera resolution, or run on a
  machine with a CUDA GPU and set `device: "cuda"`.
- **RTSP keeps disconnecting**: this is normal for some CCTV/NVR
  setups; `cameras/camera.py` already retries automatically, but
  check your camera's stream URL/credentials if it never reconnects.

## Roadmap (from the design doc)

This MVP is the foundation for:

- **Phase 2** — AI assistant that answers questions like "What do you
  see?" (`ai/`, `speech/` — wire up an LLM + Whisper/Piper here)
- **Phase 3** — Per-object tracking with persistent IDs (`tracking/`
  — ByteTrack/DeepSORT)
- **Phase 4** — Memory of who entered/exited and for how long
- **Phase 5** — Alerts (after-hours entry, fire/smoke, empty
  warehouse, missing package)

Each phase builds on the `Detection` objects already produced by
`detection/detector.py`, so none of Phase 1 needs to be rewritten to
support them.
