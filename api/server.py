"""
FastAPI control server for the AI Vision Assistant dashboard.

Run:
    uvicorn api.server:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import io
import ipaddress
import json
import os
import re
import secrets
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

import yaml
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
import asyncio
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (
    AuthenticatorAttachment,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from discovery import discover_device  # noqa: E402
from discovery.portscan import DiscoveryHostError, resolve_and_guard  # noqa: E402
from discovery.providers import StreamCredentials, enumerate_streams  # noqa: E402
from database.access_control_db import AccessControlDB  # noqa: E402
from database.camera_db import CameraDB  # noqa: E402
from database.device_db import DeviceDB  # noqa: E402
from database.accounts_db import AccountsDB  # noqa: E402
from database.catalog_db import CatalogDB  # noqa: E402
from database.security_audit_db import SecurityAuditDB  # noqa: E402
from database.tracking_db import TrackingDB  # noqa: E402
from database.warehouse_db import WarehouseDB  # noqa: E402
from detection.detector import Detector  # noqa: E402
from detection.spatial import SpatialAnalyzer  # noqa: E402
from streams import StreamManager, StreamSessionConfig  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "config.yaml"
LOG_PATH = ROOT / "logs" / "events.log"
SNAPSHOT_DIR = ROOT / "snapshots"
INVENTORY_PATH = ROOT / "logs" / "inventory.json"
INVENTORY_IMAGE_DIR = SNAPSHOT_DIR / "inventory"
CATALOG_IMAGE_DIR = SNAPSHOT_DIR / "catalog"
DASHBOARD_V2_DIR = ROOT / "dashboard-v2"
TRACKING_DB_PATH = ROOT / "database" / "tracking.db"
WAREHOUSE_DB_PATH = ROOT / "database" / "warehouse.db"
CAMERA_DB_PATH = ROOT / "database" / "cameras.db"
DEVICE_DB_PATH = ROOT / "database" / "devices.db"
SECURITY_AUDIT_DB_PATH = ROOT / "database" / "security_audit.db"
ACCESS_CONTROL_DB_PATH = ROOT / "database" / "access_control.db"
CATALOG_DB_PATH = ROOT / "database" / "catalog.db"
ACCOUNTS_DB_PATH = ROOT / "database" / "accounts.db"
DETECTION_STDOUT_PATH = ROOT / "logs" / "detection_stdout.log"
DETECTION_STDERR_PATH = ROOT / "logs" / "detection_stderr.log"
DETECTION_HEALTH_PATH = ROOT / "logs" / "detection_health.json"
DETECTION_PID_PATH = ROOT / "logs" / "detection.pid"
MAX_CAMERA_SLOTS = 50
DEFAULT_ALLOWED_ORIGINS = [
    "https://ai-vision-dashboard-phi.vercel.app",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app = FastAPI(title="AI Vision Control API", version="0.1.0")


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name, "")
    values = [value.strip().rstrip("/") for value in raw.split(",") if value.strip()]
    return values or default


_tracking_db: TrackingDB | None = None
_warehouse_db: WarehouseDB | None = None
_camera_db: CameraDB | None = None
_device_db: DeviceDB | None = None
_stream_manager: StreamManager | None = None
_security_audit_db: SecurityAuditDB | None = None
_access_control_db: AccessControlDB | None = None
_catalog_db: CatalogDB | None = None
_catalog_yolo_detector: Detector | None = None
_catalog_yolo_detector_key: tuple[Any, ...] | None = None
_accounts_db: AccountsDB | None = None
_rate_limits: dict[tuple[str, str, int], int] = {}
_watchdog_task: asyncio.Task | None = None
_catalog_recognition_task: asyncio.Task | None = None
_catalog_run_lock: asyncio.Lock | None = None
_manual_stop_requested = False
_watchdog_last_start_attempt = 0.0

# On-demand "run recognition for a few minutes" mode (POST
# /api/catalog/recognition/run-live): in-memory only, keyed by scope_id.
# Deliberately not persisted - if the server restarts mid-run the run is
# simply gone, which is fine for an ephemeral progress indicator.
_live_catalog_runs: dict[str, dict[str, Any]] = {}
_live_catalog_tasks: dict[str, asyncio.Task] = {}
CATALOG_LIVE_RUN_DURATION_SECONDS = 240
CATALOG_LIVE_RUN_SAMPLE_INTERVAL_SECONDS = 8

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "super_admin": {
        "view_dashboard",
        "view_organizations",
        "manage_organizations",
        "view_users",
        "manage_users",
        "view_permissions",
        "manage_permissions",
        "view_controllers",
        "configure_cameras",
        "view_cameras",
        "view_live_monitoring",
        "view_products",
        "manage_products",
        "configure_ai",
        "view_counts",
        "correct_counts",
        "view_alerts",
        "manage_alerts",
        "view_analytics",
        "view_reports",
        "export_reports",
        "view_system_health",
        "configure_system",
        "view_audit_logs",
        "manage_integrations",
        "view_settings",
    },
    "company_admin": {
        "view_dashboard",
        "view_users",
        "manage_users",
        "view_permissions",
        "view_controllers",
        "configure_cameras",
        "view_cameras",
        "view_live_monitoring",
        "view_products",
        "manage_products",
        "view_counts",
        "correct_counts",
        "view_alerts",
        "manage_alerts",
        "view_analytics",
        "view_reports",
        "export_reports",
        "view_system_health",
        "view_audit_logs",
        "view_settings",
    },
    "factory_manager": {
        "view_dashboard",
        "view_cameras",
        "view_live_monitoring",
        "view_products",
        "view_counts",
        "correct_counts",
        "view_alerts",
        "view_analytics",
        "view_reports",
        "export_reports",
        "view_system_health",
    },
    "warehouse_manager": {
        "view_dashboard",
        "view_cameras",
        "view_live_monitoring",
        "view_products",
        "view_counts",
        "correct_counts",
        "view_alerts",
        "view_reports",
        "export_reports",
    },
    "operator": {
        "view_dashboard",
        "view_cameras",
        "view_live_monitoring",
        "view_counts",
        "correct_counts",
        "view_alerts",
        "view_reports",
    },
    "viewer": {
        "view_dashboard",
        "view_cameras",
        "view_live_monitoring",
        "view_counts",
        "view_alerts",
        "view_reports",
    },
    "technician": {
        "view_dashboard",
        "view_controllers",
        "configure_cameras",
        "view_cameras",
        "view_live_monitoring",
        "view_system_health",
        "view_settings",
    },
}

DASHBOARD_V2_MODULES: dict[str, list[dict[str, str]]] = {
    "head": [
        {"id": "overview", "label": "Dashboard Overview", "permission": "view_dashboard"},
        {"id": "organizations", "label": "Organizations", "permission": "view_organizations"},
        {"id": "users", "label": "Users & Roles", "permission": "view_users"},
        {"id": "permissions", "label": "Permissions", "permission": "view_permissions"},
        {"id": "controllers", "label": "Controllers / NVR", "permission": "view_controllers"},
        {"id": "cameras", "label": "Cameras", "permission": "view_cameras"},
        {"id": "live", "label": "Live Monitoring", "permission": "view_live_monitoring"},
        {"id": "products", "label": "Products", "permission": "view_products"},
        {"id": "ai", "label": "AI Management", "permission": "configure_ai"},
        {"id": "counting", "label": "Counting Management", "permission": "view_counts"},
        {"id": "alerts", "label": "Alerts Center", "permission": "view_alerts"},
        {"id": "analytics", "label": "Analytics", "permission": "view_analytics"},
        {"id": "reports", "label": "Reports", "permission": "view_reports"},
        {"id": "health", "label": "System Health", "permission": "view_system_health"},
        {"id": "audit", "label": "Audit Logs", "permission": "view_audit_logs"},
        {"id": "integrations", "label": "Integrations", "permission": "manage_integrations"},
        {"id": "settings", "label": "Settings", "permission": "view_settings"},
    ],
    "user": [
        {"id": "home", "label": "Home", "permission": "view_dashboard"},
        {"id": "live", "label": "Live Monitoring", "permission": "view_live_monitoring"},
        {"id": "counting", "label": "Counting", "permission": "view_counts"},
        {"id": "shift", "label": "Current Shift", "permission": "view_counts"},
        {"id": "verification", "label": "Verification Tasks", "permission": "correct_counts"},
        {"id": "alerts", "label": "Alerts", "permission": "view_alerts"},
        {"id": "reports", "label": "Reports", "permission": "view_reports"},
        {"id": "activity", "label": "Activity History", "permission": "view_reports"},
        {"id": "profile", "label": "Profile", "permission": "view_dashboard"},
    ],
}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


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


def _get_catalog_db() -> CatalogDB:
    global _catalog_db
    if _catalog_db is None:
        _catalog_db = CatalogDB(db_path=str(CATALOG_DB_PATH))
    return _catalog_db


def _get_accounts_db() -> AccountsDB:
    global _accounts_db
    if _accounts_db is None:
        _accounts_db = AccountsDB(db_path=str(ACCOUNTS_DB_PATH))
    return _accounts_db


def _get_camera_db() -> CameraDB:
    global _camera_db
    if _camera_db is None:
        _camera_db = CameraDB(db_path=str(CAMERA_DB_PATH))
        _seed_cameras_from_environment(_camera_db)
        config = _read_yaml(CONFIG_PATH) if CONFIG_PATH.exists() else {}
        first_camera = (config.get("cameras") or [{"name": "Camera 1", "source": 0}])[0]
        _camera_db.ensure_default_camera(
            name=str(first_camera.get("name", "Camera 1")),
            stream_url=str(first_camera.get("source", 0)),
        )
    return _camera_db


def _get_device_db() -> DeviceDB:
    global _device_db
    if _device_db is None:
        _device_db = DeviceDB(db_path=str(DEVICE_DB_PATH))
    return _device_db


def _get_stream_manager() -> StreamManager:
    global _stream_manager
    if _stream_manager is None:
        _stream_manager = StreamManager(snapshot_dir=SNAPSHOT_DIR)
    return _stream_manager


def _ensure_streams_from_active_cameras() -> dict[str, Any]:
    db = _get_camera_db()
    if db is None or not hasattr(db, "list_active_cameras"):
        return {"streams": []}
    active = db.list_active_cameras(include_secret=True)
    return _get_stream_manager().ensure_from_cameras(active)


def _start_stream_for_camera(camera: dict[str, Any]) -> dict[str, Any]:
    return _get_stream_manager().start(
        StreamSessionConfig(
            channel_id=str(camera["id"]),
            name=str(camera["name"]),
            source=str(camera["stream_url"]),
            slot_number=camera.get("slot_number"),
            snapshot_dir=SNAPSHOT_DIR,
        )
    )


def _seed_cameras_from_environment(db: CameraDB) -> None:
    """Optional boot-time camera seeding for stateless cloud deployments.

    DigitalOcean App Platform files can reset on rebuild. These env vars let the
    backend recreate controller channels on startup so the dashboard does not
    fall back to only the checked-in demo camera.
    """

    host = os.getenv("CAMERA_CONTROLLER_HOST", "").strip()
    if not host:
        return

    existing_active = db.list_active_cameras(include_secret=False)
    if existing_active and not (
        len(existing_active) == 1
        and str(existing_active[0].get("masked_stream_url", "")).strip().lower() == "dummy"
    ):
        return

    protocol = os.getenv("CAMERA_CONTROLLER_PROTOCOL", "rtsp").strip().lower()
    if protocol not in STREAM_DEFAULT_PORTS:
        protocol = "rtsp"

    try:
        port = int(os.getenv("CAMERA_CONTROLLER_PORT", str(STREAM_DEFAULT_PORTS[protocol])))
        channel_count = int(os.getenv("CAMERA_CONTROLLER_CHANNEL_COUNT", "10"))
        channel_start = int(os.getenv("CAMERA_CONTROLLER_CHANNEL_START", "1"))
        start_slot = int(os.getenv("CAMERA_CONTROLLER_START_SLOT", "1"))
    except ValueError:
        return

    controller = CameraControllerCreate(
        name=os.getenv("CAMERA_CONTROLLER_NAME", "Warehouse NVR Substream"),
        host=host,
        protocol=protocol,
        port=port,
        username=os.getenv("CAMERA_CONTROLLER_USERNAME") or None,
        password=os.getenv("CAMERA_CONTROLLER_PASSWORD") or None,
        channel_count=max(1, min(channel_count, MAX_CAMERA_SLOTS)),
        channel_start=max(1, channel_start),
        start_slot=max(1, min(start_slot, MAX_CAMERA_SLOTS)),
        stream_path_template=os.getenv(
            "CAMERA_CONTROLLER_STREAM_TEMPLATE",
            "/Streaming/Channels/{channel}01",
        ),
        camera_name_template=os.getenv(
            "CAMERA_CONTROLLER_CAMERA_NAME_TEMPLATE",
            "{controller} Camera {channel}",
        ),
        make_active=True,
        # Unlike the dashboard's Add NVR flow, this seed path used to skip
        # every connectivity check and activate channels unconditionally -
        # stale or wrong credentials baked into old environment variables
        # could silently occupy real slots forever without ever actually
        # working, since nothing ever tested them.
        test_controller=True,
        test_streams=True,
        require_public=False,
    )

    try:
        _register_controller_channels(controller, db)
    except HTTPException as exc:
        print(f"WARNING: environment camera seed skipped: {exc.detail}")

    _sync_config_active_cameras(db)


def _get_security_audit_db() -> SecurityAuditDB:
    global _security_audit_db
    if _security_audit_db is None:
        _security_audit_db = SecurityAuditDB(db_path=str(SECURITY_AUDIT_DB_PATH))
    return _security_audit_db


def _get_access_control_db() -> AccessControlDB:
    global _access_control_db
    if _access_control_db is None:
        _access_control_db = AccessControlDB(db_path=str(ACCESS_CONTROL_DB_PATH))
    return _access_control_db


def _admin_api_key() -> str:
    return os.getenv("ADMIN_API_KEY", "").strip()


def _security_enabled() -> bool:
    return bool(_admin_api_key())


def _request_actor(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def _v2_user_email(request: Request) -> str:
    user = _v2_session_user(request)
    if user:
        return str(user["email"]).strip().lower()
    return (
        request.query_params.get("user_email")
        or request.headers.get("x-ai-user-email")
        or "admin@ai-vision.local"
    ).strip().lower()


def _v2_bearer_token(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return ""


def _v2_session_user(request: Request) -> dict[str, Any] | None:
    token = _v2_bearer_token(request)
    if not token:
        return None
    return _get_access_control_db().get_user_by_session_token(token)


def _v2_rp_id(request: Request) -> str:
    origin = request.headers.get("origin", "")
    if origin:
        host = urlsplit(origin).hostname
        if host:
            return host
    return request.url.hostname or "localhost"


def _v2_expected_origins(request: Request) -> list[str]:
    current = f"{request.url.scheme}://{request.url.netloc}"
    browser_origin = request.headers.get("origin", "").rstrip("/")
    configured = _env_list("WEBAUTHN_ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS)
    origins = {current, browser_origin, *configured, "http://localhost:8000", "http://127.0.0.1:8000"}
    return sorted(origin.rstrip("/") for origin in origins if origin)


def _v2_public_key_options(options: Any) -> dict[str, Any]:
    return json.loads(options_to_json(options))


def _v2_dashboard(request: Request) -> dict[str, Any]:
    ac = _get_access_control_db()
    session_user = _v2_session_user(request)
    if session_user:
        return ac.resolve_dashboard(user_id=int(session_user["id"]))
    email = (
        request.query_params.get("user_email")
        or request.headers.get("x-ai-user-email")
        or "admin@ai-vision.local"
    ).strip().lower()
    user = ac.get_user_by_email(email)
    if user and user.get("has_password"):
        raise HTTPException(status_code=401, detail="Login required for this account.")
    return ac.resolve_dashboard(email=email)


def _v2_auth_response(user: dict[str, Any], token: dict[str, Any]) -> dict[str, Any]:
    dashboard = _get_access_control_db().resolve_dashboard(user_id=int(user["id"]))
    return {"user": dashboard["user"], "modules": dashboard["modules"], **token}



def _v2_require_permission(request: Request, permission: str) -> dict[str, Any]:
    dashboard = _v2_dashboard(request)
    if permission not in set(dashboard.get("permissions", [])):
        raise HTTPException(status_code=403, detail=f"Permission required: {permission}")
    return dashboard


def _v2_require_module(request: Request, module_code: str, permission: str | None = None) -> dict[str, Any]:
    dashboard = _v2_dashboard(request)
    modules = {module["code"] for module in dashboard.get("modules", [])}
    if module_code not in modules:
        raise HTTPException(status_code=403, detail=f"Module not assigned: {module_code}")
    if permission and permission not in set(dashboard.get("permissions", [])):
        raise HTTPException(status_code=403, detail=f"Permission required: {permission}")
    return dashboard


def _is_public_path(path: str) -> bool:
    return (
        path == "/"
        or path == "/api/status"
        or path.startswith("/assets/")
        or path in {"/favicon.ico", "/robots.txt"}
    )


def _valid_api_key(request: Request) -> bool:
    expected = _admin_api_key()
    if not expected:
        return True
    provided = request.headers.get("x-api-key") or request.query_params.get("api_key") or ""
    return secrets.compare_digest(provided, expected)


def _normalize_role(role: str | None) -> str:
    value = (role or "super_admin").strip().lower().replace(" ", "_").replace("-", "_")
    return value if value in ROLE_PERMISSIONS else "viewer"


def _parse_csv_header(value: str | None) -> set[str]:
    if not value:
        return set()
    return {item.strip() for item in value.split(",") if item.strip()}


def _rbac_context(request: Request) -> dict[str, Any]:
    role = _normalize_role(request.headers.get("x-ai-role"))
    base_permissions = set(ROLE_PERMISSIONS.get(role, set()))
    explicit_permissions = _parse_csv_header(request.headers.get("x-ai-permissions"))
    denied_permissions = _parse_csv_header(request.headers.get("x-ai-deny-permissions"))
    permissions = sorted((base_permissions | explicit_permissions) - denied_permissions)
    return {
        "user": {
            "id": request.headers.get("x-ai-user-id", "demo-super-admin"),
            "name": request.headers.get("x-ai-user-name", "Demo Super Admin"),
            "email": request.headers.get("x-ai-user-email", "admin@ai-vision.local"),
        },
        "role": role,
        "role_label": role.replace("_", " ").title(),
        "scope": {
            "company": request.headers.get("x-ai-company", "All Companies"),
            "factory": request.headers.get("x-ai-factory", "All Factories"),
            "warehouse": request.headers.get("x-ai-warehouse", "All Warehouses"),
            "production_line": request.headers.get("x-ai-production-line", "All Lines"),
            "camera": request.headers.get("x-ai-camera", "All Cameras"),
        },
        "permissions": permissions,
    }


def _authorized_modules(surface: str, permissions: set[str]) -> list[dict[str, str]]:
    modules = DASHBOARD_V2_MODULES.get(surface, [])
    return [module for module in modules if module["permission"] in permissions]


def _require_permission(request: Request, permission: str) -> dict[str, Any]:
    context = _rbac_context(request)
    if permission not in set(context["permissions"]):
        raise HTTPException(
            status_code=403,
            detail=f"Permission required: {permission}",
        )
    return context


def _rate_limit(request: Request) -> JSONResponse | None:
    rate_path = request.url.path
    if rate_path == "/api/live_frame":
        # Live snapshots are intentionally requested more frequently than the
        # control API. This remains isolated per camera below, so one feed
        # cannot consume another feed's allowance.
        limit = int(os.getenv("LIVE_FRAME_RATE_LIMIT_PER_MINUTE", "300"))
    else:
        limit = int(os.getenv("SECURITY_RATE_LIMIT_PER_MINUTE", "120"))
    if limit <= 0:
        return None
    actor = _request_actor(request)
    window = int(time.time() // 60)
    # Live camera frames are polled independently per slot. Keep the existing
    # per-route limit, but isolate each feed so ten healthy cameras do not
    # exhaust one shared request bucket.
    if rate_path == "/api/live_frame":
        slot = request.query_params.get("slot", "")
        camera = request.query_params.get("camera", "")
        rate_path = f"{rate_path}?slot={slot}&camera={camera}"
    key = (actor, rate_path, window)
    _rate_limits[key] = _rate_limits.get(key, 0) + 1
    if len(_rate_limits) > 5000:
        stale_windows = {window - 2, window - 1, window}
        for old_key in list(_rate_limits):
            if old_key[2] not in stale_windows:
                _rate_limits.pop(old_key, None)
    if _rate_limits[key] > limit:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Try again shortly."},
            headers={"X-RateLimit-Limit": str(limit), "X-RateLimit-Remaining": "0"},
        )
    return None


def _audit(action: str, payload: dict[str, Any], actor: str = "system") -> None:
    try:
        _get_security_audit_db().append(actor=actor, action=action, payload=payload)
    except Exception:
        # Audit logging should never take the control API down.
        pass


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") or path.startswith("/snapshots/"):
        limited = _rate_limit(request)
        if limited is not None:
            return limited

    if _security_enabled() and not _is_public_path(path):
        if request.method != "OPTIONS" and (path.startswith("/api/") or path.startswith("/snapshots/")):
            if not _valid_api_key(request):
                actor = _request_actor(request)
                _audit(
                    "auth.denied",
                    {"method": request.method, "path": path},
                    actor=actor,
                )
                return JSONResponse(status_code=401, content={"detail": "Valid API key required."})

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    elif path.startswith("/dashboard-v2/"):
        # StaticFiles never sets an explicit Cache-Control header for
        # dashboard-v2/assets/*, which lets the Vercel edge (proxying via
        # rewrites) apply its own default caching for asset-looking paths —
        # independent of the ?v= query-string bump. That let a stale
        # pre-migration app.js keep running in production and silently
        # create client-only "accounts" that never reached the server. Force
        # revalidation on every dashboard-v2 asset so a fresh deploy is
        # always picked up.
        response.headers["Cache-Control"] = "no-cache"

    if path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"}:
        actor = _request_actor(request)
        _audit(
            "api.mutation",
            {"method": request.method, "path": path, "status_code": response.status_code},
            actor=actor,
        )
    return response


# Registered after security_middleware (not alongside the other
# app.add_middleware calls near the top of the file) so that CORSMiddleware
# ends up as the OUTERMOST layer — Starlette wraps in the order middleware is
# added, last-added-wraps-outermost. With CORS registered before
# security_middleware, an early 401 returned by security_middleware (e.g.
# when ADMIN_API_KEY is set and no key is supplied) never reached
# CORSMiddleware at all, so the response carried no
# Access-Control-Allow-Origin header — the browser reported it as a CORS
# failure instead of surfacing the real 401, which would silently break
# every cross-origin caller (including the Vercel-hosted dashboard) the
# moment API-key auth was turned on.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_env_list("ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-API-Key",
        "X-AI-Company",
        "X-AI-Role",
        "X-AI-User-Email",
        "X-AI-User-Name",
        "X-Requested-With",
    ],
)

_process: subprocess.Popen | None = None
_started_at: float | None = None
_last_exit_code: int | None = None
_stdout_handle = None
_stderr_handle = None


class StartRequest(BaseModel):
    no_display: bool = True
    config_path: str = "config/config.yaml"


class ConfigPatch(BaseModel):
    model_path: str | None = Field(default=None, min_length=1)
    confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    image_size: int | None = Field(default=None, ge=320, le=1920)
    device: str | None = None
    classes: list[str] | None = None
    class_prompts: list[str] | None = None
    class_agnostic_nms: bool | None = None
    tracking_enabled: bool | None = None
    warehouse_counting_enabled: bool | None = None
    snapshots_enabled: bool | None = None
    snapshot_trigger_classes: list[str] | None = None
    snapshot_cooldown_seconds: int | None = Field(default=None, ge=0)
    logging_enabled: bool | None = None
    recognition_model: str | None = Field(default=None, min_length=1)


class CompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class CompanyRename(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class CameraConfigUpdate(BaseModel):
    cameraConfig: dict[str, Any]  # noqa: N815 - matches the JS wire shape


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    login: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)
    access_camera: bool = False
    access_analytics: bool = False


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    login: str | None = Field(default=None, min_length=1, max_length=80)
    password: str | None = Field(default=None, min_length=1, max_length=200)
    access_camera: bool | None = None
    access_analytics: bool | None = None


class ProfileUpdate(BaseModel):
    login: str | None = Field(default=None, min_length=1, max_length=80)
    password: str | None = Field(default=None, min_length=1, max_length=200)
    avatar: str | None = None
    remove_avatar: bool = False


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


class CameraCleanupRequest(BaseModel):
    name_prefix: str = Field(min_length=1)


class DiscoveryScanRequest(BaseModel):
    host: str = Field(min_length=1, max_length=255)


class DiscoveryConnectRequest(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    protocol: str = Field(default="rtsp", pattern="^(rtsp|http|https)$")
    port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = None
    password: str | None = None
    vendor: str | None = None  # fingerprint hint carried from the scan step
    channel_count: int = Field(default=1, ge=1, le=MAX_CAMERA_SLOTS)
    name: str = Field(default="Camera", min_length=1, max_length=60)
    make_active: bool = True
    test_streams: bool = True


class V2DeviceDiscoverRequest(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    name: str | None = Field(default=None, max_length=80)


class V2DeviceAuthenticateRequest(BaseModel):
    protocol: str = Field(default="rtsp", pattern="^(rtsp|http|https)$")
    port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = None
    password: str | None = None
    channel_count: int = Field(default=1, ge=1, le=MAX_CAMERA_SLOTS)
    make_active: bool = True
    test_streams: bool = False


def _v2_stream_vendor_hint(device: dict[str, Any], request: V2DeviceAuthenticateRequest) -> str | None:
    vendor = device.get("vendor")
    if vendor:
        return str(vendor)

    # Some public NVR forwards expose only RTSP/554 and do not return a brand
    # banner to the unauthenticated OPTIONS probe. The RTSP root almost never
    # carries usable video for those devices; the common Hikvision channel
    # profile is a better automatic first template while keeping vendor/path
    # choices out of the operator UI.
    if request.protocol.lower() == "rtsp":
        device_type = str(device.get("device_type") or "")
        if device_type in {"nvr_or_dvr", "ip_camera"} or request.channel_count > 1:
            return "hikvision"
    return None


class V2StreamStartRequest(BaseModel):
    slot_number: int | None = Field(default=None, ge=1, le=MAX_CAMERA_SLOTS)


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
    require_public: bool = True


class V2UserCreate(BaseModel):
    name: str = Field(min_length=1)
    email: str = Field(min_length=3)


class V2LoginRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=1)


class V2PasswordSet(BaseModel):
    password: str = Field(min_length=8)


class V2AuthPreferenceSet(BaseModel):
    preferred_auth_method: str = Field(pattern="^(biometric_first|password_first|password_and_biometric)$")


class V2PasskeyRegisterStart(BaseModel):
    name: str | None = None


class V2PasskeyRegisterFinish(BaseModel):
    challenge_id: int
    credential: dict[str, Any]
    name: str | None = None


class V2PasskeyLoginFinish(BaseModel):
    email: str = Field(min_length=3)
    challenge_id: int
    credential: dict[str, Any]


class V2PasskeyLoginStart(BaseModel):
    email: str = Field(min_length=3)


class V2RoleCreate(BaseModel):
    name: str = Field(min_length=1)
    code: str = Field(min_length=1)


class V2RoleAssignment(BaseModel):
    role_code: str = Field(min_length=1)


class V2ModuleAssignment(BaseModel):
    module_code: str = Field(min_length=1)
    effect: str = Field(pattern="^(allow|deny)$")
    display_order: int | None = Field(default=None, ge=1)


class V2PermissionAssignment(BaseModel):
    permission_code: str = Field(min_length=1)
    effect: str = Field(pattern="^(allow|deny)$")


class V2ScopeAssignment(BaseModel):
    scope_type: str = Field(pattern="^(company|factory|warehouse|production_line|zone|camera)$")
    scope_ids: list[str] = Field(default_factory=list)
    effect: str = Field(default="allow", pattern="^(allow|deny)$")


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


def _private_controller_host_message(host: str) -> str | None:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return None

    if not address.is_global:
        return (
            f"Controller host {host} is not publicly reachable from the internet. "
            "Use the controller/router public IP address or a DNS/DDNS hostname, and forward the "
            "RTSP/HTTP stream port to the controller. Private LAN addresses like 192.168.x.x, "
            "10.x.x.x, 172.16-31.x.x, and 127.x.x.x only work from the same local network."
        )
    return None


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
import subprocess
import shutil
import sys
import cv2

raw = sys.argv[1].strip()
source = int(raw) if raw.isdigit() else raw
inner_timeout = max(1, int(sys.argv[2]) - 1)

def try_open(cap_args):
    cap = cv2.VideoCapture(*cap_args)
    opened = bool(cap.isOpened())
    ok = False
    if opened:
        ok, _ = cap.read()
    if not (opened and ok):
        cap.release()
    return cap, opened, ok

def try_ffmpeg(url, timeout_seconds):
    # Mirrors cameras/camera.py's Camera._open_ffmpeg(), including
    # -skip_frame nokey (RTSP-over-TCP sessions commonly start mid-GOP,
    # which HEVC decoders tolerate far worse than H.264 - confirmed live
    # against a real Hikvision NVR streaming H.265 - so only decoding
    # self-contained keyframes sidesteps that instead of erroring out).
    # This pre-flight check has to use the exact same method the real
    # detector process does, or a camera that would actually work could
    # still get wrongly rejected here before it's ever tried for real.
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    command = [
        ffmpeg, "-rtsp_transport", "tcp", "-skip_frame", "nokey", "-fflags", "+discardcorrupt", "-i", url,
        "-f", "image2pipe", "-vcodec", "mjpeg", "-q:v", "5",
        "-an", "-threads", "1", "-loglevel", "error", "-frames:v", "1", "-",
    ]
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        return False, False
    try:
        data, _ = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            process.communicate(timeout=2.0)
        except Exception:
            pass
        return True, False, "waiting_for_frame"
    has_jpeg = b"\xff\xd8" in data and b"\xff\xd9" in data
    return has_jpeg, has_jpeg, None

try:
    note = None
    if isinstance(source, int) and os.name == "nt":
        cap = None
        opened = False
        ok = False
        for cap_args in [(source, cv2.CAP_DSHOW), (source,)]:
            cap, opened, ok = try_open(cap_args)
            if opened and ok:
                break
        cap.release()
    elif isinstance(source, str) and source.lower().startswith("rtsp://"):
        opened, ok, note = try_ffmpeg(source, inner_timeout)
    else:
        cap, opened, ok = try_open((source,))
        cap.release()
    print(json.dumps({"ok": bool(opened and ok), "opened": opened, "frame_read": bool(ok), "note": note}))
except Exception as exc:
    print(json.dumps({"ok": False, "error": str(exc)}))
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", code, stream_url, str(timeout_seconds)],
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

    if payload.get("opened") and payload.get("note") == "waiting_for_frame":
        response = {
            "status": "connected",
            "message": (
                "Camera endpoint is reachable and FFmpeg stayed connected, but no keyframe "
                "arrived before the short test timeout. Stream Manager will keep waiting "
                "and reconnecting until live frames arrive."
            ),
        }
        if endpoint is not None:
            response["details"] = {
                "host": endpoint["host"],
                "port": endpoint["port"],
                "scheme": endpoint["scheme"],
                "endpoint_reachable": True,
                "opencv_opened": True,
                "frame_read": False,
                "waiting_for_frame": True,
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


def _catalog_interval_hours() -> int:
    return max(1, int(os.getenv("CATALOG_RECOGNITION_INTERVAL_HOURS", "12")))


def _catalog_scope(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-")
    if not cleaned:
        raise HTTPException(status_code=400, detail="A valid catalog scope is required.")
    return cleaned[:80]


def _catalog_safe_name(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("._")
    return cleaned[:100] or "reference.jpg"


def _catalog_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _catalog_schedule(scope_id: str) -> dict[str, Any]:
    latest = _get_catalog_db().latest_run(scope_id)
    interval = _catalog_interval_hours()
    completed = _catalog_datetime(latest.get("completed_at")) if latest else None
    next_run = completed + timedelta(hours=interval) if completed else datetime.now(timezone.utc)
    return {
        "interval_hours": interval,
        "last_run_at": completed.isoformat() if completed else None,
        "next_run_at": next_run.isoformat(),
    }


def _catalog_dimensions(obj: dict[str, Any] | None) -> tuple[float, float, float] | None:
    if not obj:
        return None
    try:
        values = (float(obj["width_m"]), float(obj["height_m"]), float(obj["depth_m"]))
    except (KeyError, TypeError, ValueError):
        return None
    return values if all(value > 0 for value in values) else None


def _catalog_normalize_name(value: Any) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).split())


def _catalog_frame_embeddings(health: dict[str, Any]) -> dict[str, list[float]]:
    try:
        import cv2
        from recognition.embedding import image_embedding
    except ImportError:
        return {}

    embeddings: dict[str, list[float]] = {}
    for camera in health.get("cameras") or []:
        slot = camera.get("slot_number")
        name = str(camera.get("name") or f"slot-{slot}")
        if not slot:
            continue
        path = _live_feed_path(slot=int(slot))
        frame = cv2.imread(str(path)) if path.exists() else None
        if frame is not None:
            embeddings[name] = image_embedding(frame)
    return embeddings


def _catalog_health_snapshot() -> dict[str, Any]:
    health = _read_json(DETECTION_HEALTH_PATH) or {}
    if (
        health.get("cameras")
        or health.get("last_spatial_objects_by_camera")
        or health.get("last_spatial_objects")
    ):
        return health

    streams = (health.get("stream_manager") or {}).get("streams") or []
    if not streams:
        try:
            streams = _get_stream_manager().status().get("streams", [])
        except Exception:  # noqa: BLE001 - recognition can still return an empty run
            streams = []

    cameras = [
        {"name": str(stream.get("name") or f"slot-{stream.get('slot_number')}"), "slot_number": stream.get("slot_number")}
        for stream in streams
        if stream.get("slot_number") is not None
        and str(stream.get("status") or "").lower() not in {"offline", "stopped"}
    ]
    return {**health, "cameras": cameras}


def _catalog_crop_candidates(health: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        import cv2
        from recognition.embedding import image_embedding
    except ImportError:
        return []

    slots_by_camera = {
        str(camera.get("name") or f"slot-{camera.get('slot_number')}"): camera.get("slot_number")
        for camera in health.get("cameras") or []
    }
    candidates: list[dict[str, Any]] = []
    by_camera = health.get("last_detections_by_camera") or {}
    for camera_name, detections in by_camera.items():
        slot = slots_by_camera.get(str(camera_name))
        frame = None
        for path in _live_feed_paths(slot=int(slot) if slot else None, camera=str(camera_name)):
            frame = cv2.imread(str(path)) if path.exists() else None
            if frame is not None:
                break
        if frame is None:
            continue

        for detection in detections or []:
            crop = _catalog_detection_crop(frame, detection.get("bbox") or {})
            if crop is None:
                continue
            candidates.append(
                {
                    "camera_name": str(camera_name),
                    "detection": detection,
                    "embedding": image_embedding(crop),
                }
            )
    return candidates


def _catalog_detection_crop(frame, bbox: dict[str, Any]):
    try:
        x1 = int(float(bbox["x1"]))
        y1 = int(float(bbox["y1"]))
        x2 = int(float(bbox["x2"]))
        y2 = int(float(bbox["y2"]))
    except (KeyError, TypeError, ValueError):
        return None

    height, width = frame.shape[:2]
    box_width = max(1, x2 - x1)
    box_height = max(1, y2 - y1)
    pad_x = max(4, int(box_width * 0.08))
    pad_y = max(4, int(box_height * 0.08))
    x1 = max(0, x1 - pad_x)
    y1 = max(0, y1 - pad_y)
    x2 = min(width, x2 + pad_x)
    y2 = min(height, y2 + pad_y)
    if x2 <= x1 or y2 <= y1:
        return None
    return frame[y1:y2, x1:x2]


def _catalog_live_frames(health: dict[str, Any], max_frames: int | None = None) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    for camera in health.get("cameras") or []:
        if max_frames is not None and len(frames) >= max_frames:
            break
        slot = camera.get("slot_number")
        camera_name = str(camera.get("name") or f"slot-{slot}")
        for path in _live_feed_paths(slot=int(slot) if slot else None, camera=camera_name):
            if not path.exists():
                continue
            try:
                import cv2

                frame = cv2.imread(str(path))
            except ImportError:
                return frames
            if frame is not None:
                frames.append({"camera_name": camera_name, "slot": slot, "frame": frame})
                break
    return frames


def _catalog_detection_payload(detection) -> dict[str, Any]:
    x1, y1, x2, y2 = getattr(detection, "box", (0, 0, 0, 0))
    payload = {
        "class_name": getattr(detection, "class_name", "object"),
        "confidence": float(getattr(detection, "confidence", 0.0)),
        "quantity": max(1, int(getattr(detection, "quantity", 1))),
        "bbox": {"x1": float(x1), "y1": float(y1), "x2": float(x2), "y2": float(y2)},
    }
    for field in ("width_m", "height_m", "depth_m", "distance_m", "method", "object_type", "quantity_grid"):
        if hasattr(detection, field):
            value = getattr(detection, field)
            payload[field] = list(value) if field == "quantity_grid" else value
    return payload


def _catalog_detection_prompts(items: list[dict[str, Any]]) -> list[str]:
    prompts = [str(item["name"]) for item in items]
    prompts.extend(["cardboard box", "box", "carton box", "stack of boxes", "package"])
    seen: set[str] = set()
    unique = []
    for prompt in prompts:
        normalized = _catalog_normalize_name(prompt)
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(prompt)
    return unique


def _catalog_detection_matches_item_prompt(detection: dict[str, Any], item_name: str) -> bool:
    target = _catalog_normalize_name(item_name)
    labels = [
        _catalog_normalize_name(str(detection.get("inventory_name") or "")),
        _catalog_normalize_name(str(detection.get("class_name") or "")),
        _catalog_normalize_name(str(detection.get("object_type") or "")),
    ]
    labels = [label for label in labels if label]
    if any(label == target or label in target or target in label for label in labels):
        return True

    if "box" in target:
        return any(
            any(term in label for term in ("box", "carton", "package", "cardboard"))
            for label in labels
        )

    if any(term in target for term in ("sack", "bag")):
        return any(any(term in label for term in ("sack", "bag")) for label in labels)

    return False


def _catalog_detection_confidence(detection: dict[str, Any], fallback: float = 0.9) -> float:
    try:
        confidence = float(detection.get("confidence"))
    except (TypeError, ValueError):
        return fallback
    return confidence if confidence > 0 else fallback


def _catalog_yolo_for_prompts(prompts: list[str]) -> Detector | None:
    global _catalog_yolo_detector, _catalog_yolo_detector_key
    if not prompts:
        return None

    config = _read_yaml(CONFIG_PATH) if CONFIG_PATH.exists() else {}
    det_cfg = config.get("detection", {})
    key = (
        det_cfg.get("model_path", "yolov8s-world.pt"),
        tuple(prompts),
        float(os.getenv("CATALOG_YOLO_CONFIDENCE_THRESHOLD", "0.03")),
        det_cfg.get("device", "cpu"),
        int(os.getenv("CATALOG_YOLO_IMAGE_SIZE", "640")),
    )
    if _catalog_yolo_detector is not None and _catalog_yolo_detector_key == key:
        return _catalog_yolo_detector

    try:
        _catalog_yolo_detector = Detector(
            model_path=str(key[0]),
            confidence_threshold=float(key[2]),
            device=str(key[3]),
            class_prompts=prompts,
            image_size=int(key[4]),
            class_agnostic_nms=True,
        )
        _catalog_yolo_detector_key = key
        return _catalog_yolo_detector
    except Exception as exc:  # noqa: BLE001 - catalog recognition must degrade gracefully
        _audit("catalog_yolo_detector_failed", {"error": str(exc)})
        _catalog_yolo_detector = None
        _catalog_yolo_detector_key = None
        return None


def _catalog_fresh_yolo_crop_candidates(
    health: dict[str, Any],
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    try:
        from recognition.embedding import image_embedding
    except ImportError:
        return []

    max_frames = int(os.getenv("CATALOG_RECOGNITION_MAX_FRAMES", "8"))
    frames = _catalog_live_frames(health, max_frames=max_frames)
    if not frames:
        return []

    prompts = _catalog_detection_prompts(items)
    detector = _catalog_yolo_for_prompts(prompts)
    if detector is None:
        return []

    config = _read_yaml(CONFIG_PATH) if CONFIG_PATH.exists() else {}
    spatial_cfg = config.get("spatial_analysis", {})
    spatial_analyzer = (
        SpatialAnalyzer.from_config(spatial_cfg)
        if spatial_cfg.get("enabled", False)
        else None
    )
    candidates: list[dict[str, Any]] = []
    for entry in frames:
        frame = entry["frame"]
        detections = detector.detect(frame)
        if spatial_analyzer is not None:
            spatial_analyzer.enrich(frame, detections)
        for detection in detections:
            payload = _catalog_detection_payload(detection)
            crop = _catalog_detection_crop(frame, payload["bbox"])
            if crop is None:
                continue
            candidates.append(
                {
                    "camera_name": entry["camera_name"],
                    "detection": payload,
                    "embedding": image_embedding(crop),
                }
            )
    return candidates


def _catalog_match_current_frame(scope_id: str) -> list[dict[str, Any]]:
    """One instantaneous pass: match catalog items (only items enrolled via
    AI Check-in) against whatever the detector's current spatial-object
    snapshot shows. Pure - reads live state but writes nothing, so both a
    single scheduled run and a live-run's repeated sampling can share it."""
    from knowledge.similarity import cosine_similarity

    db = _get_catalog_db()
    items = db.list_items(scope_id, active_only=True)
    health = _catalog_health_snapshot()
    cameras = health.get("cameras") or []
    by_camera = health.get("last_spatial_objects_by_camera") or {}
    if not by_camera and health.get("last_spatial_objects"):
        fallback_name = str((cameras[-1] if cameras else {}).get("name") or "camera")
        by_camera = {fallback_name: health.get("last_spatial_objects") or []}
    crop_candidates = _catalog_crop_candidates(health)
    crop_candidates.extend(_catalog_fresh_yolo_crop_candidates(health, items))
    frame_embeddings = _catalog_frame_embeddings(health)
    visual_threshold = float(os.getenv("CATALOG_VISUAL_SIMILARITY_THRESHOLD", "0.94"))
    crop_threshold = float(os.getenv("CATALOG_CROP_SIMILARITY_THRESHOLD", "0.90"))

    matches: list[dict[str, Any]] = []
    for item in items:
        target = _catalog_normalize_name(item["name"])
        references = db.list_images(str(item["id"]), include_embeddings=True)
        matched_objects: list[dict[str, Any]] = []
        for objects in by_camera.values():
            matched_objects.extend(
                obj
                for obj in objects or []
                if _catalog_normalize_name(obj.get("inventory_name")) == target
            )

        confidence = 1.0 if matched_objects else 0.0
        quantity = sum(max(1, int(obj.get("quantity") or 1)) for obj in matched_objects)
        measurement = matched_objects[0] if matched_objects else None
        method = str(measurement.get("method") or "catalog-name-and-3d") if measurement else None

        if not matched_objects:
            if len(items) == 1:
                prompt_matches = [
                    candidate["detection"]
                    for candidate in crop_candidates
                    if _catalog_detection_matches_item_prompt(candidate["detection"], str(item["name"]))
                ]
                if prompt_matches:
                    min_confidence = float(
                        os.getenv("CATALOG_SINGLE_ITEM_ACCEPTED_CONFIDENCE", "0.75")
                    )
                    confidence = max(
                        min_confidence,
                        max(_catalog_detection_confidence(detection) for detection in prompt_matches),
                    )
                    quantity = sum(
                        max(1, int(detection.get("quantity") or 1))
                        for detection in prompt_matches
                    )
                    measurement = prompt_matches[0]
                    method = str(measurement.get("method") or "catalog-single-item-yolo-and-3d")

            if quantity > 0:
                matches.append(
                    {
                        "item_id": str(item["id"]),
                        "item_name": str(item["name"]),
                        "quantity": quantity,
                        "confidence": confidence,
                        "dimensions_m": _catalog_dimensions(measurement),
                        "measurement_method": method,
                    }
                )
                continue

            crop_matches: list[tuple[float, dict[str, Any]]] = []
            for candidate in crop_candidates:
                score = max(
                    (
                        cosine_similarity(candidate["embedding"], ref.get("embedding") or [])
                        for ref in references
                    ),
                    default=0.0,
                )
                if score >= crop_threshold:
                    crop_matches.append((score, candidate["detection"]))

            if crop_matches:
                confidence = max(score for score, _ in crop_matches)
                quantity = sum(
                    max(1, int(detection.get("quantity") or 1))
                    for _, detection in crop_matches
                )
                measurement = crop_matches[0][1]
                method = str(measurement.get("method") or "catalog-crop-reference-and-3d")

        if not matched_objects and quantity <= 0:
            best: tuple[float, str] | None = None
            for camera_name, frame_embedding in frame_embeddings.items():
                score = max(
                    (cosine_similarity(frame_embedding, ref.get("embedding") or []) for ref in references),
                    default=0.0,
                )
                if best is None or score > best[0]:
                    best = (score, camera_name)
            if best and best[0] >= visual_threshold:
                confidence = best[0]
                camera_objects = by_camera.get(best[1]) or []
                quantity = sum(max(1, int(obj.get("quantity") or 1)) for obj in camera_objects) or 1
                measurement = camera_objects[0] if camera_objects else None
                method = "catalog-reference-and-3d"

        matches.append(
            {
                "item_id": str(item["id"]),
                "item_name": str(item["name"]),
                "quantity": quantity,
                "confidence": confidence,
                "dimensions_m": _catalog_dimensions(measurement),
                "measurement_method": method,
            }
        )
    return matches


def _run_catalog_recognition(scope_id: str) -> dict[str, Any]:
    """Create one immutable catalog-only count snapshot for a scope."""
    db = _get_catalog_db()
    health = _catalog_health_snapshot()
    cameras = health.get("cameras") or []
    interval = _catalog_interval_hours()
    run_id = db.start_run(scope_id, interval, len(cameras))
    try:
        for match in _catalog_match_current_frame(scope_id):
            db.add_result(run_id=run_id, **match)
        db.complete_run(run_id)
    except Exception:
        db.complete_run(run_id, status="failed")
        raise
    return {
        "run": db.latest_run(scope_id),
        "results": db.latest_results(scope_id),
        "schedule": _catalog_schedule(scope_id),
    }


def _live_catalog_status_payload(scope_id: str) -> dict[str, Any]:
    state = _live_catalog_runs.get(scope_id)
    if not state:
        return {"running": False}
    running = state["status"] == "running"
    remaining = 0
    if running:
        ends_at = _catalog_datetime(state["ends_at"])
        if ends_at is not None:
            remaining = max(0, int((ends_at - datetime.now(timezone.utc)).total_seconds()))
    results = sorted(
        state["items"].values(), key=lambda result: (-result["quantity"], result["item_name"])
    )
    return {
        "running": running,
        "status": state["status"],
        "started_at": state["started_at"],
        "ends_at": state["ends_at"],
        "remaining_seconds": remaining,
        "results": results,
        "run_id": state.get("run_id"),
    }


async def _run_live_catalog_recognition(scope_id: str, ends_at: datetime) -> None:
    global _catalog_run_lock
    state = _live_catalog_runs[scope_id]
    try:
        while datetime.now(timezone.utc) < ends_at:
            try:
                matches = await asyncio.to_thread(_catalog_match_current_frame, scope_id)
            except Exception as exc:  # keep sampling - one bad sample shouldn't end the run
                state["error"] = str(exc)
            else:
                for match in matches:
                    if match["quantity"] <= 0:
                        continue
                    existing = state["items"].get(match["item_id"])
                    if existing is None or match["confidence"] > existing["confidence"]:
                        state["items"][match["item_id"]] = match
            remaining = (ends_at - datetime.now(timezone.utc)).total_seconds()
            if remaining <= 0:
                break
            await asyncio.sleep(min(CATALOG_LIVE_RUN_SAMPLE_INTERVAL_SECONDS, remaining))
    finally:
        if _catalog_run_lock is None:
            _catalog_run_lock = asyncio.Lock()
        async with _catalog_run_lock:
            db = _get_catalog_db()
            health = _read_json(DETECTION_HEALTH_PATH) or {}
            run_id = db.start_run(
                scope_id, _catalog_interval_hours(), len(health.get("cameras") or [])
            )
            for match in state["items"].values():
                db.add_result(run_id=run_id, **match)
            db.complete_run(run_id)
        state["status"] = "completed"
        state["run_id"] = run_id
        _audit("catalog_recognition_completed", {"scope_id": scope_id, "run_id": run_id, "mode": "live"})


def _run_due_catalog_scopes() -> None:
    now = datetime.now(timezone.utc)
    for scope_id in _get_catalog_db().list_scopes():
        schedule = _catalog_schedule(scope_id)
        next_run = _catalog_datetime(schedule["next_run_at"])
        if next_run is None or next_run <= now:
            _run_catalog_recognition(scope_id)


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
    movements = warehouse_db.recent_movements(limit)
    stock = warehouse_db.get_all_stock()
    movement_counts = warehouse_db.movement_counts()
    stock_by_name = {item["name"]: int(item.get("current_stock") or 0) for item in stock}
    all_movements = warehouse_db.recent_movements(500)
    movement_totals: dict[tuple[str, str], int] = {}
    for movement in all_movements:
        key = (movement["product_name"], movement["direction"])
        movement_totals[key] = movement_totals.get(key, 0) + int(movement.get("quantity") or 1)
    vision_items = [
        {
            "product_name": product_name,
            "state": "check-in" if direction == "IN" else "check-out",
            "quantity": stock_by_name.get(product_name, quantity) if direction == "IN" else quantity,
            "current_stock": stock_by_name.get(product_name, 0),
        }
        for (product_name, direction), quantity in sorted(
            movement_totals.items(),
            key=lambda item: (-item[1], item[0][0], item[0][1]),
        )
    ]
    status = _status()
    return {
        "running": status["running"],
        "entries": entries,
        "counts": distinct,
        "vision_items": vision_items,
        "movements": movements,
        "movement_counts": movement_counts,
        "stock": stock,
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

    for camera in active_cameras:
        db.set_status(camera["id"], "stream_managed")

    # V2: analytics never opens RTSP for validation. The Stream Manager owns
    # the upstream connection and is allowed to be starting/reconnecting while
    # YOLO comes online as a secondary frame consumer.
    _set_config_active_cameras(active_cameras)


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
        "streams": _get_stream_manager().status().get("streams", []),
        "stdout_tail": _tail_file(DETECTION_STDOUT_PATH, 40),
        "stderr_tail": _tail_file(DETECTION_STDERR_PATH, 40),
    }


def _should_autostart_detection() -> bool:
    if not _env_bool("AUTO_START_DETECTION", True):
        return False
    try:
        active = _get_camera_db().list_active_cameras(include_secret=False)
    except Exception:
        return False
    return bool(active)


def _clear_live_frames() -> None:
    if not SNAPSHOT_DIR.exists():
        return
    for pattern in ("latest.jpg", "latest_slot_*.jpg", "latest_*.jpg"):
        for path in SNAPSHOT_DIR.glob(pattern):
            try:
                path.unlink()
            except OSError:
                pass


def _ensure_detection_running(reason: str = "watchdog") -> None:
    global _watchdog_last_start_attempt
    if _manual_stop_requested or not _should_autostart_detection():
        return
    if _detector_pid() is not None:
        return

    now = time.time()
    cooldown_seconds = int(os.getenv("DETECTION_WATCHDOG_COOLDOWN_SECONDS", "45"))
    if now - _watchdog_last_start_attempt < cooldown_seconds:
        return

    _watchdog_last_start_attempt = now
    try:
        start_detection(StartRequest())
        _audit(
            "detection_autostart",
            {"reason": reason, "started": True},
            actor="watchdog",
        )
    except HTTPException as exc:
        _audit(
            "detection_autostart_failed",
            {"reason": reason, "status_code": exc.status_code, "detail": str(exc.detail)},
            actor="watchdog",
        )
    except Exception as exc:
        _audit(
            "detection_autostart_failed",
            {"reason": reason, "error": _redact_sensitive_text(str(exc))},
            actor="watchdog",
        )


async def _detection_watchdog() -> None:
    await asyncio.sleep(int(os.getenv("DETECTION_AUTOSTART_DELAY_SECONDS", "8")))
    while _env_bool("DETECTION_WATCHDOG_ENABLED", True):
        await asyncio.to_thread(_ensure_detection_running, "watchdog")
        await asyncio.sleep(int(os.getenv("DETECTION_WATCHDOG_INTERVAL_SECONDS", "30")))


async def _catalog_recognition_scheduler() -> None:
    await asyncio.sleep(int(os.getenv("CATALOG_RECOGNITION_STARTUP_DELAY_SECONDS", "60")))
    while _env_bool("CATALOG_RECOGNITION_SCHEDULER_ENABLED", True):
        try:
            await asyncio.to_thread(_run_due_catalog_scopes)
        except Exception as exc:  # noqa: BLE001
            _audit(
                "catalog_recognition_scheduler_failed",
                {"error": _redact_sensitive_text(str(exc))},
                actor="scheduler",
            )
        await asyncio.sleep(int(os.getenv("CATALOG_RECOGNITION_POLL_SECONDS", "300")))


@app.on_event("startup")
async def start_detection_watchdog() -> None:
    global _catalog_recognition_task, _watchdog_task
    if _watchdog_task is None or _watchdog_task.done():
        _watchdog_task = asyncio.create_task(_detection_watchdog())
    if _catalog_recognition_task is None or _catalog_recognition_task.done():
        _catalog_recognition_task = asyncio.create_task(_catalog_recognition_scheduler())


_HTML_NO_CACHE = {"Cache-Control": "no-cache"}


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse(DASHBOARD_V2_DIR / "index.html", headers=_HTML_NO_CACHE)


@app.get("/dashboard-v2")
def dashboard_v2() -> FileResponse:
    return FileResponse(DASHBOARD_V2_DIR / "index.html", headers=_HTML_NO_CACHE)


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    return FileResponse(DASHBOARD_V2_DIR / "favicon.svg", media_type="image/svg+xml")


@app.post("/api/v2/auth/login")
def v2_auth_login(payload: V2LoginRequest, request: Request) -> dict[str, Any]:
    ac = _get_access_control_db()
    user = ac.authenticate_user(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    passkeys = ac.list_passkeys(int(user["id"]))
    if passkeys:
        options = generate_authentication_options(
            rp_id=_v2_rp_id(request),
            allow_credentials=[
                PublicKeyCredentialDescriptor(id=base64url_to_bytes(passkey["credential_id"]))
                for passkey in passkeys
            ],
            user_verification=UserVerificationRequirement.REQUIRED,
        )
        challenge_id = ac.create_challenge(int(user["id"]), bytes_to_base64url(options.challenge), "login")
        return {
            "requires_passkey": True,
            "challenge_id": challenge_id,
            "publicKey": _v2_public_key_options(options),
            "user": {"id": user["id"], "name": user["name"], "email": user["email"]},
        }
    token = ac.create_session(int(user["id"]))
    _audit("v2.auth.login", {"user_id": user["id"], "method": "password"}, actor=user["email"])
    return _v2_auth_response(user, token)


@app.post("/api/v2/auth/setup-password")
def v2_auth_setup_password(payload: V2LoginRequest, request: Request) -> dict[str, Any]:
    ac = _get_access_control_db()
    user = ac.get_user_by_email(payload.email.strip().lower())
    if not user:
        raise HTTPException(status_code=404, detail="Account not found.")
    if user.get("has_password"):
        raise HTTPException(status_code=409, detail="Password is already set for this account.")
    if user.get("status") != "active":
        raise HTTPException(status_code=403, detail="Account is disabled.")
    try:
        user = ac.set_user_password(int(user["id"]), payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    token = ac.create_session(int(user["id"]))
    _audit("v2.auth.initial_password_set", {"user_id": user["id"]}, actor=user["email"])
    return _v2_auth_response(user, token)


@app.post("/api/v2/auth/login/passkey/options")
def v2_auth_login_passkey_options(payload: V2PasskeyLoginStart, request: Request) -> dict[str, Any]:
    ac = _get_access_control_db()
    user = ac.get_user_by_email(payload.email.strip().lower())
    if not user or user.get("status") != "active":
        raise HTTPException(status_code=401, detail="Account not found or disabled.")
    passkeys = ac.list_passkeys(int(user["id"]))
    if not passkeys:
        raise HTTPException(status_code=404, detail="No fingerprint, Face ID, or passkey is registered for this account yet.")
    options = generate_authentication_options(
        rp_id=_v2_rp_id(request),
        allow_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(passkey["credential_id"]))
            for passkey in passkeys
        ],
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    challenge_id = ac.create_challenge(int(user["id"]), bytes_to_base64url(options.challenge), "login")
    return {
        "requires_passkey": True,
        "challenge_id": challenge_id,
        "publicKey": _v2_public_key_options(options),
        "user": {"id": user["id"], "name": user["name"], "email": user["email"]},
    }


@app.post("/api/v2/auth/login/passkey")
def v2_auth_login_passkey(payload: V2PasskeyLoginFinish, request: Request) -> dict[str, Any]:
    ac = _get_access_control_db()
    user = ac.get_user_by_email(payload.email.strip().lower())
    if not user:
        raise HTTPException(status_code=401, detail="Invalid login.")
    credential_id = str(payload.credential.get("id") or payload.credential.get("rawId") or "")
    passkey = ac.get_passkey(credential_id)
    if not passkey or int(passkey["user_id"]) != int(user["id"]):
        raise HTTPException(status_code=401, detail="Unknown passkey.")
    challenge = ac.consume_challenge(int(user["id"]), payload.challenge_id, "login")
    if not challenge:
        raise HTTPException(status_code=401, detail="Passkey challenge expired.")
    try:
        verified = verify_authentication_response(
            credential=payload.credential,
            expected_challenge=base64url_to_bytes(challenge),
            expected_rp_id=_v2_rp_id(request),
            expected_origin=_v2_expected_origins(request),
            credential_public_key=base64url_to_bytes(passkey["public_key"]),
            credential_current_sign_count=int(passkey["sign_count"] or 0),
            require_user_verification=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Passkey verification failed: {exc}") from exc
    ac.update_passkey_sign_count(credential_id, int(verified.new_sign_count))
    token = ac.create_session(int(user["id"]))
    _audit("v2.auth.login", {"user_id": user["id"], "method": "password+passkey"}, actor=user["email"])
    return _v2_auth_response(user, token)


@app.get("/api/v2/auth/me")
def v2_auth_me(request: Request) -> dict[str, Any]:
    user = _v2_session_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Login required.")
    dashboard = _get_access_control_db().resolve_dashboard(user_id=int(user["id"]))
    return {"user": dashboard["user"], "modules": dashboard["modules"]}


@app.post("/api/v2/auth/passkeys/register/options")
def v2_passkey_register_options(payload: V2PasskeyRegisterStart, request: Request) -> dict[str, Any]:
    user = _v2_session_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Login required.")
    ac = _get_access_control_db()
    existing = ac.list_passkeys(int(user["id"]))
    options = generate_registration_options(
        rp_id=_v2_rp_id(request),
        rp_name=os.getenv("WEBAUTHN_RP_NAME", "AI Vision"),
        user_id=str(user["id"]).encode("utf-8"),
        user_name=user["email"],
        user_display_name=user["name"],
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(passkey["credential_id"]))
            for passkey in existing
        ],
    )
    challenge_id = ac.create_challenge(int(user["id"]), bytes_to_base64url(options.challenge), "register")
    return {"challenge_id": challenge_id, "publicKey": _v2_public_key_options(options)}


@app.post("/api/v2/auth/passkeys/register/verify")
def v2_passkey_register_verify(payload: V2PasskeyRegisterFinish, request: Request) -> dict[str, Any]:
    user = _v2_session_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Login required.")
    ac = _get_access_control_db()
    challenge = ac.consume_challenge(int(user["id"]), payload.challenge_id, "register")
    if not challenge:
        raise HTTPException(status_code=401, detail="Passkey challenge expired.")
    try:
        verified = verify_registration_response(
            credential=payload.credential,
            expected_challenge=base64url_to_bytes(challenge),
            expected_rp_id=_v2_rp_id(request),
            expected_origin=_v2_expected_origins(request),
            require_user_verification=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Passkey registration failed: {exc}") from exc
    passkey = ac.add_passkey(
        int(user["id"]),
        bytes_to_base64url(verified.credential_id),
        bytes_to_base64url(verified.credential_public_key),
        int(verified.sign_count),
        payload.name or "Fingerprint / passkey",
    )
    _audit("v2.auth.passkey_registered", {"user_id": user["id"], "credential_id": passkey["credential_id"]}, actor=user["email"])
    return {"ok": True, "passkey": {"name": passkey["name"]}}


@app.get("/api/v2/me/dashboard")
def v2_me_dashboard(request: Request) -> dict[str, Any]:
    return _v2_dashboard(request)


@app.get("/api/v2/me/module/{module_code}")
def v2_module_data(module_code: str, request: Request) -> dict[str, Any]:
    dashboard = _v2_require_module(request, module_code)
    if module_code == "live_monitoring":
        cameras = _get_camera_db().list_active_cameras(include_secret=False)
        allowed_ids = set(dashboard.get("scope", {}).get("camera_ids") or [])
        if allowed_ids:
            cameras = [camera for camera in cameras if str(camera.get("id")) in allowed_ids]
        return {"module": module_code, "cameras": cameras, "status": _status()}
    if module_code == "counting":
        return {
            "module": module_code,
            "stock": _get_warehouse_db().get_all_stock(),
            "movement_counts": _get_warehouse_db().movement_counts(),
        }
    if module_code in {"reports", "activity_history"}:
        return {"module": module_code, "movements": _get_warehouse_db().recent_movements(limit=50)}
    if module_code == "products":
        return {"module": module_code, "stock": _get_warehouse_db().get_all_stock()}
    if module_code == "system_health":
        return {"module": module_code, "status": _status(), "opencv": opencv_diagnostics()}
    if module_code == "audit_logs":
        _v2_require_module(request, module_code, permission="audit.view")
        return security_audit(limit=100)
    return {"module": module_code, "message": "Module shell is assigned and ready for implementation."}


@app.get("/api/v2/admin/overview")
def v2_admin_overview(request: Request) -> dict[str, Any]:
    _v2_require_permission(request, "dashboard.view")
    ac = _get_access_control_db()
    cameras = _get_camera_db().list_cameras(include_secret=False)
    active_cameras = [camera for camera in cameras if camera["is_active"]]
    health = (_status().get("health") or {})
    return {
        "totals": {
            "companies": len([org for org in ac.list_organizations() if org["type"] == "company"]),
            "factories": len([org for org in ac.list_organizations() if org["type"] == "factory"]),
            "warehouses": len([org for org in ac.list_organizations() if org["type"] == "warehouse"]),
            "users": len(ac.list_users()),
            "online_cameras": len(active_cameras),
            "offline_cameras": max(0, len(cameras) - len(active_cameras)),
            "active_ai_processes": 1 if _status()["running"] else 0,
            "products_counted_today": health.get("last_detection_count", 0),
            "active_alerts": 0,
        },
        "server_status": _status(),
        "recent_activity": _get_security_audit_db().recent(limit=12),
    }


@app.get("/api/v2/admin/bootstrap")
def v2_admin_bootstrap(request: Request) -> dict[str, Any]:
    _v2_require_permission(request, "user.view")
    ac = _get_access_control_db()
    return {
        "users": ac.list_users(),
        "roles": ac.list_roles(),
        "permissions": ac.list_permissions(),
        "modules": ac.list_modules(),
        "organizations": ac.list_organizations(),
    }


@app.post("/api/v2/admin/users")
def v2_admin_create_user(payload: V2UserCreate, request: Request) -> dict[str, Any]:
    _v2_require_permission(request, "user.create")
    user = _get_access_control_db().create_user(payload.name, payload.email.strip().lower())
    _audit("v2.user.created", {"user": user}, actor=_v2_user_email(request))
    return user


@app.post("/api/v2/admin/users/{user_id}/password")
def v2_admin_set_user_password(user_id: int, payload: V2PasswordSet, request: Request) -> dict[str, Any]:
    _v2_require_permission(request, "user.edit")
    try:
        user = _get_access_control_db().set_user_password(user_id, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    _audit("v2.user.password_set", {"user_id": user_id}, actor=_v2_user_email(request))
    return user


@app.post("/api/v2/admin/users/{user_id}/auth-preference")
def v2_admin_set_user_auth_preference(user_id: int, payload: V2AuthPreferenceSet, request: Request) -> dict[str, Any]:
    _v2_require_permission(request, "user.edit")
    try:
        user = _get_access_control_db().set_user_auth_preference(user_id, payload.preferred_auth_method)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    _audit("v2.user.auth_preference_set", {"user_id": user_id, "preferred_auth_method": payload.preferred_auth_method}, actor=_v2_user_email(request))
    return user


@app.post("/api/v2/admin/roles")
def v2_admin_create_role(payload: V2RoleCreate, request: Request) -> dict[str, Any]:
    _v2_require_permission(request, "role.create")
    role = _get_access_control_db().create_role(payload.name, payload.code)
    _audit("v2.role.created", {"role": role}, actor=_v2_user_email(request))
    return role


@app.post("/api/v2/admin/users/{user_id}/roles")
def v2_admin_assign_role(user_id: int, payload: V2RoleAssignment, request: Request) -> dict[str, Any]:
    _v2_require_permission(request, "user.edit")
    _get_access_control_db().assign_role(user_id, payload.role_code)
    _audit("v2.user.role_assigned", {"user_id": user_id, "role_code": payload.role_code}, actor=_v2_user_email(request))
    return _get_access_control_db().resolve_dashboard(user_id=user_id)


@app.delete("/api/v2/admin/users/{user_id}/roles/{role_code}")
def v2_admin_remove_role(user_id: int, role_code: str, request: Request) -> dict[str, Any]:
    _v2_require_permission(request, "user.edit")
    _get_access_control_db().remove_role(user_id, role_code)
    _audit("v2.user.role_removed", {"user_id": user_id, "role_code": role_code}, actor=_v2_user_email(request))
    return _get_access_control_db().resolve_dashboard(user_id=user_id)


@app.post("/api/v2/admin/users/{user_id}/modules")
def v2_admin_assign_module(user_id: int, payload: V2ModuleAssignment, request: Request) -> dict[str, Any]:
    _v2_require_permission(request, "module.assign")
    _get_access_control_db().set_user_module(user_id, payload.module_code, payload.effect, payload.display_order)
    _audit("v2.user.module_changed", {"user_id": user_id, **payload.model_dump()}, actor=_v2_user_email(request))
    return _get_access_control_db().resolve_dashboard(user_id=user_id)


@app.post("/api/v2/admin/users/{user_id}/permissions")
def v2_admin_assign_permission(user_id: int, payload: V2PermissionAssignment, request: Request) -> dict[str, Any]:
    _v2_require_permission(request, "user.edit")
    _get_access_control_db().set_user_permission(user_id, payload.permission_code, payload.effect)
    _audit("v2.user.permission_changed", {"user_id": user_id, **payload.model_dump()}, actor=_v2_user_email(request))
    return _get_access_control_db().resolve_dashboard(user_id=user_id)


@app.post("/api/v2/admin/users/{user_id}/scopes")
def v2_admin_assign_scope(user_id: int, payload: V2ScopeAssignment, request: Request) -> dict[str, Any]:
    _v2_require_permission(request, "scope.assign")
    _get_access_control_db().set_user_scope(user_id, payload.scope_type, payload.scope_ids, payload.effect)
    _audit("v2.user.scope_changed", {"user_id": user_id, **payload.model_dump()}, actor=_v2_user_email(request))
    return _get_access_control_db().resolve_dashboard(user_id=user_id)


@app.post("/api/v2/admin/users/{user_id}/disable")
def v2_admin_disable_user(user_id: int, request: Request) -> dict[str, Any]:
    _v2_require_permission(request, "user.disable")
    user = _get_access_control_db().set_user_status(user_id, "disabled")
    _audit("v2.user.disabled", {"user_id": user_id}, actor=_v2_user_email(request))
    return user or {}


@app.post("/api/v2/admin/users/{user_id}/reactivate")
def v2_admin_reactivate_user(user_id: int, request: Request) -> dict[str, Any]:
    _v2_require_permission(request, "user.edit")
    user = _get_access_control_db().set_user_status(user_id, "active")
    _audit("v2.user.reactivated", {"user_id": user_id}, actor=_v2_user_email(request))
    return user or {}


@app.get("/api/v2/rbac/me")
def dashboard_v2_rbac_me(request: Request) -> dict[str, Any]:
    context = _rbac_context(request)
    permissions = set(context["permissions"])
    return {
        **context,
        "surfaces": {
            "head": _authorized_modules("head", permissions),
            "user": _authorized_modules("user", permissions),
        },
        "available_roles": [
            {"id": role, "label": role.replace("_", " ").title()}
            for role in ROLE_PERMISSIONS
        ],
    }


@app.get("/api/v2/navigation")
def dashboard_v2_navigation(request: Request, surface: str = "head") -> dict[str, Any]:
    surface = surface.strip().lower()
    if surface not in DASHBOARD_V2_MODULES:
        raise HTTPException(status_code=400, detail="Unknown dashboard surface.")
    context = _require_permission(request, "view_dashboard")
    return {
        "surface": surface,
        "modules": _authorized_modules(surface, set(context["permissions"])),
        "role": context["role"],
        "scope": context["scope"],
    }


@app.get("/api/v2/head/overview")
def dashboard_v2_head_overview(request: Request) -> dict[str, Any]:
    context = _require_permission(request, "view_dashboard")
    status_data = _status()
    health = status_data.get("health") or {}
    cameras = _get_camera_db().list_cameras(include_secret=False)
    active_cameras = [camera for camera in cameras if camera["is_active"]]
    stock = _get_warehouse_db().get_all_stock()
    movement_counts = _get_warehouse_db().movement_counts()
    audit = _get_security_audit_db().verify()
    return {
        "context": context,
        "summary": {
            "organizations": 1,
            "active_cameras": len(active_cameras),
            "saved_cameras": len(cameras),
            "detector_running": status_data["running"],
            "frames_read": health.get("frames_read", 0),
            "last_frame_at": health.get("last_frame_at"),
            "last_detection_count": health.get("last_detection_count", 0),
            "stock_items": len(stock),
            "audit_verified": audit.get("verified", False),
        },
        "health": health,
        "movement_counts": movement_counts,
        "future_integrations": [
            "ERP",
            "HRM",
            "CRM",
            "Inventory Management",
            "Quality Control",
            "Predictive Analytics",
            "Multi-site Management",
            "API Integrations",
        ],
    }


@app.get("/api/v2/user/overview")
def dashboard_v2_user_overview(request: Request) -> dict[str, Any]:
    context = _require_permission(request, "view_dashboard")
    status_data = _status()
    health = status_data.get("health") or {}
    stock = _get_warehouse_db().get_all_stock()
    movements = _get_warehouse_db().recent_movements(limit=12)
    return {
        "context": context,
        "summary": {
            "detector_running": status_data["running"],
            "active_cameras": health.get("camera_count", 0),
            "frames_read": health.get("frames_read", 0),
            "last_detection_count": health.get("last_detection_count", 0),
            "last_tracked_count": health.get("last_tracked_count", 0),
            "stock_items": len(stock),
            "open_verification_tasks": 0,
            "active_alerts": 0,
        },
        "stock": stock[:12],
        "recent_movements": movements,
    }


@app.get("/api/status")
def status() -> dict[str, Any]:
    data = _status()
    data["security"] = {
        "api_key_required": _security_enabled(),
        "allowed_origins": _env_list("ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS),
    }
    return data


@app.get("/api/security/audit")
def security_audit(limit: int = 100) -> dict[str, Any]:
    db = _get_security_audit_db()
    return {
        "chain": db.verify(),
        "events": db.recent(limit=limit),
    }


@app.get("/api/diagnostics/opencv")
def opencv_diagnostics() -> dict[str, Any]:
    try:
        import cv2

        return {
            "ok": True,
            "version": getattr(cv2, "__version__", "unknown"),
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": _redact_sensitive_text(str(exc)),
            "error_type": type(exc).__name__,
        }


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return _redact_config(_read_yaml(CONFIG_PATH))


@app.patch("/api/config")
def update_config(patch: ConfigPatch) -> dict[str, Any]:
    data = _read_yaml(CONFIG_PATH)
    detection = data.setdefault("detection", {})
    snapshots = data.setdefault("snapshots", {})
    logging_cfg = data.setdefault("logging", {})
    tracking = data.setdefault("tracking", {})
    warehouse_counting = data.setdefault("warehouse_counting", {})
    recognition = data.setdefault("recognition", {})

    values = patch.model_dump(exclude_unset=True)
    if "model_path" in values:
        detection["model_path"] = values["model_path"]
    if "confidence_threshold" in values:
        detection["confidence_threshold"] = values["confidence_threshold"]
    if "image_size" in values:
        detection["image_size"] = values["image_size"]
    if "device" in values:
        detection["device"] = values["device"]
    if "classes" in values:
        detection["classes"] = values["classes"] or None
    if "class_prompts" in values:
        detection["class_prompts"] = values["class_prompts"] or None
    if "class_agnostic_nms" in values:
        detection["class_agnostic_nms"] = values["class_agnostic_nms"]
    if "tracking_enabled" in values:
        tracking["enabled"] = values["tracking_enabled"]
    if "warehouse_counting_enabled" in values:
        warehouse_counting["enabled"] = values["warehouse_counting_enabled"]
    if "snapshots_enabled" in values:
        snapshots["enabled"] = values["snapshots_enabled"]
    if "snapshot_trigger_classes" in values:
        snapshots["trigger_classes"] = values["snapshot_trigger_classes"] or []
    if "snapshot_cooldown_seconds" in values:
        snapshots["cooldown_seconds"] = values["snapshot_cooldown_seconds"]
    if "logging_enabled" in values:
        logging_cfg["enabled"] = values["logging_enabled"]
    if "recognition_model" in values:
        recognition["model"] = values["recognition_model"]

    _write_yaml(CONFIG_PATH, data)
    return _redact_config(data)


def _redact_config(data: dict[str, Any]) -> dict[str, Any]:
    redacted = json.loads(json.dumps(data))
    for camera in redacted.get("cameras", []) or []:
        source = camera.get("source")
        if source is not None:
            camera["source"] = _redact_sensitive_text(str(source))
    return redacted


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
    stream = None
    if camera.make_active and test_result["status"] == "connected":
        slot_number = camera.slot_number or _next_available_slot(db.list_cameras(include_secret=False))
        active = db.assign_slot(saved["id"], slot_number)
        _sync_config_active_cameras(db)
        stream = _start_stream_for_camera(active)
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
        "stream": stream,
        "cameras": cameras,
    }


def _register_controller_channels(
    controller: CameraControllerCreate, db: CameraDB
) -> dict[str, Any]:
    """Test and save/activate every channel on a controller.

    Shared by the Add NVR endpoint and the environment-based boot-time seed
    so both paths apply the exact same validation instead of drifting apart
    - the seed path used to have its own separate, untested activation loop
    that could silently occupy real slots with channels that had never
    actually been checked.
    """
    endpoint = _controller_endpoint(controller)
    if not endpoint["host"]:
        raise HTTPException(status_code=400, detail="Controller IP/host is required.")

    private_host_message = _private_controller_host_message(endpoint["host"])
    if controller.require_public and private_host_message:
        raise HTTPException(status_code=400, detail=private_host_message)

    controller_error = None
    if controller.test_controller:
        controller_error = _check_camera_endpoint(endpoint)
        if controller_error:
            controller_error = _redact_sensitive_text(controller_error)

    saved_cameras = []
    test_results = []
    controller_reachable = controller_error is None

    # A camera can be registered (saved, tested, shown on the dashboard)
    # without being active (occupying a real slot the detector actually
    # opens a connection to). MAX_CAMERA_SLOTS bounds how many cameras can
    # be active - i.e. actually connected - at once, to protect the
    # droplet's CPU/memory/bandwidth; it does not bound how many cameras
    # can be registered. A controller with more channels than there are
    # free slots right now still saves and tests every channel - it just
    # leaves the channels beyond the free-slot budget registered but
    # inactive instead of rejecting the whole request.
    used_slots = {
        int(camera["slot_number"])
        for camera in db.list_active_cameras(include_secret=False)
        if camera.get("slot_number") is not None
    }
    next_slot = max(controller.start_slot, 1)

    for index in range(controller.channel_count):
        channel = controller.channel_start + index
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
            name=_controller_camera_name(controller, channel, next_slot),
            stream_url=stream_url,
            status=test_result["status"],
        )

        active = None
        assigned_slot = None
        stream_status = None
        message = test_result["message"]
        if controller.make_active and test_result["status"] == "connected":
            while next_slot in used_slots and next_slot <= MAX_CAMERA_SLOTS:
                next_slot += 1
            if next_slot <= MAX_CAMERA_SLOTS:
                active = db.assign_slot(saved["id"], next_slot)
                used_slots.add(next_slot)
                assigned_slot = next_slot
                next_slot += 1
                stream_status = _start_stream_for_camera(active)
            else:
                message = (
                    f"Reachable, but no free camera slot is available right now "
                    f"({MAX_CAMERA_SLOTS} active slot limit reached). Deactivate "
                    "another camera to free one up for this one."
                )

        saved_cameras.append(db.get_camera(saved["id"], include_secret=False))
        test_results.append(
            {
                "camera_id": saved["id"],
                "slot_number": assigned_slot,
                "channel": channel,
                "status": test_result["status"],
                "message": message,
                "active": active is not None,
                "stream": stream_status,
            }
        )

    return {
        "endpoint": endpoint,
        "private_host_message": private_host_message,
        "controller_error": controller_error,
        "controller_reachable": controller_reachable,
        "saved_cameras": saved_cameras,
        "test_results": test_results,
    }


@app.post("/api/discovery/scan")
async def discovery_scan(request: DiscoveryScanRequest) -> dict[str, Any]:
    """Device-first discovery: given only an IP/hostname, report what the
    device is and which streaming services it exposes, with no RTSP URL,
    stream path, or vendor supplied by the operator.

    The scan is CPU-light but network-bound (several socket probes), so it runs
    off the event loop. The Discovery Engine itself enforces the target-host
    safety policy (see discovery.portscan.resolve_and_guard)."""
    result = await asyncio.to_thread(discover_device, request.host.strip())
    _audit(
        "discovery_scan",
        {
            "host": request.host.strip(),
            "reachable": result.reachable,
            "vendor": result.fingerprint.vendor,
            "service_count": len(result.services),
        },
    )
    return result.to_dict()


@app.post("/api/v2/devices/discover")
async def v2_discover_device(request: V2DeviceDiscoverRequest) -> dict[str, Any]:
    """V2 entry point: discovery starts from only an IP address or hostname."""
    result = await asyncio.to_thread(discover_device, request.host.strip())
    payload = result.to_dict()
    device = _get_device_db().upsert_device_from_discovery(
        name=(request.name or request.host).strip(),
        host=request.host.strip(),
        result=payload,
    )
    _audit(
        "v2_device_discover",
        {
            "device_id": device.get("id"),
            "host": request.host.strip(),
            "reachable": payload.get("reachable"),
            "service_count": len(payload.get("services") or []),
        },
    )
    return {"device": device, "discovery": payload}


@app.get("/api/v2/devices")
def v2_list_devices() -> dict[str, Any]:
    return {"devices": _get_device_db().list_devices()}


@app.post("/api/v2/devices/{device_id}/authenticate")
def v2_authenticate_device(device_id: int, request: V2DeviceAuthenticateRequest) -> dict[str, Any]:
    """Authenticate only after service selection, then enumerate channels."""
    db = _get_device_db()
    device = db.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found.")

    port = request.port or STREAM_DEFAULT_PORTS.get(request.protocol.lower(), 554)
    credentials = StreamCredentials(request.username or "", request.password or "")
    enumeration = enumerate_streams(
        host=str(device["host"]),
        port=port,
        protocol=request.protocol,
        credentials=credentials,
        vendor=_v2_stream_vendor_hint(device, request),
        channel_count=request.channel_count,
    )
    if enumeration.requires_auth and not request.username:
        raise HTTPException(
            status_code=401,
            detail="This service requires authentication. Provide credentials after selecting the service.",
        )
    if not enumeration.channels:
        raise HTTPException(
            status_code=502,
            detail=_redact_sensitive_text(enumeration.error or "No channels were discovered."),
        )

    camera_db = _get_camera_db()
    used_slots = {
        int(camera["slot_number"])
        for camera in camera_db.list_active_cameras(include_secret=False)
        if camera.get("slot_number") is not None
    }
    next_slot = 1
    channels = []
    stream_statuses = []
    for stream in enumeration.channels:
        camera = camera_db.add_camera(
            name=f"{device['name']} {stream.name}",
            stream_url=stream.stream_url,
            status="connected" if not request.test_streams else _test_camera_stream(stream.stream_url)["status"],
        )
        assigned_slot = None
        active = None
        if request.make_active:
            while next_slot in used_slots and next_slot <= MAX_CAMERA_SLOTS:
                next_slot += 1
            if next_slot <= MAX_CAMERA_SLOTS:
                active = camera_db.assign_slot(camera["id"], next_slot)
                assigned_slot = next_slot
                used_slots.add(next_slot)
                next_slot += 1

        channel = db.add_channel(
            device_id=device_id,
            external_channel_id=str(stream.channel),
            name=f"{device['name']} {stream.name}",
            profile=stream.description,
            stream_reference=stream.stream_url,
            camera_id=camera["id"],
            slot_number=assigned_slot,
        )
        if active is not None:
            status = _start_stream_for_camera(active)
            db.update_stream_session(channel["id"], status)
            stream_statuses.append(status)
        channels.append(channel)

    _sync_config_active_cameras(camera_db)
    _audit("v2_device_authenticate", {"device_id": device_id, "channels": len(channels)})
    return {
        "provider": enumeration.provider,
        "device": db.get_device(device_id),
        "channels": channels,
        "streams": stream_statuses,
    }


@app.get("/api/v2/devices/{device_id}/channels")
def v2_device_channels(device_id: int) -> dict[str, Any]:
    device = _get_device_db().get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found.")
    return {"device": device, "channels": device.get("channels", [])}


def _register_discovered_channels(
    name_prefix: str,
    channels: list[Any],
    make_active: bool,
    test_streams: bool,
    db: CameraDB,
) -> list[dict[str, Any]]:
    """Save/activate a provider's enumerated channels, reusing the same
    register-without-activate + slot-budget behaviour as the controller path:
    every channel is saved, and channels beyond the free active-slot budget
    are left registered-but-inactive rather than rejecting the whole request.
    """
    used_slots = {
        int(camera["slot_number"])
        for camera in db.list_active_cameras(include_secret=False)
        if camera.get("slot_number") is not None
    }
    next_slot = 1
    results: list[dict[str, Any]] = []

    for stream in channels:
        if test_streams:
            test_result = _test_camera_stream(stream.stream_url)
        else:
            test_result = {"status": "connected", "message": "Stream registered without a pre-flight test."}

        saved = db.add_camera(
            name=f"{name_prefix} {stream.name}",
            stream_url=stream.stream_url,
            status=test_result["status"],
        )

        active = None
        assigned_slot = None
        stream_status = None
        message = test_result["message"]
        if make_active and test_result["status"] == "connected":
            while next_slot in used_slots and next_slot <= MAX_CAMERA_SLOTS:
                next_slot += 1
            if next_slot <= MAX_CAMERA_SLOTS:
                active = db.assign_slot(saved["id"], next_slot)
                used_slots.add(next_slot)
                assigned_slot = next_slot
                next_slot += 1
                stream_status = _start_stream_for_camera(active)
            else:
                message = (
                    f"Reachable, but no free camera slot is available right now "
                    f"({MAX_CAMERA_SLOTS} active slot limit reached). Deactivate "
                    "another camera to free one up for this one."
                )

        results.append(
            {
                "camera_id": saved["id"],
                "channel": stream.channel,
                "slot_number": assigned_slot,
                "status": test_result["status"],
                "message": message,
                "active": active is not None,
                "stream": stream_status,
            }
        )
    return results


@app.post("/api/discovery/connect")
def discovery_connect(request: DiscoveryConnectRequest) -> dict[str, Any]:
    """Complete the device-first flow: enumerate the chosen service's streams
    via the provider stack (ONVIF-first, vendor/generic fallback) and register
    them through the existing camera store + slot allocator + ffmpeg stream
    layer. The operator supplies only the device, the selected service, and -
    when required - credentials; never a stream path."""
    host = request.host.strip()
    try:
        resolve_and_guard(host)
    except DiscoveryHostError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    port = request.port or STREAM_DEFAULT_PORTS.get(request.protocol.lower(), 554)
    credentials = StreamCredentials(request.username or "", request.password or "")
    enumeration = enumerate_streams(
        host=host,
        port=port,
        protocol=request.protocol,
        credentials=credentials,
        vendor=request.vendor,
        channel_count=request.channel_count,
    )

    if enumeration.requires_auth and not request.username:
        raise HTTPException(
            status_code=401,
            detail="This service requires authentication. Provide a username and password.",
        )
    if not enumeration.channels:
        raise HTTPException(
            status_code=502,
            detail=_redact_sensitive_text(
                enumeration.error or "No connectable streams were found on this device."
            ),
        )

    db = _get_camera_db()
    results = _register_discovered_channels(
        name_prefix=request.name.strip(),
        channels=enumeration.channels,
        make_active=request.make_active,
        test_streams=request.test_streams,
        db=db,
    )

    if request.make_active and any(result["active"] for result in results):
        _sync_config_active_cameras(db)
        if _status()["running"]:
            stop_detection()
        try:
            start_detection(StartRequest())
        except HTTPException:
            pass

    cameras = db.list_cameras(include_secret=False)
    active_cameras = [row for row in cameras if row["is_active"]]
    _audit(
        "discovery_connect",
        {"host": host, "provider": enumeration.provider, "channels": len(results)},
    )
    return {
        "provider": enumeration.provider,
        "results": results,
        "cameras": cameras,
        "active_cameras": active_cameras,
    }


@app.post("/api/camera-controller")
def save_camera_controller(controller: CameraControllerCreate) -> dict[str, Any]:
    db = _get_camera_db()
    registration = _register_controller_channels(controller, db)
    endpoint = registration["endpoint"]
    private_host_message = registration["private_host_message"]
    controller_error = registration["controller_error"]
    controller_reachable = registration["controller_reachable"]
    saved_cameras = registration["saved_cameras"]
    test_results = registration["test_results"]

    if controller.make_active and any(result["active"] for result in test_results):
        _sync_config_active_cameras(db)
        if _status()["running"]:
            stop_detection()
        # Always attempt a (re)start so newly added channels start
        # transmitting immediately instead of waiting on the next NVR
        # change to happen to restart detection. A freshly reconnected RTSP
        # stream can fail the stricter start-time stream check (e.g. no
        # keyframe yet) even though the endpoint itself is reachable; that
        # shouldn't fail this request since the cameras were already saved
        # and activated above — the watchdog retries shortly after.
        try:
            start_detection(StartRequest())
        except HTTPException:
            pass

    cameras = db.list_cameras(include_secret=False)
    active_cameras = [row for row in cameras if row["is_active"]]
    return {
        "controller": {
            "name": controller.name.strip(),
            "host": endpoint["host"],
            "port": endpoint["port"],
            "protocol": endpoint["scheme"],
            "reachable": controller_reachable,
            "public_reachable_required": controller.require_public,
            "public_reachability_warning": private_host_message,
            "message": controller_error
            or f"Controller endpoint {endpoint['host']}:{endpoint['port']} is reachable.",
        },
        "created": saved_cameras,
        "results": test_results,
        "cameras": cameras,
        "active_cameras": active_cameras,
        "active_camera": active_cameras[0] if active_cameras else None,
    }


@app.post("/api/v2/channels/{channel_id}/stream/start")
def v2_start_stream(channel_id: int, request: V2StreamStartRequest | None = None) -> dict[str, Any]:
    request = request or V2StreamStartRequest()
    device_db = _get_device_db()
    channel = device_db.get_channel(channel_id, include_secret=True)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found.")

    slot_number = request.slot_number or channel.get("slot_number")
    if slot_number is None and channel.get("camera_id"):
        camera = _get_camera_db().assign_slot(
            int(channel["camera_id"]),
            _next_available_slot(_get_camera_db().list_cameras(include_secret=False)),
        )
        slot_number = camera.get("slot_number") if camera else None
        _sync_config_active_cameras(_get_camera_db())

    status = _get_stream_manager().start(
        StreamSessionConfig(
            channel_id=str(channel_id),
            name=str(channel["name"]),
            source=str(channel["stream_reference"]),
            slot_number=slot_number,
            snapshot_dir=SNAPSHOT_DIR,
        )
    )
    device_db.update_stream_session(channel_id, status)
    return {"channel": device_db.get_channel(channel_id, include_secret=False), "stream": status}


@app.post("/api/v2/channels/{channel_id}/stream/stop")
def v2_stop_stream(channel_id: int) -> dict[str, Any]:
    stopped = _get_stream_manager().stop(str(channel_id))
    status = {"channel_id": str(channel_id), "status": "offline"}
    _get_device_db().update_stream_session(channel_id, status)
    return {"stopped": stopped, "stream": status}


@app.get("/api/v2/streams/health")
def v2_stream_health() -> dict[str, Any]:
    return _get_stream_manager().status()


@app.get("/api/v2/channels/{channel_id}/stream/health")
def v2_channel_stream_health(channel_id: int) -> dict[str, Any]:
    return _get_stream_manager().status(str(channel_id))


@app.get("/api/v2/channels/{channel_id}/live")
async def v2_channel_live_frame(channel_id: int):
    channel = _get_device_db().get_channel(channel_id, include_secret=False)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found.")
    return await live_frame(slot=channel.get("slot_number"))


@app.post("/api/v2/channels/{channel_id}/analytics/start")
def v2_start_analytics(channel_id: int) -> dict[str, Any]:
    channel = _get_device_db().set_analytics_enabled(channel_id, True)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found.")
    if _detector_pid() is None:
        try:
            start_detection(StartRequest())
        except HTTPException as exc:
            if exc.status_code != 409:
                raise
    return {"channel": channel, "analytics": _status()}


@app.post("/api/v2/channels/{channel_id}/analytics/stop")
def v2_stop_analytics(channel_id: int) -> dict[str, Any]:
    channel = _get_device_db().set_analytics_enabled(channel_id, False)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found.")
    return {"channel": channel, "analytics": _status()}


@app.get("/api/v2/analytics/health")
def v2_analytics_health() -> dict[str, Any]:
    status = _status()
    return {
        "status": "online" if status.get("running") else "offline",
        "pid": status.get("pid"),
        "health": status.get("health"),
    }


@app.get("/api/v2/detections/latest")
def v2_latest_detections() -> dict[str, Any]:
    health = _read_json(DETECTION_HEALTH_PATH) or {}
    return {
        "state": health.get("state", "offline"),
        "updated_at": health.get("updated_at"),
        "detections": health.get("last_detections_by_camera") or {},
        "spatial": health.get("last_spatial_objects_by_camera")
        or health.get("last_spatial_objects")
        or {},
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


@app.delete("/api/cameras/{camera_id}")
def delete_saved_camera(camera_id: int) -> dict[str, Any]:
    db = _get_camera_db()
    deleted = db.delete_camera(camera_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Camera not found.")

    _sync_config_active_cameras(db)
    if _status()["running"]:
        stop_detection()
        start_detection(StartRequest())

    cameras = db.list_cameras(include_secret=False)
    active_cameras = [row for row in cameras if row["is_active"]]
    return {
        "deleted": True,
        "cameras": cameras,
        "active_cameras": active_cameras,
        "active_camera": active_cameras[0] if active_cameras else None,
    }


@app.post("/api/cameras/cleanup")
def cleanup_cameras_by_name(request: CameraCleanupRequest) -> dict[str, Any]:
    """Bulk-delete every camera whose name starts with the given prefix.

    For clearing out stale rows left behind by the environment-based boot
    seed (see _seed_cameras_from_environment) - those get created once with
    whatever stream URL was correct/available at the time, stored as a
    literal string, and never retroactively updated by a later code or env
    var change. A camera named e.g. "Warehouse NVR Camera 7" with a wrong
    URL baked in from months ago has to be deleted and re-added, not
    patched.
    """
    prefix = request.name_prefix.strip()
    if not prefix:
        raise HTTPException(status_code=400, detail="name_prefix is required.")

    db = _get_camera_db()
    matches = [
        camera
        for camera in db.list_cameras(include_secret=False)
        if str(camera.get("name", "")).startswith(prefix)
    ]

    deleted = []
    any_active = False
    for camera in matches:
        if camera.get("is_active"):
            any_active = True
        if db.delete_camera(camera["id"]):
            deleted.append({"id": camera["id"], "name": camera["name"]})

    if any_active:
        _sync_config_active_cameras(db)
        if _status()["running"]:
            stop_detection()
        try:
            start_detection(StartRequest())
        except HTTPException:
            pass

    cameras = db.list_cameras(include_secret=False)
    active_cameras = [row for row in cameras if row["is_active"]]
    return {
        "deleted": deleted,
        "deleted_count": len(deleted),
        "cameras": cameras,
        "active_cameras": active_cameras,
    }


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
    stream = _start_stream_for_camera(active)
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
        "stream": stream,
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
    active_before = [
        camera for camera in db.list_active_cameras(include_secret=False)
        if camera.get("slot_number") == slot_number
    ]
    db.clear_slot(slot_number)
    for camera in active_before:
        _get_stream_manager().stop(str(camera["id"]))
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
    global _process, _started_at, _last_exit_code, _stdout_handle, _stderr_handle, _manual_stop_requested
    request = request or StartRequest()
    if _detector_pid() is not None:
        raise HTTPException(status_code=409, detail="Detection is already running.")
    # Clear the manual-stop latch as soon as a start is attempted, not after
    # validation succeeds. Otherwise a start that's triggered right after a
    # stop (e.g. restarting to pick up a newly added camera) and then fails
    # validation (a stream that hasn't sent its first keyframe yet, briefly
    # unreachable, etc.) leaves _manual_stop_requested stuck True, which
    # permanently blocks the watchdog from ever retrying.
    _manual_stop_requested = False
    # Treat the camera database as the source of truth. This prevents a stale
    # config/config.yaml (for example the demo camera checked into the repo) from
    # making the detector process only slot 1 while the dashboard has many active
    # NVR/controller channels saved in SQLite.
    _sync_config_active_cameras(_get_camera_db())
    stream_status = _ensure_streams_from_active_cameras()
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
                "stream_manager": stream_status,
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
        env={**os.environ, "PYTHONUNBUFFERED": "1", "AI_VISION_STREAM_FIRST": "1"},
        start_new_session=os.name != "nt",
    )
    _started_at = time.time()
    _last_exit_code = None
    _write_detector_pid(_process.pid)
    return _status()


@app.post("/api/stop")
def stop_detection() -> dict[str, Any]:
    global _process, _started_at, _last_exit_code, _stdout_handle, _stderr_handle, _manual_stop_requested
    _manual_stop_requested = True
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
    global _manual_stop_requested
    _manual_stop_requested = False
    stop_detection()
    _manual_stop_requested = False
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


@app.get("/api/catalog/items")
def catalog_items(scope_id: str) -> dict[str, Any]:
    scope = _catalog_scope(scope_id)
    db = _get_catalog_db()
    return {
        "items": db.list_items(scope),
        "schedule": _catalog_schedule(scope),
        "latest_run": db.latest_run(scope),
    }


@app.post("/api/catalog/items")
async def create_catalog_item(
    scope_id: str = Form(...),
    name: str = Form(...),
    files: list[UploadFile] = File(...),
) -> dict[str, Any]:
    import cv2
    import numpy as np
    from recognition.embedding import image_embedding

    scope = _catalog_scope(scope_id)
    item_name = " ".join(name.split()).strip()
    if not item_name:
        raise HTTPException(status_code=400, detail="Item name is required.")
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="Upload at least two reference images.")
    if len(files) > 12:
        raise HTTPException(status_code=400, detail="Upload no more than twelve reference images.")

    decoded: list[tuple[str, bytes, Any, list[float]]] = []
    for upload in files:
        if not (upload.content_type or "").startswith("image/"):
            raise HTTPException(status_code=400, detail=f"{upload.filename or 'File'} is not an image.")
        contents = await upload.read()
        if not contents or len(contents) > 8 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Each image must be between 1 byte and 8 MB.")
        frame = cv2.imdecode(np.frombuffer(contents, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise HTTPException(status_code=400, detail=f"{upload.filename or 'File'} could not be decoded.")
        decoded.append(
            (
                _catalog_safe_name(upload.filename or "reference.jpg"),
                contents,
                frame,
                image_embedding(frame),
            )
        )

    db = _get_catalog_db()
    if any(_catalog_normalize_name(item["name"]) == _catalog_normalize_name(item_name) for item in db.list_items(scope)):
        raise HTTPException(status_code=409, detail="An item with this name already exists.")
    item = db.create_item(scope, item_name)
    item_dir = CATALOG_IMAGE_DIR / scope / str(item["id"])
    item_dir.mkdir(parents=True, exist_ok=True)
    for index, (original_name, contents, frame, embedding) in enumerate(decoded, start=1):
        suffix = Path(original_name).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
            suffix = ".jpg"
        filename = f"reference_{index:02d}{suffix}"
        path = item_dir / filename
        path.write_bytes(contents)
        url = f"/snapshots/catalog/{quote(scope)}/{quote(str(item['id']))}/{quote(filename)}"
        db.add_image(
            item_id=str(item["id"]),
            filename=filename,
            url=url,
            embedding=embedding,
            width_px=int(frame.shape[1]),
            height_px=int(frame.shape[0]),
        )
    _audit(
        "catalog_item_created",
        {"scope_id": scope, "item_id": item["id"], "name": item_name, "image_count": len(decoded)},
    )
    recognition = await asyncio.to_thread(_run_catalog_recognition, scope)
    return {
        "item": db.get_item(str(item["id"])),
        "schedule": recognition["schedule"],
        "recognition": recognition,
    }


@app.delete("/api/catalog/items/{item_id}")
def delete_catalog_item(item_id: str, scope_id: str) -> dict[str, Any]:
    scope = _catalog_scope(scope_id)
    db = _get_catalog_db()
    item = db.get_item(item_id)
    if not item or item["scope_id"] != scope:
        raise HTTPException(status_code=404, detail="Catalog item not found.")
    filenames = db.delete_item(item_id)
    item_dir = (CATALOG_IMAGE_DIR / scope / item_id).resolve()
    catalog_root = CATALOG_IMAGE_DIR.resolve()
    if item_dir.is_relative_to(catalog_root):
        for filename in filenames:
            path = (item_dir / filename).resolve()
            if path.is_relative_to(item_dir) and path.exists():
                path.unlink()
        try:
            item_dir.rmdir()
        except OSError:
            pass
    _audit("catalog_item_deleted", {"scope_id": scope, "item_id": item_id, "name": item["name"]})
    return {"deleted": True, "item_id": item_id}


@app.get("/api/catalog/results")
def catalog_results(scope_id: str) -> dict[str, Any]:
    scope = _catalog_scope(scope_id)
    db = _get_catalog_db()
    return {
        "run": db.latest_run(scope),
        "results": db.latest_results(scope, detected_only=True),
        "schedule": _catalog_schedule(scope),
    }


@app.post("/api/catalog/recognition/run")
async def run_catalog_recognition(scope_id: str) -> dict[str, Any]:
    global _catalog_run_lock
    scope = _catalog_scope(scope_id)
    if _catalog_run_lock is None:
        _catalog_run_lock = asyncio.Lock()
    if _catalog_run_lock.locked():
        raise HTTPException(status_code=409, detail="A catalog recognition run is already active.")
    async with _catalog_run_lock:
        result = await asyncio.to_thread(_run_catalog_recognition, scope)
    _audit("catalog_recognition_completed", {"scope_id": scope, "run_id": result["run"]["id"]})
    return result


@app.post("/api/catalog/recognition/run-live")
async def start_live_catalog_recognition(scope_id: str) -> dict[str, Any]:
    """Sample the catalog's items against the live camera feeds repeatedly
    over CATALOG_LIVE_RUN_DURATION_SECONDS instead of a single instant
    snapshot - a slow-moving or briefly-occluded item is more likely to be
    caught. Only matches items enrolled via AI Check-in (same catalog the
    scheduled/instant recognition uses)."""
    scope = _catalog_scope(scope_id)
    existing = _live_catalog_runs.get(scope)
    if existing and existing["status"] == "running":
        raise HTTPException(status_code=409, detail="A live recognition run is already active for this scope.")

    started_at = datetime.now(timezone.utc)
    ends_at = started_at + timedelta(seconds=CATALOG_LIVE_RUN_DURATION_SECONDS)
    _live_catalog_runs[scope] = {
        "status": "running",
        "started_at": started_at.isoformat(),
        "ends_at": ends_at.isoformat(),
        "items": {},
    }
    _live_catalog_tasks[scope] = asyncio.create_task(_run_live_catalog_recognition(scope, ends_at))
    return _live_catalog_status_payload(scope)


@app.get("/api/catalog/recognition/run-live/status")
def live_catalog_recognition_status(scope_id: str) -> dict[str, Any]:
    scope = _catalog_scope(scope_id)
    return _live_catalog_status_payload(scope)


def _catalog_export_workbook(scope_id: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.table import Table, TableStyleInfo

    db = _get_catalog_db()
    run = db.latest_run(scope_id)
    results = db.latest_results(scope_id, detected_only=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Detected Items"
    sheet.sheet_view.showGridLines = False
    sheet.freeze_panes = "A6"
    sheet.merge_cells("A1:G1")
    sheet["A1"] = "AI Vision — Detected Item Count"
    sheet["A1"].font = Font(size=18, bold=True, color="FFFFFF")
    sheet["A1"].fill = PatternFill("solid", fgColor="1E3A5F")
    sheet["A1"].alignment = Alignment(vertical="center")
    sheet.row_dimensions[1].height = 30
    sheet["A3"] = "Recognition run"
    sheet["B3"] = str((run or {}).get("completed_at") or "No completed run")
    sheet["D3"] = "Schedule"
    sheet["E3"] = f"Every {_catalog_interval_hours()} hours"
    sheet["A4"] = "Scope"
    sheet["B4"] = scope_id
    sheet["D4"] = "Detected item types"
    sheet["E4"] = len(results)
    headers = ["Item", "Count", "Confidence", "Width (cm)", "Height (cm)", "Depth (cm)", "3D method"]
    sheet.append(headers)
    header_fill = PatternFill("solid", fgColor="2563EB")
    for cell in sheet[5]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for result in results:
        sheet.append(
            [
                result["item_name"],
                int(result["quantity"]),
                float(result["confidence"]),
                round(float(result["width_m"]) * 100, 1) if result.get("width_m") else None,
                round(float(result["height_m"]) * 100, 1) if result.get("height_m") else None,
                round(float(result["depth_m"]) * 100, 1) if result.get("depth_m") else None,
                result.get("measurement_method") or "Not measured",
            ]
        )
    if results:
        table = Table(displayName="DetectedItems", ref=f"A5:G{5 + len(results)}")
        table.tableStyleInfo = TableStyleInfo(
            name="TableStyleMedium2",
            showFirstColumn=False,
            showLastColumn=False,
            showRowStripes=True,
            showColumnStripes=False,
        )
        sheet.add_table(table)
    sheet.column_dimensions["A"].width = 30
    sheet.column_dimensions["B"].width = 12
    sheet.column_dimensions["C"].width = 14
    sheet.column_dimensions["D"].width = 14
    sheet.column_dimensions["E"].width = 14
    sheet.column_dimensions["F"].width = 14
    sheet.column_dimensions["G"].width = 30
    for row in sheet.iter_rows(min_row=6, max_row=5 + len(results), min_col=2, max_col=6):
        for cell in row:
            cell.alignment = Alignment(horizontal="center")
    for cell in sheet["C"][5:]:
        cell.number_format = "0.0%"
    for column in ("D", "E", "F"):
        for cell in sheet[column][5:]:
            cell.number_format = "0.0"
    sheet.auto_filter.ref = f"A5:G{max(5, 5 + len(results))}"
    sheet.print_title_rows = "1:5"
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.fitToWidth = 1
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


@app.get("/api/catalog/results/export.xlsx")
def export_catalog_results(scope_id: str) -> Response:
    scope = _catalog_scope(scope_id)
    content = _catalog_export_workbook(scope)
    filename = f"detected-items-{datetime.now(timezone.utc).date().isoformat()}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/v2/companies")
def list_companies() -> dict[str, Any]:
    return {"companies": _get_accounts_db().list_companies()}


@app.post("/api/v2/companies")
def create_company(payload: CompanyCreate) -> dict[str, Any]:
    company = _get_accounts_db().create_company(payload.name.strip())
    _audit("company_created", {"company_id": company["id"], "name": company["name"]})
    return company


@app.put("/api/v2/companies/{company_id}")
def rename_company(company_id: str, payload: CompanyRename) -> dict[str, Any]:
    company = _get_accounts_db().rename_company(company_id, payload.name.strip())
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found.")
    return company


@app.delete("/api/v2/companies/{company_id}")
def delete_company(company_id: str) -> dict[str, Any]:
    deleted = _get_accounts_db().delete_company(company_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Company not found.")
    _audit("company_deleted", {"company_id": company_id})
    return {"deleted": True, "company_id": company_id}


@app.put("/api/v2/companies/{company_id}/camera-config")
def update_camera_config(company_id: str, payload: CameraConfigUpdate) -> dict[str, Any]:
    nvrs = payload.cameraConfig.get("nvrs") or []
    if len(nvrs) > 5:
        raise HTTPException(status_code=400, detail="A company may connect at most 5 NVRs.")
    for nvr in nvrs:
        if int(nvr.get("slots") or 0) > 15:
            raise HTTPException(status_code=400, detail="Each NVR may expose at most 15 camera slots.")
    company = _get_accounts_db().set_camera_config(company_id, payload.cameraConfig)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found.")
    return company


@app.post("/api/v2/companies/{company_id}/roles")
def create_role(company_id: str, payload: RoleCreate) -> dict[str, Any]:
    if _get_accounts_db().get_company(company_id) is None:
        raise HTTPException(status_code=404, detail="Company not found.")
    try:
        role = _get_accounts_db().create_role(
            company_id,
            payload.name.strip(),
            payload.login.strip(),
            payload.password,
            access_camera=payload.access_camera,
            access_analytics=payload.access_analytics,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _audit("role_created", {"company_id": company_id, "role_id": role["id"], "login": role["login"]})
    return role


@app.put("/api/v2/roles/{role_id}")
def update_role(role_id: str, payload: RoleUpdate) -> dict[str, Any]:
    if _get_accounts_db().get_role(role_id) is None:
        raise HTTPException(status_code=404, detail="Role not found.")
    try:
        role = _get_accounts_db().update_role(
            role_id,
            name=payload.name.strip() if payload.name is not None else None,
            login=payload.login.strip() if payload.login is not None else None,
            password=payload.password,
            access_camera=payload.access_camera,
            access_analytics=payload.access_analytics,
        )
    except Exception as exc:  # duplicate login, etc.
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return role  # type: ignore[return-value]


@app.delete("/api/v2/roles/{role_id}")
def delete_role(role_id: str) -> dict[str, Any]:
    deleted = _get_accounts_db().delete_role(role_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Role not found.")
    _audit("role_deleted", {"role_id": role_id})
    return {"deleted": True, "role_id": role_id}


@app.get("/api/v2/accounts/{role_id}")
def get_account(role_id: str) -> dict[str, Any]:
    account = _get_accounts_db().get_role_public(role_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    return account


@app.get("/api/v2/admin/profile")
def get_admin_profile() -> dict[str, Any]:
    return _get_accounts_db().get_profile()


@app.put("/api/v2/admin/profile")
def update_admin_profile(payload: ProfileUpdate) -> dict[str, Any]:
    if payload.avatar and len(payload.avatar) > 3 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Profile picture is too large.")
    avatar_value: str | None = "__unset__"
    if payload.remove_avatar:
        avatar_value = None
    elif payload.avatar is not None:
        avatar_value = payload.avatar
    return _get_accounts_db().update_profile(
        login=payload.login.strip() if payload.login else None,
        password=payload.password,
        avatar=avatar_value,
    )


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


@app.get("/api/live_frame")
async def live_frame(slot: int | None = None, camera: str | None = None):
    """Return the latest processed JPEG frame for one camera.

    The dashboard grid uses this polling endpoint instead of opening one
    long-lived MJPEG connection per slot. Browsers often cap concurrent
    connections per origin, so 10 simultaneous MJPEG streams can leave some
    screens stuck on "Waiting for frames" even when the backend is healthy.
    """

    latest = next((path for path in _live_feed_paths(slot=slot, camera=camera) if path.exists()), None)
    if latest is None:
        raise HTTPException(status_code=404, detail="No live frame is available yet.")

    for _ in range(5):
        data = latest.read_bytes()
        if data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9"):
            return Response(
                content=data,
                media_type="image/jpeg",
                headers={
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                    "Pragma": "no-cache",
                },
            )
        await asyncio.sleep(0.03)

    raise HTTPException(status_code=503, detail="Latest live frame is being written; retry.")


def _live_feed_path(slot: int | None = None, camera: str | None = None) -> Path:
    if slot is not None:
        return SNAPSHOT_DIR / f"latest_stream_slot_{slot}.jpg"
    if camera:
        safe_name = "".join(ch if ch.isalnum() else "_" for ch in camera).strip("_") or "camera"
        return SNAPSHOT_DIR / f"latest_stream_{safe_name}.jpg"
    return SNAPSHOT_DIR / "latest_stream.jpg"


def _live_feed_paths(slot: int | None = None, camera: str | None = None) -> list[Path]:
    paths = [_live_feed_path(slot=slot, camera=camera)]
    if slot is not None:
        paths.append(SNAPSHOT_DIR / f"latest_slot_{slot}.jpg")
    if camera:
        safe_name = "".join(ch if ch.isalnum() else "_" for ch in camera).strip("_") or "camera"
        paths.append(SNAPSHOT_DIR / f"latest_{safe_name}.jpg")
    paths.append(SNAPSHOT_DIR / "latest.jpg")
    return paths


app.mount("/dashboard-v2/assets", StaticFiles(directory=DASHBOARD_V2_DIR), name="dashboard-v2-assets")
app.mount("/assets", StaticFiles(directory=DASHBOARD_V2_DIR), name="dashboard-assets")
app.mount("/snapshots", StaticFiles(directory=SNAPSHOT_DIR), name="snapshots")
