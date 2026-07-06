"""
FastAPI control server for the AI Vision Assistant dashboard.

Run:
    uvicorn api.server:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import io
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
import asyncio
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database.tracking_db import TrackingDB  # noqa: E402
from database.warehouse_db import WarehouseDB  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "config.yaml"
LOG_PATH = ROOT / "logs" / "events.log"
SNAPSHOT_DIR = ROOT / "snapshots"
INVENTORY_PATH = ROOT / "logs" / "inventory.json"
INVENTORY_IMAGE_DIR = SNAPSHOT_DIR / "inventory"
DASHBOARD_DIR = ROOT / "dashboard"
TRACKING_DB_PATH = ROOT / "database" / "tracking.db"
WAREHOUSE_DB_PATH = ROOT / "database" / "warehouse.db"

app = FastAPI(title="AI Vision Control API", version="0.1.0")

_tracking_db: TrackingDB | None = None
_warehouse_db: WarehouseDB | None = None


def _get_tracking_db() -> TrackingDB:
    global _tracking_db
    if _tracking_db is None:
        _tracking_db = TrackingDB(db_path=str(TRACKING_DB_PATH))
    return _tracking_db


def _get_warehouse_db() -> WarehouseDB:
    global _warehouse_db
    if _warehouse_db is None:
        _warehouse_db = WarehouseDB(db_path=str(WAREHOUSE_DB_PATH))
    return _warehouse_db

_process: subprocess.Popen | None = None
_started_at: float | None = None
_last_exit_code: int | None = None


class StartRequest(BaseModel):
    no_display: bool = True
    config_path: str = "config/config.yaml"


class ConfigPatch(BaseModel):
    confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    device: str | None = None
    classes: list[str] | None = None
    snapshots_enabled: bool | None = None
    snapshot_trigger_classes: list[str] | None = None
    snapshot_cooldown_seconds: int | None = Field(default=None, ge=0)
    logging_enabled: bool | None = None


class ItemCreate(BaseModel):
    item_id: str
    name: str
    item_type: str | None = None


class InventoryAction(BaseModel):
    item_id: str
    quantity: int = Field(default=1, ge=1)
    note: str | None = None


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)


def _load_inventory() -> dict[str, Any]:
    INVENTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not INVENTORY_PATH.exists():
        _save_inventory({"items": [], "history": []})

    with INVENTORY_PATH.open("r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {"items": [], "history": []}


def _save_inventory(data: dict[str, Any]) -> None:
    with INVENTORY_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def _ensure_inventory() -> dict[str, Any]:
    data = _load_inventory()
    data.setdefault("items", [])
    data.setdefault("history", [])
    return data


def _find_item(data: dict[str, Any], item_id: str) -> dict[str, Any] | None:
    return next((item for item in data["items"] if item["item_id"] == item_id), None)


def _record_inventory_event(data: dict[str, Any], action: str, item_id: str, quantity: int, note: str | None) -> None:
    data["history"].insert(0, {
        "timestamp": _now_iso(),
        "item_id": item_id,
        "action": action,
        "quantity": quantity,
        "note": note,
    })


def _parse_event_log(limit: int = 40) -> list[dict[str, Any]]:
    if not LOG_PATH.exists():
        return []

    content = LOG_PATH.read_text(encoding="utf-8", errors="replace")
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    entries: list[dict[str, Any]] = []
    i = 0
    while i + 3 < len(lines):
        timestamp = lines[i]
        class_line = lines[i + 1]
        camera = lines[i + 2]
        confidence = lines[i + 3]
        match = re.match(r"^(.*) detected$", class_line, re.IGNORECASE)
        class_name = match.group(1) if match else class_line
        entries.append(
            {
                "timestamp": timestamp,
                "class_name": class_name,
                "camera": camera,
                "confidence": confidence,
            }
        )
        i += 5
    return entries[-limit:]


@app.get("/api/recognitions")
def recognitions(limit: int = 40) -> dict[str, Any]:
    entries = _parse_event_log(limit)
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry["class_name"]] = counts.get(entry["class_name"], 0) + 1
    distinct = [
        {"class_name": class_name, "count": count}
        for class_name, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    warehouse_db = _get_warehouse_db()
    status = _status()
    return {
        "running": status["running"],
        "entries": entries,
        "counts": distinct,
        "movements": warehouse_db.recent_movements(limit),
        "movement_counts": warehouse_db.movement_counts(),
        "stock": warehouse_db.get_all_stock(),
    }


@app.get("/api/warehouse/stock")
def warehouse_stock() -> dict[str, Any]:
    db = _get_warehouse_db()
    return {"stock": db.get_all_stock(), "movement_counts": db.movement_counts()}


@app.get("/api/warehouse/movements")
def warehouse_movements(limit: int = 50) -> dict[str, Any]:
    db = _get_warehouse_db()
    return {"movements": db.recent_movements(limit=max(1, min(limit, 500)))}


def _poll_process() -> None:
    global _last_exit_code, _process, _started_at
    if _process is None:
        return

    exit_code = _process.poll()
    if exit_code is not None:
        _last_exit_code = exit_code
        _process = None
        _started_at = None


def _status() -> dict[str, Any]:
    _poll_process()
    return {
        "running": _process is not None,
        "pid": _process.pid if _process else None,
        "started_at": _started_at,
        "uptime_seconds": round(time.time() - _started_at, 1)
        if _started_at
        else 0,
        "last_exit_code": _last_exit_code,
    }


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse(DASHBOARD_DIR / "index.html")


@app.get("/api/status")
def status() -> dict[str, Any]:
    return _status()


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return _read_yaml(CONFIG_PATH)


@app.patch("/api/config")
def update_config(patch: ConfigPatch) -> dict[str, Any]:
    data = _read_yaml(CONFIG_PATH)
    detection = data.setdefault("detection", {})
    snapshots = data.setdefault("snapshots", {})
    logging_cfg = data.setdefault("logging", {})

    values = patch.model_dump(exclude_unset=True)
    if "confidence_threshold" in values:
        detection["confidence_threshold"] = values["confidence_threshold"]
    if "device" in values:
        detection["device"] = values["device"]
    if "classes" in values:
        detection["classes"] = values["classes"] or None
    if "snapshots_enabled" in values:
        snapshots["enabled"] = values["snapshots_enabled"]
    if "snapshot_trigger_classes" in values:
        snapshots["trigger_classes"] = values["snapshot_trigger_classes"] or []
    if "snapshot_cooldown_seconds" in values:
        snapshots["cooldown_seconds"] = values["snapshot_cooldown_seconds"]
    if "logging_enabled" in values:
        logging_cfg["enabled"] = values["logging_enabled"]

    _write_yaml(CONFIG_PATH, data)
    return data


@app.post("/api/start")
def start_detection(request: StartRequest | None = None) -> dict[str, Any]:
    global _process, _started_at, _last_exit_code
    request = request or StartRequest()
    _poll_process()
    if _process is not None:
        raise HTTPException(status_code=409, detail="Detection is already running.")

    command = [
        sys.executable,
        str(ROOT / "main.py"),
        "--config",
        request.config_path,
    ]
    if request.no_display:
        command.append("--no-display")

    _process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=os.name != "nt",
    )
    _started_at = time.time()
    _last_exit_code = None
    return _status()


@app.post("/api/stop")
def stop_detection() -> dict[str, Any]:
    global _process, _started_at, _last_exit_code
    _poll_process()
    if _process is None:
        return _status()

    process = _process
    if os.name == "nt":
        process.terminate()
    else:
        os.killpg(process.pid, signal.SIGTERM)

    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)

    _last_exit_code = process.returncode
    _process = None
    _started_at = None
    return _status()


@app.post("/api/restart")
def restart_detection(request: StartRequest | None = None) -> dict[str, Any]:
    stop_detection()
    return start_detection(request)


@app.get("/api/logs")
def recent_logs(limit: int = 80) -> dict[str, Any]:
    if not LOG_PATH.exists():
        return {"lines": []}

    lines = LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    return {"lines": lines[-max(1, min(limit, 500)) :]}


@app.get("/api/snapshots")
def snapshots(limit: int = 24) -> dict[str, Any]:
    if not SNAPSHOT_DIR.exists():
        return {"snapshots": []}

    files = sorted(
        SNAPSHOT_DIR.glob("*.jpg"), key=lambda path: path.stat().st_mtime, reverse=True
    )
    return {
        "snapshots": [
            {
                "name": path.name,
                "url": f"/snapshots/{path.name}",
                "modified_at": path.stat().st_mtime,
            }
            for path in files[: max(1, min(limit, 100))]
        ]
    }


@app.get("/api/occupancy")
def occupancy(camera: str | None = None) -> dict[str, Any]:
    """Currently checked-in tracked objects (from ByteTrack + SQLite),
    plus per-class counts. Distinct from /api/inventory, which is the
    manually-operated warehouse item ledger."""
    db = _get_tracking_db()
    current = db.current_occupancy(camera_name=camera)
    counts = db.occupancy_counts(camera_name=camera)
    return {
        "current": current,
        "counts": [
            {"class_name": name, "count": count}
            for name, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
    }


@app.get("/api/occupancy/events")
def occupancy_events(limit: int = 50, camera: str | None = None) -> dict[str, Any]:
    """Recent check-in / check-out events, most recent first."""
    db = _get_tracking_db()
    events = db.recent_events(limit=max(1, min(limit, 500)), camera_name=camera)
    return {"events": events}


@app.get("/api/inventory")
def inventory() -> dict[str, Any]:
    data = _ensure_inventory()
    return {"items": data["items"], "history": data["history"]}


@app.post("/api/inventory/item")
def add_inventory_item(item: ItemCreate) -> dict[str, Any]:
    data = _ensure_inventory()
    if _find_item(data, item.item_id):
        raise HTTPException(status_code=409, detail="Item ID already exists.")

    record = {
        "item_id": item.item_id,
        "name": item.name,
        "item_type": item.item_type or "unknown",
        "quantity": 0,
        "created_at": _now_iso(),
        "last_updated_at": _now_iso(),
    }
    data["items"].append(record)
    _save_inventory(data)
    return record


@app.post("/api/inventory/checkin")
def inventory_checkin(action: InventoryAction) -> dict[str, Any]:
    data = _ensure_inventory()
    item = _find_item(data, action.item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found.")

    item["quantity"] += action.quantity
    item["last_updated_at"] = _now_iso()
    _record_inventory_event(data, "check-in", action.item_id, action.quantity, action.note)
    _save_inventory(data)
    return item


@app.post("/api/inventory/checkout")
def inventory_checkout(action: InventoryAction) -> dict[str, Any]:
    data = _ensure_inventory()
    item = _find_item(data, action.item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found.")
    if action.quantity > item["quantity"]:
        raise HTTPException(status_code=400, detail="Insufficient quantity for checkout.")

    item["quantity"] -= action.quantity
    item["last_updated_at"] = _now_iso()
    _record_inventory_event(data, "check-out", action.item_id, action.quantity, action.note)
    _save_inventory(data)
    return item


@app.post("/api/inventory/upload-image")
async def upload_inventory_image(item_id: str = Form(...), file: UploadFile = File(...)) -> dict[str, Any]:
    INVENTORY_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    item = _find_item(_ensure_inventory(), item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found.")

    filename = f"{item_id}_{int(time.time())}_{file.filename}"
    path = INVENTORY_IMAGE_DIR / filename
    contents = await file.read()
    path.write_bytes(contents)
    return {"url": f"/snapshots/inventory/{filename}", "name": filename}


@app.get("/api/logs/stream")
async def stream_logs():
    async def event_generator():
        last_pos = 0
        while True:
            if LOG_PATH.exists():
                try:
                    with LOG_PATH.open("r", encoding="utf-8", errors="replace") as f:
                        f.seek(last_pos)
                        data = f.read()
                        if data:
                            for line in data.splitlines():
                                yield f"data: {line}\n\n"
                        last_pos = f.tell()
                except Exception:
                    # swallow errors and continue polling
                    pass
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/live_mjpeg")
async def live_mjpeg():
    """Return a multipart/x-mixed-replace MJPEG stream by repeatedly
    reading snapshots/latest.jpg. This is a simple MJPEG server that
    serves the latest frame written by the detector.
    """

    boundary = "frame"

    async def frame_generator():
        while True:
            latest = SNAPSHOT_DIR / "latest.jpg"
            if latest.exists():
                try:
                    data = latest.read_bytes()
                    header = (
                        f"--{boundary}\r\n"
                        "Content-Type: image/jpeg\r\n"
                        f"Content-Length: {len(data)}\r\n\r\n"
                    ).encode("utf-8")
                    yield header + data + b"\r\n"
                except Exception:
                    # ignore read errors
                    pass
            await asyncio.sleep(0.05)

    return StreamingResponse(frame_generator(), media_type=f"multipart/x-mixed-replace; boundary={boundary}")


app.mount("/assets", StaticFiles(directory=DASHBOARD_DIR), name="dashboard-assets")
app.mount("/snapshots", StaticFiles(directory=SNAPSHOT_DIR), name="snapshots")
