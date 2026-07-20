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
from database.access_control_db import AccessControlDB  # noqa: E402
from database.camera_db import CameraDB  # noqa: E402
from database.security_audit_db import SecurityAuditDB  # noqa: E402
from database.tracking_db import TrackingDB  # noqa: E402
from database.warehouse_db import WarehouseDB  # noqa: E402


# ============================================================
# api/server.py — COPY/PASTE CHANGES
# ============================================================

# 1) Add this import next to the other database imports:

from database.company_portal_db import CompanyPortalDB


# 2) Add this constant next to the other DB paths:

COMPANY_PORTAL_DB_PATH = ROOT / "database" / "company_portal.db"


# 3) Add this global next to the other *_db globals:

_company_portal_db: CompanyPortalDB | None = None


# 4) Add this helper near _get_access_control_db():

def _get_company_portal_db() -> CompanyPortalDB:
    global _company_portal_db
    if _company_portal_db is None:
        _company_portal_db = CompanyPortalDB(
            db_path=str(COMPANY_PORTAL_DB_PATH)
        )
    return _company_portal_db


def _public_dashboard_url() -> str:
    return os.getenv(
        "PUBLIC_DASHBOARD_URL",
        "https://ai-vision-dashboard-phi.vercel.app",
    ).strip().rstrip("/")


# 5) Add these Pydantic request models near the other BaseModel classes:
/* ============================================================
   dashboard-v2/app.js — COPY/PASTE REPLACEMENTS
   ============================================================ */


/* 1) ADD this helper immediately after the existing api(path) function. */

async function apiJson(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-AI-Role": state.role,
      "X-AI-User-Name": "Dashboard V2 Preview",
      "X-AI-Company": "All Companies",
      ...(options.headers || {}),
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || response.statusText);
  }

  return response.json();
}


/* 2) REPLACE the block beginning with:
      const COMPANY_STORE_KEY = "ai_vision_v2_companies";
   and including loadCompanies() and saveCompanies()
   with this block. */

let companyStore = [];
let publicDashboardUrl = "https://ai-vision-dashboard-phi.vercel.app";

function loadCompanies() {
  return companyStore;
}

function saveCompanies(companies) {
  companyStore = Array.isArray(companies) ? companies : [];
}

async function loadCompanyControl() {
  const result = await api("/api/v2/company-control");
  companyStore = Array.isArray(result.companies) ? result.companies : [];
  publicDashboardUrl =
    result.public_dashboard_url ||
    "https://ai-vision-dashboard-phi.vercel.app";
  return companyStore;
}

async function persistCompanyControl(companies) {
  const result = await apiJson("/api/v2/company-control", {
    method: "POST",
    body: JSON.stringify({ companies }),
  });

  companyStore = Array.isArray(result.companies) ? result.companies : [];
  publicDashboardUrl =
    result.public_dashboard_url ||
    "https://ai-vision-dashboard-phi.vercel.app";

  return companyStore;
}


/* 3) REPLACE accountLink(role) with this version. */

function accountLink(role) {
  if (role.link) return role.link;
  if (role.token) {
    return `${publicDashboardUrl}/dashboard-v2#acc=${encodeURIComponent(
      role.token
    )}`;
  }
  return "";
}


/* 4) Change this function declaration:

function handleCompanyClick(event) {

   to:

async function handleCompanyClick(event) {


   Then REPLACE only the "save" action block with this version: */

  if (button.dataset.ccAction === "save") {
    try {
      const companies = ccCompanies();
      const saved = await persistCompanyControl(companies);
      ccDraft = saved;
      ccDirty = false;
      ccEditingCompany = null;
      toast("Changes saved on DigitalOcean — public links are ready.");
      renderCompanyControl(els.moduleContent);
      renderSideCompanies();
    } catch (error) {
      toast(error instanceof Error ? error.message : String(error));
    }
    return;
  }


/* 5) REPLACE resolveAccountFromHash() with these two functions. */

function accountTokenFromHash() {
  const match = window.location.hash.match(/acc=([^&]+)/i);
  return match ? decodeURIComponent(match[1]) : null;
}

async function resolveAccountFromHash() {
  const token = accountTokenFromHash();
  if (!token) return null;

  return apiJson(
    `/api/v2/company-control/accounts/public/${encodeURIComponent(token)}`,
    {
      headers: {
        "X-AI-Role": "viewer",
        "X-AI-User-Name": "Public account",
        "X-AI-Company": "Assigned company",
      },
    }
  );
}


/* 6) REPLACE persistAccountCompany() with this async version. */

async function persistAccountCompany() {
  const token = accountTokenFromHash();
  if (!token || !accountState?.company) return;

  const result = await apiJson(
    `/api/v2/company-control/accounts/public/${encodeURIComponent(token)}`,
    {
      method: "PUT",
      body: JSON.stringify({ company: accountState.company }),
      headers: {
        "X-AI-Role": "viewer",
        "X-AI-User-Name": "Public account",
        "X-AI-Company": accountState.company.name || "Assigned company",
      },
    }
  );

  accountState = result;
}


/* IMPORTANT:
   Existing places that call persistAccountCompany() may remain as they are.
   The request will run asynchronously. To display save failures visibly,
   use:

   persistAccountCompany().catch((error) =>
     toast(error instanceof Error ? error.message : String(error))
   );
*/


/* 7) REPLACE the complete load() function with this version. */

async function load() {
  const token = accountTokenFromHash();

  if (token) {
    const account = await resolveAccountFromHash();
    renderAccountView(account);
    return;
  }

  const [session, overview] = await Promise.all([
    api("/api/v2/rbac/me"),
    api("/api/v2/head/overview"),
    loadCompanyControl(),
  ]);

  state.session = session;
  state.overview = overview;

  els.pageTitle.textContent = "Head Dashboard";
  els.companiesSection.hidden = false;
  renderNavigation();
  renderSummary();
  renderScope();
  renderModuleContent();
}


/* 8) REPLACE these browser-only notes wherever they appear:

   "Stored in this browser for now — backend hookup pending."

   with:

   "Stored securely on the DigitalOcean backend."
*/

class CompanyControlSaveRequest(BaseModel):
    companies: list[dict[str, Any]] = Field(default_factory=list)


class PublicCompanyUpdateRequest(BaseModel):
    company: dict[str, Any]


# 6) Replace _is_public_path() with this version:

def _is_public_path(path: str) -> bool:
    return (
        path == "/"
        or path == "/api/status"
        or path.startswith("/assets/")
        or path.startswith("/api/v2/company-control/accounts/public/")
        or path in {"/favicon.ico", "/robots.txt"}
    )


# 7) Add these routes near the other /api/v2 routes:

@app.get("/api/v2/company-control")
def get_company_control(request: Request) -> dict[str, Any]:
    _require_permission(request, "manage_users")
    return {
        "companies": _get_company_portal_db().list_companies(),
        "public_dashboard_url": _public_dashboard_url(),
    }


@app.post("/api/v2/company-control")
def save_company_control(
    payload: CompanyControlSaveRequest,
    request: Request,
) -> dict[str, Any]:
    _require_permission(request, "manage_users")
    companies = _get_company_portal_db().save_companies(
        payload.companies,
        _public_dashboard_url(),
    )
    _audit(
        "company_control_saved",
        {
            "company_count": len(companies),
            "role_count": sum(
                len(company.get("roles") or [])
                for company in companies
            ),
        },
        actor=_request_actor(request),
    )
    return {
        "companies": companies,
        "public_dashboard_url": _public_dashboard_url(),
    }


@app.get("/api/v2/company-control/accounts/public/{token}")
def get_public_company_account(token: str) -> dict[str, Any]:
    account = _get_company_portal_db().get_public_account(token)
    if not account:
        raise HTTPException(
            status_code=404,
            detail="This account link is invalid or has been removed.",
        )
    return account


@app.put("/api/v2/company-control/accounts/public/{token}")
def update_public_company_account(
    token: str,
    payload: PublicCompanyUpdateRequest,
) -> dict[str, Any]:
    account = _get_company_portal_db().update_public_company(
        token,
        payload.company,
    )
    if not account:
        raise HTTPException(
            status_code=404,
            detail="This account link is invalid or has been removed.",
        )
    return account

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "config.yaml"
LOG_PATH = ROOT / "logs" / "events.log"
SNAPSHOT_DIR = ROOT / "snapshots"
INVENTORY_PATH = ROOT / "logs" / "inventory.json"
INVENTORY_IMAGE_DIR = SNAPSHOT_DIR / "inventory"
DASHBOARD_V2_DIR = ROOT / "dashboard-v2"
TRACKING_DB_PATH = ROOT / "database" / "tracking.db"
WAREHOUSE_DB_PATH = ROOT / "database" / "warehouse.db"
CAMERA_DB_PATH = ROOT / "database" / "cameras.db"
SECURITY_AUDIT_DB_PATH = ROOT / "database" / "security_audit.db"
ACCESS_CONTROL_DB_PATH = ROOT / "database" / "access_control.db"
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


app.add_middleware(
    CORSMiddleware,
    allow_origins=_env_list("ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-AI-User-Email", "X-Requested-With"],
)

_tracking_db: TrackingDB | None = None
_warehouse_db: WarehouseDB | None = None
_camera_db: CameraDB | None = None
_security_audit_db: SecurityAuditDB | None = None
_access_control_db: AccessControlDB | None = None
_rate_limits: dict[tuple[str, str, int], int] = {}
_watchdog_task: asyncio.Task | None = None
_manual_stop_requested = False
_watchdog_last_start_attempt = 0.0

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
            "/Streaming/Channels/{channel}02",
        ),
        camera_name_template=os.getenv(
            "CAMERA_CONTROLLER_CAMERA_NAME_TEMPLATE",
            "{controller} Camera {channel}",
        ),
        make_active=True,
        test_controller=False,
        test_streams=False,
        require_public=False,
    )

    last_slot = controller.start_slot + controller.channel_count - 1
    if last_slot > MAX_CAMERA_SLOTS:
        return

    for index in range(controller.channel_count):
        channel = controller.channel_start + index
        slot = controller.start_slot + index
        saved = db.add_camera(
            name=_controller_camera_name(controller, channel, slot),
            stream_url=_controller_stream_url(controller, channel),
            status="connected",
        )
        db.assign_slot(saved["id"], slot)

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
    limit = int(os.getenv("SECURITY_RATE_LIMIT_PER_MINUTE", "120"))
    if limit <= 0:
        return None
    actor = _request_actor(request)
    window = int(time.time() // 60)
    key = (actor, request.url.path, window)
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

    if path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"}:
        actor = _request_actor(request)
        _audit(
            "api.mutation",
            {"method": request.method, "path": path, "status_code": response.status_code},
            actor=actor,
        )
    return response

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
import sys
import cv2

raw = sys.argv[1].strip()
source = int(raw) if raw.isdigit() else raw

try:
    if isinstance(source, int) and os.name == "nt":
        cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
    elif isinstance(source, str) and source.lower().startswith("rtsp://"):
        os.environ.setdefault(
            "OPENCV_FFMPEG_CAPTURE_OPTIONS",
            "rtsp_transport;tcp|stimeout;8000000|max_delay;500000|buffer_size;102400",
        )
        cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
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


@app.on_event("startup")
async def start_detection_watchdog() -> None:
    global _watchdog_task
    if _watchdog_task is None or _watchdog_task.done():
        _watchdog_task = asyncio.create_task(_detection_watchdog())


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

    private_host_message = _private_controller_host_message(endpoint["host"])
    if controller.require_public and private_host_message:
        raise HTTPException(status_code=400, detail=private_host_message)

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
    global _process, _started_at, _last_exit_code, _stdout_handle, _stderr_handle, _manual_stop_requested
    request = request or StartRequest()
    if _detector_pid() is not None:
        raise HTTPException(status_code=409, detail="Detection is already running.")
    # Treat the camera database as the source of truth. This prevents a stale
    # config/config.yaml (for example the demo camera checked into the repo) from
    # making the detector process only slot 1 while the dashboard has many active
    # NVR/controller channels saved in SQLite.
    _sync_config_active_cameras(_get_camera_db())
    _validate_active_cameras_for_start()
    _manual_stop_requested = False
    _clear_live_frames()

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
        return SNAPSHOT_DIR / f"latest_slot_{slot}.jpg"
    if camera:
        safe_name = "".join(ch if ch.isalnum() else "_" for ch in camera).strip("_") or "camera"
        return SNAPSHOT_DIR / f"latest_{safe_name}.jpg"
    return SNAPSHOT_DIR / "latest.jpg"


def _live_feed_paths(slot: int | None = None, camera: str | None = None) -> list[Path]:
    return [_live_feed_path(slot=slot, camera=camera)]


app.mount("/dashboard-v2/assets", StaticFiles(directory=DASHBOARD_V2_DIR), name="dashboard-v2-assets")
app.mount("/assets", StaticFiles(directory=DASHBOARD_V2_DIR), name="dashboard-assets")
app.mount("/snapshots", StaticFiles(directory=SNAPSHOT_DIR), name="snapshots")
