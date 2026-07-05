# AI Vision Assistant — Phase 1 MVP

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
| `snapshots`   | `trigger_classes`        | Classes that trigger an auto-saved image              |
| `snapshots`   | `cooldown_seconds`       | Minimum gap between snapshots of the same class       |
| `logging`     | `log_file`                | Where detection events are appended                    |

## Troubleshooting

- **"Could not open camera source"**: for USB cameras, try index `1`
  or `2` if `0` doesn't work (some systems have multiple video
  devices registered). For RTSP, double check the URL works in VLC
  first (`Media → Open Network Stream`).
- **Low FPS on CPU**: use `yolov8n.pt` (already the default — the
  smallest/fastest model), lower your camera resolution, or run on a
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
