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
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

import yaml
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
import asyncio
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database.camera_db import CameraDB  # noqa: E402
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
CAMERA_DB_PATH = ROOT / "database" / "cameras.db"
DETECTION_STDOUT_PATH = ROOT / "logs" / "detection_stdout.log"
DETECTION_STDERR_PATH = ROOT / "logs" / "detection_stderr.log"
DETECTION_HEALTH_PATH = ROOT / "logs" / "detection_health.json"
DETECTION_PID_PATH = ROOT / "logs" / "detection.pid"
MAX_CAMERA_SLOTS = 50

app = FastAPI(title="AI Vision Control API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_tracking_db: TrackingDB | None = None
_warehouse_db: WarehouseDB | None = None
_camera_db: CameraDB | None = None


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


def _get_camera_db() -> CameraDB:
    global _camera_db
    if _camera_db is None:
        _camera_db = CameraDB(db_path=str(CAMERA_DB_PATH))
        config = _read_yaml(CONFIG_PATH) if CONFIG_PATH.exists() else {}
        first_camera = (config.get("cameras") or [{"name": "Camera 1", "source": 0}])[0]
        _camera_db.ensure_default_camera(
            name=str(first_camera.get("name", "Camera 1")),
            stream_url=str(first_camera.get("source", 0)),
        )
    return _camera_db

_process: subprocess.Popen | None = None
_started_at: float | None = None
_last_exit_code: int | None = None
_stdout_handle = None
_stderr_handle = None


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


class CameraCreate(BaseModel):
    name: str = Field(min_length=1)
    stream_url: str = Field(min_length=1)
    make_active: bool = True
    test_connection: bool = True
    slot_number: int | None = Field(default=None, ge=1, le=MAX_CAMERA_SLOTS)


class CameraTestRequest(BaseModel):
    stream_url: str = Field(min_length=1)


class CameraSlotRequest(BaseModel):
    slot_number: int = Field(default=1, ge=1, le=MAX_CAMERA_SLOTS)


class CameraControllerCreate(BaseModel):
    name: str = Field(default="Camera Controller", min_length=1)
    host: str = Field(min_length=1)
    protocol: str = Field(default="rtsp", pattern="^(rtsp|http|https)$")
    port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = None
    password: str | None = None
    channel_count: int = Field(default=4, ge=1, le=MAX_CAMERA_SLOTS)
    channel_start: int = Field(default=1, ge=1)
    start_slot: int = Field(default=1, ge=1, le=MAX_CAMERA_SLOTS)
    stream_path_template: str = Field(default="/Streaming/Channels/{channel}01", min_length=1)
    camera_name_template: str = Field(default="{controller} Camera {channel}", min_length=1)
    make_active: bool = True
    test_controller: bool = True
    test_streams: bool = False


STREAM_DEFAULT_PORTS = {
    "rtsp": 554,
    "http": 80,
    "https": 443,
}

SECRET_URL_RE = re.compile(r"\b(?P<scheme>rtsp|https?)://(?P<username>[^:/\s]+):(?P<password>[^@\s]+)@")


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)


def _camera_source_from_text(stream_url: str):
    value = stream_url.strip()
    if value.isdigit():
        return int(value)
    return value


def _redact_sensitive_text(text: str) -> str:
    return SECRET_URL_RE.sub(
        lambda match: f"{match.group('scheme')}://{match.group('username')}:****@",
        text,
    )


def _is_local_capture_source(value: str) -> bool:
    if value.isdigit() or value.lower() == "dummy":
        return True
    try:
        return Path(value).exists()
    except (OSError, ValueError):
        return False


def _camera_stream_endpoint(stream_url: str) -> tuple[dict[str, Any] | None, str | None]:
    value = stream_url.strip()
    if _is_local_capture_source(value):
        return None, None

    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        return None, f"Invalid camera stream URL: {exc}"

    scheme = parsed.scheme.lower()
    if scheme not in STREAM_DEFAULT_PORTS:
        return (
            None,
            "Use a full camera stream URL starting with rtsp://, http://, or https://, "
            "or use a local webcam index like 0.",
        )

    if not parsed.hostname:
        return None, "Camera stream URL is missing a host or IP address."

    try:
        port = parsed.port or STREAM_DEFAULT_PORTS[scheme]
    except ValueError as exc:
        return None, f"Invalid camera stream port: {exc}"

    return {"scheme": scheme, "host": parsed.hostname, "port": port}, None


def _check_camera_endpoint(endpoint: dict[str, Any], timeout_seconds: float = 2.0) -> str | None:
    host = endpoint["host"]
    port = endpoint["port"]
    scheme = endpoint["scheme"].upper()
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return None
    except TimeoutError:
        reason = "connection timed out"
    except OSError as exc:
        reason = exc.strerror or str(exc)

    return (
        f"Cannot reach {scheme} endpoint {host}:{port} ({reason}). "
        "The camera is reachable only when this stream port is open; enable the camera stream service "
        "or use the correct stream URL/port."
    )


def _normalize_controller_host(host: str) -> str:
    value = host.strip()
    if "://" in value:
        parsed = urlsplit(value)
        if parsed.hostname:
            return parsed.hostname
    return value.strip("/")


def _controller_endpoint(controller: CameraControllerCreate) -> dict[str, Any]:
    protocol = controller.protocol.lower()
    return {
        "scheme": protocol,
        "host": _normalize_controller_host(controller.host),
        "port": controller.port or STREAM_DEFAULT_PORTS[protocol],
    }


def _controller_stream_url(controller: CameraControllerCreate, channel: int) -> str:
    protocol = controller.protocol.lower()
    host = _normalize_controller_host(controller.host)
    port = controller.port or STREAM_DEFAULT_PORTS[protocol]
    path = controller.stream_path_template.format(channel=channel)
    if not path.startswith("/"):
        path = f"/{path}"

    credentials = ""
    if controller.username:
        credentials = quote(controller.username, safe="")
        if controller.password:
            credentials += f":{quote(controller.password, safe='')}"
        credentials += "@"

    return f"{protocol}://{credentials}{host}:{port}{path}"


def _controller_camera_name(controller: CameraControllerCreate, channel: int, slot: int) -> str:
    return controller.camera_name_template.format(
        controller=controller.name.strip(),
        channel=channel,
        slot=slot,
    )


def _set_config_active_cameras(cameras: list[dict[str, Any]]) -> dict[str, Any]:
    data = _read_yaml(CONFIG_PATH)
    data["cameras"] = [
        {
            "name": camera["name"],
            "source": _camera_source_from_text(camera["stream_url"]),
            "slot_number": camera.get("slot_number") or index,
        }
        for index, camera in enumerate(cameras, start=1)
    ]
    _write_yaml(CONFIG_PATH, data)
    return data


def _sync_config_active_cameras(db: CameraDB) -> dict[str, Any]:
    return _set_config_active_cameras(db.list_active_cameras(include_secret=True))


def _next_available_slot(cameras: list[dict[str, Any]]) -> int:
    used_slots = {
        int(camera["slot_number"])
        for camera in cameras
        if camera.get("is_active") and camera.get("slot_number") is not None
    }
    slot_number = 1
    while slot_number in used_slots:
        slot_number += 1
    return slot_number


def _test_camera_stream(stream_url: str, timeout_seconds: int = 10) -> dict[str, Any]:
    endpoint, validation_error = _camera_stream_endpoint(stream_url)
    if validation_error:
        return {"status": "failed", "message": validation_error}

    if stream_url.strip().lower() == "dummy":
        return {"status": "connected", "message": "Demo camera source is available."}

    if endpoint is not None:
        endpoint_error = _check_camera_endpoint(endpoint)
        if endpoint_error:
            return {
                "status": "failed",
                "message": endpoint_error,
                "details": {
                    "host": endpoint["host"],
                    "port": endpoint["port"],
                    "scheme": endpoint["scheme"],
                    "endpoint_reachable": False,
                },
            }

    code = r"""
import json
import os
import sys
import cv2

raw = sys.argv[1].strip()
source = int(raw) if raw.isdigit() else raw

try:
    if isinstance(source, int) and os.name == "nt":
        cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(source)

    opened = bool(cap.isOpened())
    ok = False
    if opened:
        ok, _ = cap.read()
    cap.release()
    print(json.dumps({"ok": bool(opened and ok), "opened": opened, "frame_read": bool(ok)}))
except Exception as exc:
    print(json.dumps({"ok": False, "error": str(exc)}))
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", code, stream_url],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        response = {"status": "failed", "message": "OpenCV timed out while waiting for a video frame."}
        if endpoint is not None:
            response["details"] = {
                "host": endpoint["host"],
                "port": endpoint["port"],
                "scheme": endpoint["scheme"],
                "endpoint_reachable": True,
            }
        return response

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    try:
        payload = json.loads(stdout.splitlines()[-1]) if stdout else {}
    except (IndexError, json.JSONDecodeError):
        payload = {}

    if payload.get("ok"):
        response = {"status": "connected", "message": "Camera stream opened and returned a frame."}
        if endpoint is not None:
            response["details"] = {
                "host": endpoint["host"],
                "port": endpoint["port"],
                "scheme": endpoint["scheme"],
                "endpoint_reachable": True,
                "opencv_opened": True,
                "frame_read": True,
            }
        return response

    message = payload.get("error") or stderr or "Camera stream could not be opened or returned no frame."
    response = {"status": "failed", "message": message}
    if endpoint is not None:
        response["details"] = {
            "host": endpoint["host"],
            "port": endpoint["port"],
            "scheme": endpoint["scheme"],
            "endpoint_reachable": True,
            "opencv_opened": bool(payload.get("opened")),
            "frame_read": bool(payload.get("frame_read")),
        }
    return response


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


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _tail_file(path: Path, limit: int = 80) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return [_redact_sensitive_text(line) for line in lines[-max(1, min(limit, 500)) :]]


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
    global _last_exit_code, _process, _started_at, _stdout_handle, _stderr_handle
    if _process is None:
        return

    exit_code = _process.poll()
    if exit_code is not None:
        _last_exit_code = exit_code
        _process = None
        _started_at = None
        for handle in (_stdout_handle, _stderr_handle):
            if handle is not None:
                handle.close()
        _stdout_handle = None
        _stderr_handle = None
        _clear_detector_pid()


def _write_detector_pid(pid: int) -> None:
    DETECTION_PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    DETECTION_PID_PATH.write_text(str(pid), encoding="utf-8")


def _clear_detector_pid() -> None:
    try:
        DETECTION_PID_PATH.unlink()
    except FileNotFoundError:
        pass


def _read_detector_pid() -> int | None:
    try:
        value = DETECTION_PID_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None

    try:
        return int(value)
    except ValueError:
        _clear_detector_pid()
        return None


def _is_detector_command(command_line: str | None) -> bool:
    if not command_line:
        return False
    normalized = command_line.replace("\\", "/").lower()
    root_marker = str(ROOT).replace("\\", "/").lower()
    main_marker = str(ROOT / "main.py").replace("\\", "/").lower()
    return root_marker in normalized and main_marker in normalized and "--config" in normalized


def _process_command_line(pid: int) -> str | None:
    if pid <= 0:
        return None

    if os.name == "nt":
        command = (
            "$p = Get-CimInstance Win32_Process -Filter 'ProcessId = "
            f"{pid}' -ErrorAction SilentlyContinue; "
            "if ($p) { $p.CommandLine }"
        )
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                capture_output=True,
                text=True,
                timeout=3,
            )
        except Exception:
            return None
        if result.returncode != 0:
            return None
        return result.stdout.strip() or None

    proc_cmdline = Path("/proc") / str(pid) / "cmdline"
    try:
        return proc_cmdline.read_text(encoding="utf-8", errors="replace").replace("\x00", " ")
    except OSError:
        return None


def _pid_is_detector(pid: int) -> bool:
    return _is_detector_command(_process_command_line(pid))


def _discover_detector_pid() -> int | None:
    if os.name == "nt":
        command = (
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*main.py*' } | "
            'ForEach-Object { [string]$_.ProcessId + "`t" + $_.CommandLine }'
        )
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                capture_output=True,
                text=True,
                timeout=3,
            )
        except Exception:
            return None
        if result.returncode != 0:
            return None
        lines = result.stdout.splitlines()
    else:
        try:
            result = subprocess.run(
                ["pgrep", "-af", "main.py"],
                capture_output=True,
                text=True,
                timeout=3,
            )
        except Exception:
            return None
        lines = result.stdout.splitlines()

    for line in lines:
        pid_text, _separator, command_line = line.partition("\t")
        if not command_line and " " in pid_text:
            pid_text, _separator, command_line = pid_text.partition(" ")
        try:
            pid = int(pid_text.strip())
        except ValueError:
            continue
        if _is_detector_command(command_line):
            return pid
    return None


def _detector_pid() -> int | None:
    _poll_process()
    if _process is not None:
        return _process.pid

    pid = _read_detector_pid()
    if pid is None:
        discovered_pid = _discover_detector_pid()
        if discovered_pid is not None:
            _write_detector_pid(discovered_pid)
        return discovered_pid
    if _pid_is_detector(pid):
        return pid

    _clear_detector_pid()
    return None


def _terminate_pid(pid: int) -> int | None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T"], capture_output=True, text=True, timeout=10)
        if _pid_is_detector(pid):
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        return None

    os.kill(pid, signal.SIGTERM)
    deadline = time.time() + 10
    while time.time() < deadline:
        if not _pid_is_detector(pid):
            return 0
        time.sleep(0.2)

    os.kill(pid, signal.SIGKILL)
    return None


def _validate_active_cameras_for_start() -> None:
    db = _get_camera_db()
    active_cameras = db.list_active_cameras(include_secret=True)
    if not active_cameras:
        raise HTTPException(
            status_code=400,
            detail="Assign at least one active camera slot before starting detection.",
        )

    failures: list[str] = []
    for camera in active_cameras:
        result = _test_camera_stream(str(camera["stream_url"]))
        db.set_status(camera["id"], result["status"])
        if result["status"] != "connected":
            slot = camera.get("slot_number") or "-"
            failures.append(f"Slot {slot} ({camera['name']}): {result['message']}")

    if failures:
        raise HTTPException(
            status_code=400,
            detail="Cannot start detection until active camera slots are reachable. "
            + " ".join(failures),
        )

    _sync_config_active_cameras(db)


def _status() -> dict[str, Any]:
    pid = _detector_pid()
    return {
        "running": pid is not None,
        "pid": pid,
        "started_at": _started_at,
        "uptime_seconds": round(time.time() - _started_at, 1)
        if _started_at
        else 0,
        "last_exit_code": _last_exit_code,
        "health": _read_json(DETECTION_HEALTH_PATH),
        "stdout_tail": _tail_file(DETECTION_STDOUT_PATH, 40),
        "stderr_tail": _tail_file(DETECTION_STDERR_PATH, 40),
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


@app.get("/api/cameras")
def list_cameras() -> dict[str, Any]:
    db = _get_camera_db()
    cameras = db.list_cameras(include_secret=False)
    active_cameras = [camera for camera in cameras if camera["is_active"]]
    active = active_cameras[0] if active_cameras else None
    return {"cameras": cameras, "active_camera": active, "active_cameras": active_cameras}


@app.post("/api/cameras/test")
def test_camera_stream(request: CameraTestRequest) -> dict[str, Any]:
    return _test_camera_stream(request.stream_url)


@app.post("/api/cameras")
def save_camera(camera: CameraCreate) -> dict[str, Any]:
    db = _get_camera_db()
    _endpoint, validation_error = _camera_stream_endpoint(camera.stream_url)
    if validation_error:
        raise HTTPException(status_code=400, detail=validation_error)

    test_result = (
        _test_camera_stream(camera.stream_url)
        if camera.test_connection
        else {"status": "unknown", "message": "Saved without testing."}
    )
    saved = db.add_camera(
        name=camera.name.strip(),
        stream_url=camera.stream_url.strip(),
        status=test_result["status"],
    )

    active = None
    if camera.make_active and test_result["status"] == "connected":
        slot_number = camera.slot_number or _next_available_slot(db.list_cameras(include_secret=False))
        active = db.assign_slot(saved["id"], slot_number)
        _sync_config_active_cameras(db)
        if _status()["running"]:
            stop_detection()
            start_detection(StartRequest())

    cameras = db.list_cameras(include_secret=False)
    active_cameras = [row for row in cameras if row["is_active"]]
    return {
        "camera": db.get_camera(saved["id"], include_secret=False),
        "active_camera": db.get_camera(active["id"], include_secret=False) if active else None,
        "active_cameras": active_cameras,
        "test": test_result,
        "cameras": cameras,
    }


@app.post("/api/camera-controller")
def save_camera_controller(controller: CameraControllerCreate) -> dict[str, Any]:
    last_slot = controller.start_slot + controller.channel_count - 1
    if last_slot > MAX_CAMERA_SLOTS:
        raise HTTPException(
            status_code=400,
            detail=f"Controller channels would exceed slot {MAX_CAMERA_SLOTS}. "
            f"Use fewer channels or a lower start slot.",
        )

    endpoint = _controller_endpoint(controller)
    if not endpoint["host"]:
        raise HTTPException(status_code=400, detail="Controller IP/host is required.")

    controller_error = None
    if controller.test_controller:
        controller_error = _check_camera_endpoint(endpoint)
        if controller_error:
            controller_error = _redact_sensitive_text(controller_error)

    db = _get_camera_db()
    saved_cameras = []
    test_results = []
    controller_reachable = controller_error is None

    for index in range(controller.channel_count):
        channel = controller.channel_start + index
        slot = controller.start_slot + index
        stream_url = _controller_stream_url(controller, channel)

        if controller.test_streams and controller_reachable:
            test_result = _test_camera_stream(stream_url)
        elif controller_reachable:
            test_result = {
                "status": "connected",
                "message": f"Controller endpoint {endpoint['host']}:{endpoint['port']} is reachable.",
            }
        else:
            test_result = {
                "status": "failed",
                "message": controller_error or "Controller endpoint is not reachable.",
            }

        saved = db.add_camera(
            name=_controller_camera_name(controller, channel, slot),
            stream_url=stream_url,
            status=test_result["status"],
        )

        active = None
        if controller.make_active and test_result["status"] == "connected":
            active = db.assign_slot(saved["id"], slot)

        saved_cameras.append(db.get_camera(saved["id"], include_secret=False))
        test_results.append(
            {
                "camera_id": saved["id"],
                "slot_number": slot,
                "channel": channel,
                "status": test_result["status"],
                "message": test_result["message"],
                "active": active is not None,
            }
        )

    if controller.make_active and any(result["active"] for result in test_results):
        _sync_config_active_cameras(db)
        if _status()["running"]:
            stop_detection()
            start_detection(StartRequest())

    cameras = db.list_cameras(include_secret=False)
    active_cameras = [row for row in cameras if row["is_active"]]
    return {
        "controller": {
            "name": controller.name.strip(),
            "host": endpoint["host"],
            "port": endpoint["port"],
            "protocol": endpoint["scheme"],
            "reachable": controller_reachable,
            "message": controller_error
            or f"Controller endpoint {endpoint['host']}:{endpoint['port']} is reachable.",
        },
        "created": saved_cameras,
        "results": test_results,
        "cameras": cameras,
        "active_cameras": active_cameras,
        "active_camera": active_cameras[0] if active_cameras else None,
    }


@app.post("/api/cameras/{camera_id}/test")
def test_saved_camera(camera_id: int) -> dict[str, Any]:
    db = _get_camera_db()
    camera = db.get_camera(camera_id, include_secret=True)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found.")

    result = _test_camera_stream(camera["stream_url"])
    updated = db.set_status(camera_id, result["status"])
    return {"camera": updated, "test": result}


@app.post("/api/cameras/{camera_id}/activate")
def set_active_camera(
    camera_id: int, request: CameraSlotRequest | None = None
) -> dict[str, Any]:
    db = _get_camera_db()
    request = request or CameraSlotRequest()
    active = db.assign_slot(camera_id, request.slot_number)
    if active is None:
        raise HTTPException(status_code=404, detail="Camera not found.")

    _sync_config_active_cameras(db)
    restarted = False
    if _status()["running"]:
        stop_detection()
        start_detection(StartRequest())
        restarted = True

    cameras = db.list_cameras(include_secret=False)
    active_cameras = [row for row in cameras if row["is_active"]]
    return {
        "active_camera": db.get_camera(camera_id, include_secret=False),
        "active_cameras": active_cameras,
        "cameras": cameras,
        "restarted": restarted,
    }


@app.delete("/api/camera-slots/{slot_number}")
def clear_camera_slot(slot_number: int) -> dict[str, Any]:
    if slot_number < 1 or slot_number > MAX_CAMERA_SLOTS:
        raise HTTPException(
            status_code=400,
            detail=f"Slot number must be between 1 and {MAX_CAMERA_SLOTS}.",
        )

    db = _get_camera_db()
    db.clear_slot(slot_number)
    _sync_config_active_cameras(db)
    restarted = False
    if _status()["running"]:
        stop_detection()
        start_detection(StartRequest())
        restarted = True

    cameras = db.list_cameras(include_secret=False)
    active_cameras = [row for row in cameras if row["is_active"]]
    return {
        "active_camera": active_cameras[0] if active_cameras else None,
        "active_cameras": active_cameras,
        "cameras": cameras,
        "restarted": restarted,
    }


@app.post("/api/start")
def start_detection(request: StartRequest | None = None) -> dict[str, Any]:
    global _process, _started_at, _last_exit_code, _stdout_handle, _stderr_handle
    request = request or StartRequest()
    if _detector_pid() is not None:
        raise HTTPException(status_code=409, detail="Detection is already running.")
    _validate_active_cameras_for_start()

    DETECTION_STDOUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _stdout_handle = DETECTION_STDOUT_PATH.open("w", encoding="utf-8", buffering=1)
    _stderr_handle = DETECTION_STDERR_PATH.open("w", encoding="utf-8", buffering=1)
    _stdout_handle.write(f"\n--- detection start {_now_iso()} config={request.config_path} ---\n")
    DETECTION_HEALTH_PATH.write_text(
        json.dumps(
            {
                "state": "starting",
                "error": None,
                "frames_read": 0,
                "last_frame_at": None,
                "last_detection_count": 0,
                "last_tracked_count": 0,
                "updated_at": _now_iso(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

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
        stdout=_stdout_handle,
        stderr=_stderr_handle,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
        start_new_session=os.name != "nt",
    )
    _started_at = time.time()
    _last_exit_code = None
    _write_detector_pid(_process.pid)
    return _status()


@app.post("/api/stop")
def stop_detection() -> dict[str, Any]:
    global _process, _started_at, _last_exit_code, _stdout_handle, _stderr_handle
    process = _process
    pid = _detector_pid()
    if pid is None:
        return _status()

    if process is None:
        _last_exit_code = _terminate_pid(pid)
    elif os.name == "nt":
        _terminate_pid(process.pid)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        _last_exit_code = process.returncode
    else:
        os.killpg(process.pid, signal.SIGTERM)

        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        _last_exit_code = process.returncode

    _process = None
    _started_at = None
    _clear_detector_pid()
    DETECTION_HEALTH_PATH.write_text(
        json.dumps(
            {
                "state": "stopped",
                "error": None,
                "frames_read": 0,
                "last_frame_at": None,
                "last_detection_count": 0,
                "last_tracked_count": 0,
                "updated_at": _now_iso(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    for handle in (_stdout_handle, _stderr_handle):
        if handle is not None:
            handle.close()
    _stdout_handle = None
    _stderr_handle = None
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


@app.get("/api/detection/logs")
def detection_logs(limit: int = 120) -> dict[str, Any]:
    return {
        "health": _read_json(DETECTION_HEALTH_PATH),
        "stdout": _tail_file(DETECTION_STDOUT_PATH, limit),
        "stderr": _tail_file(DETECTION_STDERR_PATH, limit),
    }


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
async def live_mjpeg(slot: int | None = None, camera: str | None = None):
    """Return a multipart/x-mixed-replace MJPEG stream by repeatedly
    reading the latest frame written by the detector. Use ?slot=1, ?slot=2,
    etc. to view individual active camera screens.
    """

    boundary = "frame"
    latest_paths = _live_feed_paths(slot=slot, camera=camera)

    async def frame_generator():
        while True:
            latest = next((path for path in latest_paths if path.exists()), None)
            if latest is not None:
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


def _live_feed_path(slot: int | None = None, camera: str | None = None) -> Path:
    if slot is not None:
        return SNAPSHOT_DIR / f"latest_slot_{slot}.jpg"
    if camera:
        safe_name = "".join(ch if ch.isalnum() else "_" for ch in camera).strip("_") or "camera"
        return SNAPSHOT_DIR / f"latest_{safe_name}.jpg"
    return SNAPSHOT_DIR / "latest.jpg"


def _live_feed_paths(slot: int | None = None, camera: str | None = None) -> list[Path]:
    paths = [_live_feed_path(slot=slot, camera=camera)]
    fallback = SNAPSHOT_DIR / "latest.jpg"
    if fallback not in paths:
        paths.append(fallback)
    return paths


app.mount("/assets", StaticFiles(directory=DASHBOARD_DIR), name="dashboard-assets")
app.mount("/snapshots", StaticFiles(directory=SNAPSHOT_DIR), name="snapshots")
