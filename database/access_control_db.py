"""Dashboard V2 access-control persistence.

This module owns the new enterprise access model only. It intentionally does
not duplicate camera, warehouse, tracking, or recognition tables; V2 scopes
refer to those existing resources by id.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from typing import Any

from database.db import AppDB, id_column_sql


DEFAULT_PERMISSIONS = [
    "dashboard.view",
    "camera.view",
    "camera.create",
    "camera.edit",
    "camera.delete",
    "camera.configure",
    "camera.live_view",
    "controller.view",
    "controller.create",
    "controller.edit",
    "controller.delete",
    "count.view",
    "count.correct",
    "count.delete",
    "count.export",
    "report.view",
    "report.create",
    "report.export",
    "product.view",
    "product.create",
    "product.edit",
    "product.delete",
    "alert.view",
    "alert.acknowledge",
    "alert.resolve",
    "alert.configure",
    "user.view",
    "user.create",
    "user.edit",
    "user.disable",
    "role.view",
    "role.create",
    "role.edit",
    "role.delete",
    "module.view",
    "module.assign",
    "scope.assign",
    "ai.view",
    "ai.configure",
    "ai.deploy",
    "system.view",
    "system.configure",
    "audit.view",
]


DEFAULT_MODULES = [
    {
        "name": "Home Overview",
        "code": "home",
        "description": "Operator landing page and daily summary.",
        "icon": "home",
        "route": "/dashboard-v2",
        "category": "operations",
        "component_key": "HomeOverviewPage",
        "default_order": 1,
        "required_permission": "dashboard.view",
    },
    {
        "name": "Live Monitoring",
        "code": "live_monitoring",
        "description": "Live camera grid and AI-detected frames.",
        "icon": "camera",
        "route": "/dashboard-v2/live",
        "category": "vision",
        "component_key": "LiveMonitoringPage",
        "default_order": 2,
        "required_permission": "camera.live_view",
    },
    {
        "name": "Counting",
        "code": "counting",
        "description": "Current count totals and correction workflow.",
        "icon": "counter",
        "route": "/dashboard-v2/counting",
        "category": "operations",
        "component_key": "CountingPage",
        "default_order": 3,
        "required_permission": "count.view",
    },
    {
        "name": "Products",
        "code": "products",
        "description": "Products and recognized stock.",
        "icon": "box",
        "route": "/dashboard-v2/products",
        "category": "inventory",
        "component_key": "ProductsPage",
        "default_order": 4,
        "required_permission": "product.view",
    },
    {
        "name": "Current Shift",
        "code": "current_shift",
        "description": "Shift-level operational status.",
        "icon": "clock",
        "route": "/dashboard-v2/shift",
        "category": "operations",
        "component_key": "CurrentShiftPage",
        "default_order": 5,
        "required_permission": "count.view",
    },
    {
        "name": "Verification Queue",
        "code": "verification_queue",
        "description": "Human review queue for uncertain events.",
        "icon": "check",
        "route": "/dashboard-v2/verification",
        "category": "quality",
        "component_key": "VerificationQueuePage",
        "default_order": 6,
        "required_permission": "count.correct",
    },
    {
        "name": "Alerts",
        "code": "alerts",
        "description": "Active and historical alerts.",
        "icon": "alert",
        "route": "/dashboard-v2/alerts",
        "category": "safety",
        "component_key": "AlertsPage",
        "default_order": 7,
        "required_permission": "alert.view",
    },
    {
        "name": "Reports",
        "code": "reports",
        "description": "Operational reports and exports.",
        "icon": "report",
        "route": "/dashboard-v2/reports",
        "category": "reporting",
        "component_key": "ReportsPage",
        "default_order": 8,
        "required_permission": "report.view",
    },
    {
        "name": "Analytics",
        "code": "analytics",
        "description": "Trends, anomalies, and performance.",
        "icon": "chart",
        "route": "/dashboard-v2/analytics",
        "category": "analytics",
        "component_key": "AnalyticsPage",
        "default_order": 9,
        "required_permission": "report.view",
    },
    {
        "name": "Camera Management",
        "code": "camera_management",
        "description": "Camera assignment and configuration.",
        "icon": "cctv",
        "route": "/dashboard-v2/cameras",
        "category": "administration",
        "component_key": "CameraManagementPage",
        "default_order": 10,
        "required_permission": "camera.configure",
    },
    {
        "name": "Controller Management",
        "code": "controller_management",
        "description": "NVR/controller configuration.",
        "icon": "server",
        "route": "/dashboard-v2/controllers",
        "category": "administration",
        "component_key": "ControllerManagementPage",
        "default_order": 11,
        "required_permission": "controller.view",
    },
    {
        "name": "System Health",
        "code": "system_health",
        "description": "Backend, AI, and camera health.",
        "icon": "pulse",
        "route": "/dashboard-v2/health",
        "category": "system",
        "component_key": "SystemHealthPage",
        "default_order": 12,
        "required_permission": "system.view",
    },
    {
        "name": "Audit Logs",
        "code": "audit_logs",
        "description": "Tamper-evident access and mutation logs.",
        "icon": "audit",
        "route": "/dashboard-v2/audit",
        "category": "security",
        "component_key": "AuditLogsPage",
        "default_order": 13,
        "required_permission": "audit.view",
    },
    {
        "name": "Profile",
        "code": "profile",
        "description": "Current user profile and account details.",
        "icon": "user",
        "route": "/dashboard-v2/profile",
        "category": "account",
        "component_key": "ProfilePage",
        "default_order": 14,
        "required_permission": "dashboard.view",
    },
    {
        "name": "Activity History",
        "code": "activity_history",
        "description": "Recent user and warehouse activity.",
        "icon": "history",
        "route": "/dashboard-v2/activity",
        "category": "reporting",
        "component_key": "ActivityHistoryPage",
        "default_order": 15,
        "required_permission": "report.view",
    },
]


DEFAULT_ROLES = {
    "super_admin": {
        "name": "Super Admin",
        "permissions": DEFAULT_PERMISSIONS,
        "modules": [module["code"] for module in DEFAULT_MODULES],
    },
    "company_admin": {
        "name": "Company Admin",
        "permissions": [
            "dashboard.view",
            "camera.view",
            "camera.live_view",
            "camera.configure",
            "controller.view",
            "count.view",
            "count.correct",
            "count.export",
            "report.view",
            "report.export",
            "product.view",
            "product.create",
            "product.edit",
            "alert.view",
            "alert.acknowledge",
            "alert.resolve",
            "user.view",
            "user.create",
            "user.edit",
            "role.view",
            "module.view",
            "module.assign",
            "scope.assign",
            "system.view",
            "audit.view",
        ],
        "modules": [
            "home",
            "live_monitoring",
            "counting",
            "products",
            "alerts",
            "reports",
            "analytics",
            "camera_management",
            "controller_management",
            "system_health",
            "audit_logs",
            "profile",
            "activity_history",
        ],
    },
    "factory_manager": {
        "name": "Factory Manager",
        "permissions": [
            "dashboard.view",
            "camera.view",
            "camera.live_view",
            "count.view",
            "count.correct",
            "report.view",
            "report.export",
            "product.view",
            "alert.view",
            "system.view",
        ],
        "modules": ["home", "live_monitoring", "counting", "products", "alerts", "reports", "analytics", "system_health", "profile"],
    },
    "warehouse_manager": {
        "name": "Warehouse Manager",
        "permissions": [
            "dashboard.view",
            "camera.view",
            "camera.live_view",
            "count.view",
            "count.correct",
            "report.view",
            "report.export",
            "product.view",
            "alert.view",
        ],
        "modules": ["home", "live_monitoring", "counting", "products", "current_shift", "verification_queue", "alerts", "reports", "profile"],
    },
    "shift_supervisor": {
        "name": "Shift Supervisor",
        "permissions": ["dashboard.view", "camera.view", "camera.live_view", "count.view", "count.correct", "alert.view", "report.view"],
        "modules": ["home", "live_monitoring", "counting", "current_shift", "verification_queue", "alerts", "profile"],
    },
    "operator": {
        "name": "Operator",
        "permissions": ["dashboard.view", "camera.view", "camera.live_view", "count.view", "alert.view"],
        "modules": ["home", "live_monitoring", "counting", "current_shift", "alerts", "profile"],
    },
    "analyst": {
        "name": "Analyst",
        "permissions": ["dashboard.view", "camera.view", "count.view", "report.view", "report.export", "product.view"],
        "modules": ["home", "counting", "products", "reports", "analytics", "activity_history", "profile"],
    },
    "technician": {
        "name": "Technician",
        "permissions": ["dashboard.view", "camera.view", "camera.live_view", "camera.configure", "controller.view", "controller.edit", "system.view"],
        "modules": ["home", "live_monitoring", "camera_management", "controller_management", "system_health", "profile"],
    },
    "viewer": {
        "name": "Viewer",
        "permissions": ["dashboard.view", "camera.view", "camera.live_view", "count.view", "alert.view", "report.view"],
        "modules": ["home", "live_monitoring", "counting", "alerts", "reports", "profile"],
    },
}


class AccessControlDB:
    def __init__(self, db_path: str = "database/access_control.db"):
        self.db_path = db_path
        self.db = AppDB(db_path)
        self._init_schema()
        self.seed_defaults()

    def _sql(self, query: str) -> str:
        return self.db.sql(query)

    def _bool(self, value: bool) -> bool | int:
        return self.db.bool_value(value)

    def _insert_returning_id(self, conn, sqlite_query: str, pg_query: str, params: tuple) -> int:
        if self.db.is_postgres:
            row = conn.execute(pg_query, params).fetchone()
            return int(row["id"])
        cursor = conn.execute(sqlite_query, params)
        return int(cursor.lastrowid)

    def _init_schema(self) -> None:
        timestamp_type = "TIMESTAMPTZ" if self.db.is_postgres else "DATETIME"
        bool_type = "BOOLEAN" if self.db.is_postgres else "INTEGER"
        true_value = "TRUE" if self.db.is_postgres else "1"
        false_value = "FALSE" if self.db.is_postgres else "0"
        with self.db.connect() as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS ac_users (
                    id {id_column_sql(self.db)},
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'active',
                    preferred_auth_method TEXT NOT NULL DEFAULT 'biometric_first',
                    password_hash TEXT,
                    password_updated_at {timestamp_type},
                    last_login_at {timestamp_type},
                    created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
                    updated_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            columns = self.db.table_columns(conn, "ac_users")
            if "password_hash" not in columns:
                conn.execute("ALTER TABLE ac_users ADD COLUMN password_hash TEXT")
            if "preferred_auth_method" not in columns:
                conn.execute("ALTER TABLE ac_users ADD COLUMN preferred_auth_method TEXT NOT NULL DEFAULT 'biometric_first'")
            if "password_updated_at" not in columns:
                conn.execute(f"ALTER TABLE ac_users ADD COLUMN password_updated_at {timestamp_type}")
            if "last_login_at" not in columns:
                conn.execute(f"ALTER TABLE ac_users ADD COLUMN last_login_at {timestamp_type}")
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS ac_sessions (
                    id {id_column_sql(self.db)},
                    user_id INTEGER NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
                    last_seen_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS ac_auth_challenges (
                    id {id_column_sql(self.db)},
                    user_id INTEGER NOT NULL,
                    challenge TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS ac_webauthn_credentials (
                    id {id_column_sql(self.db)},
                    user_id INTEGER NOT NULL,
                    credential_id TEXT NOT NULL UNIQUE,
                    public_key TEXT NOT NULL,
                    sign_count INTEGER NOT NULL DEFAULT 0,
                    name TEXT,
                    created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
                    last_used_at {timestamp_type}
                )
                """
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS ac_roles (
                    id {id_column_sql(self.db)},
                    name TEXT NOT NULL,
                    code TEXT NOT NULL UNIQUE,
                    is_active {bool_type} NOT NULL DEFAULT {true_value},
                    created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
                    updated_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS ac_permissions (
                    id {id_column_sql(self.db)},
                    code TEXT NOT NULL UNIQUE,
                    description TEXT,
                    created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS ac_modules (
                    id {id_column_sql(self.db)},
                    name TEXT NOT NULL,
                    code TEXT NOT NULL UNIQUE,
                    description TEXT,
                    icon TEXT,
                    route TEXT NOT NULL,
                    category TEXT,
                    component_key TEXT,
                    is_active {bool_type} NOT NULL DEFAULT {true_value},
                    default_order INTEGER NOT NULL DEFAULT 100,
                    required_permission TEXT,
                    created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
                    updated_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS ac_user_roles (
                    user_id INTEGER NOT NULL,
                    role_id INTEGER NOT NULL,
                    created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, role_id)
                )
                """
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS ac_role_permissions (role_id INTEGER NOT NULL, permission_code TEXT NOT NULL, UNIQUE(role_id, permission_code))"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS ac_role_modules (role_id INTEGER NOT NULL, module_code TEXT NOT NULL, is_enabled INTEGER NOT NULL DEFAULT 1, display_order INTEGER, UNIQUE(role_id, module_code))"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS ac_user_permissions (user_id INTEGER NOT NULL, permission_code TEXT NOT NULL, effect TEXT NOT NULL CHECK(effect IN ('allow','deny')), UNIQUE(user_id, permission_code))"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS ac_user_modules (user_id INTEGER NOT NULL, module_code TEXT NOT NULL, effect TEXT NOT NULL CHECK(effect IN ('allow','deny')), display_order INTEGER, UNIQUE(user_id, module_code))"
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS ac_user_scopes (
                    id {id_column_sql(self.db)},
                    user_id INTEGER NOT NULL,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL,
                    effect TEXT NOT NULL DEFAULT 'allow' CHECK(effect IN ('allow','deny')),
                    created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS ac_dashboard_layouts (
                    id {id_column_sql(self.db)},
                    owner_type TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    is_active {bool_type} NOT NULL DEFAULT {true_value},
                    created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
                    updated_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS ac_dashboard_layout_items (
                    id {id_column_sql(self.db)},
                    layout_id INTEGER NOT NULL,
                    module_code TEXT NOT NULL,
                    display_order INTEGER NOT NULL DEFAULT 100,
                    widget_size TEXT DEFAULT 'medium',
                    default_filters_json TEXT DEFAULT '{{}}',
                    created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS ac_organizations (
                    id {id_column_sql(self.db)},
                    type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    parent_id INTEGER,
                    is_active {bool_type} NOT NULL DEFAULT {true_value},
                    created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
                    updated_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            if self.db.is_postgres:
                conn.execute(
                    """
                    INSERT INTO ac_organizations (id, type, name, is_active)
                    VALUES (1, 'company', 'Default Company', TRUE)
                    ON CONFLICT (id) DO NOTHING
                    """
                )
            else:
                conn.execute(
                    "INSERT OR IGNORE INTO ac_organizations (id, type, name, is_active) VALUES (1, 'company', 'Default Company', ?)",
                    (self._bool(True),),
                )

    def seed_defaults(self) -> None:
        with self.db.connect() as conn:
            for code in DEFAULT_PERMISSIONS:
                if self.db.is_postgres:
                    conn.execute(
                        "INSERT INTO ac_permissions (code, description) VALUES (%s, %s) ON CONFLICT (code) DO NOTHING",
                        (code, code.replace(".", " ").title()),
                    )
                else:
                    conn.execute(
                        "INSERT OR IGNORE INTO ac_permissions (code, description) VALUES (?, ?)",
                        (code, code.replace(".", " ").title()),
                    )

            for module in DEFAULT_MODULES:
                params = (
                    module["name"],
                    module["code"],
                    module["description"],
                    module["icon"],
                    module["route"],
                    module["category"],
                    module["component_key"],
                    self._bool(True),
                    module["default_order"],
                    module["required_permission"],
                )
                if self.db.is_postgres:
                    conn.execute(
                        """
                        INSERT INTO ac_modules (
                            name, code, description, icon, route, category, component_key,
                            is_active, default_order, required_permission
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (code) DO UPDATE SET
                            name = EXCLUDED.name,
                            description = EXCLUDED.description,
                            icon = EXCLUDED.icon,
                            route = EXCLUDED.route,
                            category = EXCLUDED.category,
                            component_key = EXCLUDED.component_key,
                            required_permission = EXCLUDED.required_permission
                        """,
                        params,
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO ac_modules (
                            name, code, description, icon, route, category, component_key,
                            is_active, default_order, required_permission
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(code) DO UPDATE SET
                            name = excluded.name,
                            description = excluded.description,
                            icon = excluded.icon,
                            route = excluded.route,
                            category = excluded.category,
                            component_key = excluded.component_key,
                            required_permission = excluded.required_permission
                        """,
                        params,
                    )

            for code, role in DEFAULT_ROLES.items():
                role_id = self._ensure_role(conn, role["name"], code)
                for permission in role["permissions"]:
                    self._insert_ignore(
                        conn,
                        "ac_role_permissions",
                        ("role_id", "permission_code"),
                        (role_id, permission),
                    )
                for index, module_code in enumerate(role["modules"], start=1):
                    self._insert_ignore(
                        conn,
                        "ac_role_modules",
                        ("role_id", "module_code", "is_enabled", "display_order"),
                        (role_id, module_code, 1, index),
                    )

            super_admin_id = self._ensure_user(conn, "Demo Super Admin", "admin@ai-vision.local", "active")
            super_admin_role_id = self._role_id(conn, "super_admin")
            if super_admin_role_id is not None:
                self._insert_ignore(
                    conn,
                    "ac_user_roles",
                    ("user_id", "role_id"),
                    (super_admin_id, super_admin_role_id),
                )

    def _insert_ignore(self, conn, table: str, columns: tuple[str, ...], values: tuple) -> None:
        placeholders = ", ".join(["%s" if self.db.is_postgres else "?"] * len(values))
        column_sql = ", ".join(columns)
        if self.db.is_postgres:
            conn.execute(
                f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
                values,
            )
        else:
            conn.execute(
                f"INSERT OR IGNORE INTO {table} ({column_sql}) VALUES ({placeholders})",
                values,
            )

    def _ensure_role(self, conn, name: str, code: str) -> int:
        row = conn.execute(self._sql("SELECT id FROM ac_roles WHERE code = ?"), (code,)).fetchone()
        if row:
            return int(row["id"])
        return self._insert_returning_id(
            conn,
            "INSERT INTO ac_roles (name, code, is_active) VALUES (?, ?, ?)",
            "INSERT INTO ac_roles (name, code, is_active) VALUES (%s, %s, %s) RETURNING id",
            (name, code, self._bool(True)),
        )

    def _ensure_user(self, conn, name: str, email: str, status: str = "active") -> int:
        row = conn.execute(self._sql("SELECT id FROM ac_users WHERE email = ?"), (email,)).fetchone()
        if row:
            return int(row["id"])
        return self._insert_returning_id(
            conn,
            "INSERT INTO ac_users (name, email, status) VALUES (?, ?, ?)",
            "INSERT INTO ac_users (name, email, status) VALUES (%s, %s, %s) RETURNING id",
            (name, email, status),
        )

    def _role_id(self, conn, role_code: str) -> int | None:
        row = conn.execute(self._sql("SELECT id FROM ac_roles WHERE code = ?"), (role_code,)).fetchone()
        return int(row["id"]) if row else None

    @staticmethod
    def _row(row) -> dict[str, Any]:
        data = dict(row)
        for key in ("is_active",):
            if key in data:
                data[key] = bool(data[key])
        if "password_hash" in data:
            data["has_password"] = bool(data.get("password_hash"))
            data.pop("password_hash", None)
        return data

    @staticmethod
    def _hash_password(password: str) -> str:
        iterations = 260_000
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations).hex()
        return f"pbkdf2_sha256${iterations}${salt}${digest}"

    @staticmethod
    def _verify_password_hash(password: str, password_hash: str | None) -> bool:
        if not password_hash:
            return False
        try:
            scheme, iterations_raw, salt, expected = password_hash.split("$", 3)
            if scheme != "pbkdf2_sha256":
                return False
            digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations_raw)).hex()
            return hmac.compare_digest(digest, expected)
        except Exception:
            return False

    @staticmethod
    def _hash_session_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def list_users(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM ac_users ORDER BY id DESC").fetchall()
            users = [self._row(row) for row in rows]
            for user in users:
                role_rows = conn.execute(
                    self._sql(
                        """
                        SELECT r.code
                        FROM ac_roles r
                        INNER JOIN ac_user_roles ur ON ur.role_id = r.id
                        WHERE ur.user_id = ?
                        ORDER BY r.name
                        """
                    ),
                    (user["id"],),
                ).fetchall()
                user["roles"] = [row["code"] for row in role_rows]
                count_row = conn.execute(
                    self._sql("SELECT COUNT(*) AS count FROM ac_webauthn_credentials WHERE user_id = ?"),
                    (user["id"],),
                ).fetchone()
                user["passkey_count"] = int(count_row["count"] or 0)
        return users

    def create_user(self, name: str, email: str) -> dict[str, Any]:
        with self.db.connect() as conn:
            user_id = self._ensure_user(conn, name, email, "active")
        return self.get_user(user_id) or {}

    def get_user(self, user_id: int) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(self._sql("SELECT * FROM ac_users WHERE id = ?"), (user_id,)).fetchone()
        return self._row(row) if row else None

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(self._sql("SELECT * FROM ac_users WHERE email = ?"), (email,)).fetchone()
        return self._row(row) if row else None

    def set_user_password(self, user_id: int, password: str) -> dict[str, Any] | None:
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters.")
        password_hash = self._hash_password(password)
        with self.db.connect() as conn:
            conn.execute(
                self._sql("UPDATE ac_users SET password_hash = ?, password_updated_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?"),
                (password_hash, user_id),
            )
            conn.execute(self._sql("DELETE FROM ac_sessions WHERE user_id = ?"), (user_id,))
        return self.get_user(user_id)

    def set_user_auth_preference(self, user_id: int, preferred_auth_method: str) -> dict[str, Any] | None:
        allowed = {"biometric_first", "password_first", "password_and_biometric"}
        if preferred_auth_method not in allowed:
            raise ValueError(f"Preferred auth method must be one of: {', '.join(sorted(allowed))}.")
        with self.db.connect() as conn:
            conn.execute(
                self._sql("UPDATE ac_users SET preferred_auth_method = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"),
                (preferred_auth_method, user_id),
            )
        return self.get_user(user_id)

    def authenticate_user(self, email: str, password: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(self._sql("SELECT * FROM ac_users WHERE email = ?"), (email.strip().lower(),)).fetchone()
            if not row:
                return None
            raw_user = dict(row)
            if raw_user.get("status") != "active":
                return None
            if not self._verify_password_hash(password, raw_user.get("password_hash")):
                return None
            conn.execute(self._sql("UPDATE ac_users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?"), (raw_user["id"],))
            return self._row(raw_user)

    def create_session(self, user_id: int) -> dict[str, Any]:
        token = secrets.token_urlsafe(32)
        token_hash = self._hash_session_token(token)
        with self.db.connect() as conn:
            self._insert_returning_id(
                conn,
                "INSERT INTO ac_sessions (user_id, token_hash) VALUES (?, ?)",
                "INSERT INTO ac_sessions (user_id, token_hash) VALUES (%s, %s) RETURNING id",
                (user_id, token_hash),
            )
        return {"token": token, "token_type": "bearer"}

    def get_user_by_session_token(self, token: str) -> dict[str, Any] | None:
        if not token:
            return None
        token_hash = self._hash_session_token(token)
        with self.db.connect() as conn:
            row = conn.execute(
                self._sql(
                    """
                    SELECT u.*
                    FROM ac_sessions s
                    INNER JOIN ac_users u ON u.id = s.user_id
                    WHERE s.token_hash = ?
                    """
                ),
                (token_hash,),
            ).fetchone()
            if not row:
                return None
            conn.execute(self._sql("UPDATE ac_sessions SET last_seen_at = CURRENT_TIMESTAMP WHERE token_hash = ?"), (token_hash,))
        user = self._row(row)
        return user if user.get("status") == "active" else None

    def create_challenge(self, user_id: int, challenge: str, purpose: str) -> int:
        with self.db.connect() as conn:
            conn.execute(self._sql("DELETE FROM ac_auth_challenges WHERE user_id = ? AND purpose = ?"), (user_id, purpose))
            return self._insert_returning_id(
                conn,
                "INSERT INTO ac_auth_challenges (user_id, challenge, purpose) VALUES (?, ?, ?)",
                "INSERT INTO ac_auth_challenges (user_id, challenge, purpose) VALUES (%s, %s, %s) RETURNING id",
                (user_id, challenge, purpose),
            )

    def consume_challenge(self, user_id: int, challenge_id: int, purpose: str) -> str | None:
        with self.db.connect() as conn:
            row = conn.execute(
                self._sql("SELECT challenge FROM ac_auth_challenges WHERE id = ? AND user_id = ? AND purpose = ?"),
                (challenge_id, user_id, purpose),
            ).fetchone()
            if not row:
                return None
            conn.execute(self._sql("DELETE FROM ac_auth_challenges WHERE id = ?"), (challenge_id,))
        return str(row["challenge"])

    def add_passkey(self, user_id: int, credential_id: str, public_key: str, sign_count: int, name: str | None = None) -> dict[str, Any]:
        with self.db.connect() as conn:
            if self.db.is_postgres:
                conn.execute(
                    """
                    INSERT INTO ac_webauthn_credentials (user_id, credential_id, public_key, sign_count, name)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (credential_id) DO UPDATE SET
                        public_key = EXCLUDED.public_key,
                        sign_count = EXCLUDED.sign_count,
                        name = EXCLUDED.name
                    """,
                    (user_id, credential_id, public_key, sign_count, name),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO ac_webauthn_credentials (user_id, credential_id, public_key, sign_count, name)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(credential_id) DO UPDATE SET
                        public_key = excluded.public_key,
                        sign_count = excluded.sign_count,
                        name = excluded.name
                    """,
                    (user_id, credential_id, public_key, sign_count, name),
                )
        return {"credential_id": credential_id, "name": name or "Passkey", "sign_count": sign_count}

    def list_passkeys(self, user_id: int) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                self._sql(
                    """
                    SELECT id, user_id, credential_id, public_key, sign_count, name, created_at, last_used_at
                    FROM ac_webauthn_credentials
                    WHERE user_id = ?
                    ORDER BY id DESC
                    """
                ),
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_passkey(self, credential_id: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                self._sql("SELECT * FROM ac_webauthn_credentials WHERE credential_id = ?"),
                (credential_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_passkey_sign_count(self, credential_id: str, sign_count: int) -> None:
        with self.db.connect() as conn:
            conn.execute(
                self._sql("UPDATE ac_webauthn_credentials SET sign_count = ?, last_used_at = CURRENT_TIMESTAMP WHERE credential_id = ?"),
                (sign_count, credential_id),
            )

    def set_user_status(self, user_id: int, status: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            conn.execute(self._sql("UPDATE ac_users SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"), (status, user_id))
        return self.get_user(user_id)

    def list_roles(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM ac_roles ORDER BY name").fetchall()
        return [self._row(row) for row in rows]

    def create_role(self, name: str, code: str) -> dict[str, Any]:
        code = code.strip().lower().replace(" ", "_").replace("-", "_")
        with self.db.connect() as conn:
            role_id = self._ensure_role(conn, name, code)
        return self.get_role(role_id) or {}

    def get_role(self, role_id: int) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(self._sql("SELECT * FROM ac_roles WHERE id = ?"), (role_id,)).fetchone()
        return self._row(row) if row else None

    def list_permissions(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM ac_permissions ORDER BY code").fetchall()
        return [dict(row) for row in rows]

    def list_modules(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM ac_modules ORDER BY default_order, name").fetchall()
        return [self._row(row) for row in rows]

    def assign_role(self, user_id: int, role_code: str) -> None:
        with self.db.connect() as conn:
            role_id = self._role_id(conn, role_code)
            if role_id is None:
                raise KeyError(role_code)
            self._insert_ignore(conn, "ac_user_roles", ("user_id", "role_id"), (user_id, role_id))

    def remove_role(self, user_id: int, role_code: str) -> None:
        with self.db.connect() as conn:
            role_id = self._role_id(conn, role_code)
            if role_id is not None:
                conn.execute(self._sql("DELETE FROM ac_user_roles WHERE user_id = ? AND role_id = ?"), (user_id, role_id))

    def set_user_module(self, user_id: int, module_code: str, effect: str, display_order: int | None = None) -> None:
        if effect not in {"allow", "deny"}:
            raise ValueError("effect must be allow or deny")
        with self.db.connect() as conn:
            if self.db.is_postgres:
                conn.execute(
                    """
                    INSERT INTO ac_user_modules (user_id, module_code, effect, display_order)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id, module_code) DO UPDATE SET
                        effect = EXCLUDED.effect,
                        display_order = EXCLUDED.display_order
                    """,
                    (user_id, module_code, effect, display_order),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO ac_user_modules (user_id, module_code, effect, display_order)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id, module_code) DO UPDATE SET
                        effect = excluded.effect,
                        display_order = excluded.display_order
                    """,
                    (user_id, module_code, effect, display_order),
                )

    def set_user_permission(self, user_id: int, permission_code: str, effect: str) -> None:
        if effect not in {"allow", "deny"}:
            raise ValueError("effect must be allow or deny")
        with self.db.connect() as conn:
            if self.db.is_postgres:
                conn.execute(
                    """
                    INSERT INTO ac_user_permissions (user_id, permission_code, effect)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, permission_code) DO UPDATE SET effect = EXCLUDED.effect
                    """,
                    (user_id, permission_code, effect),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO ac_user_permissions (user_id, permission_code, effect)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id, permission_code) DO UPDATE SET effect = excluded.effect
                    """,
                    (user_id, permission_code, effect),
                )

    def set_user_scope(self, user_id: int, scope_type: str, scope_ids: list[str], effect: str = "allow") -> None:
        if effect not in {"allow", "deny"}:
            raise ValueError("effect must be allow or deny")
        with self.db.connect() as conn:
            conn.execute(
                self._sql("DELETE FROM ac_user_scopes WHERE user_id = ? AND scope_type = ? AND effect = ?"),
                (user_id, scope_type, effect),
            )
            for scope_id in scope_ids:
                conn.execute(
                    self._sql("INSERT INTO ac_user_scopes (user_id, scope_type, scope_id, effect) VALUES (?, ?, ?, ?)"),
                    (user_id, scope_type, str(scope_id), effect),
                )

    def resolve_dashboard(self, user_id: int | None = None, email: str | None = None) -> dict[str, Any]:
        user = self.get_user(user_id) if user_id is not None else None
        if user is None and email:
            user = self.get_user_by_email(email)
        if user is None:
            return self.empty_dashboard(email=email)
        if user.get("status") != "active":
            result = self.empty_dashboard(email=user.get("email"))
            result["user"] = {**user, "roles": []}
            result["disabled"] = True
            return result

        uid = int(user["id"])
        with self.db.connect() as conn:
            roles = conn.execute(
                self._sql(
                    """
                    SELECT r.* FROM ac_roles r
                    INNER JOIN ac_user_roles ur ON ur.role_id = r.id
                    WHERE ur.user_id = ? AND r.is_active = ?
                    ORDER BY r.name
                    """
                ),
                (uid, self._bool(True)),
            ).fetchall()
            role_ids = [int(role["id"]) for role in roles]

            permissions: set[str] = set()
            role_modules: dict[str, dict[str, Any]] = {}
            if role_ids:
                placeholder = ",".join(["%s" if self.db.is_postgres else "?"] * len(role_ids))
                for row in conn.execute(f"SELECT permission_code FROM ac_role_permissions WHERE role_id IN ({placeholder})", tuple(role_ids)).fetchall():
                    permissions.add(row["permission_code"])
                for row in conn.execute(
                    f"""
                    SELECT m.*, rm.display_order
                    FROM ac_role_modules rm
                    INNER JOIN ac_modules m ON m.code = rm.module_code
                    WHERE rm.role_id IN ({placeholder}) AND rm.is_enabled = 1 AND m.is_active = {1 if not self.db.is_postgres else 'TRUE'}
                    """,
                    tuple(role_ids),
                ).fetchall():
                    module = self._row(row)
                    role_modules[module["code"]] = module

            for row in conn.execute(self._sql("SELECT permission_code, effect FROM ac_user_permissions WHERE user_id = ?"), (uid,)).fetchall():
                if row["effect"] == "deny":
                    permissions.discard(row["permission_code"])
                else:
                    permissions.add(row["permission_code"])

            modules = dict(role_modules)
            user_module_rows = conn.execute(
                self._sql(
                    """
                    SELECT um.effect, um.display_order, m.*
                    FROM ac_user_modules um
                    INNER JOIN ac_modules m ON m.code = um.module_code
                    WHERE um.user_id = ? AND m.is_active = ?
                    """
                ),
                (uid, self._bool(True)),
            ).fetchall()
            for row in user_module_rows:
                module = self._row(row)
                code = module["code"]
                if row["effect"] == "deny":
                    modules.pop(code, None)
                else:
                    modules[code] = module

            scopes = self._scopes_for_user(conn, uid)

        final_modules = []
        for module in modules.values():
            required = module.get("required_permission")
            if required and required not in permissions:
                continue
            final_modules.append(
                {
                    "id": module["id"],
                    "code": module["code"],
                    "name": module["name"],
                    "route": module["route"],
                    "icon": module.get("icon"),
                    "order": int(module.get("display_order") or module.get("default_order") or 100),
                    "category": module.get("category"),
                    "component_key": module.get("component_key"),
                    "required_permission": required,
                }
            )
        final_modules.sort(key=lambda item: (item["order"], item["name"]))
        user["roles"] = [self._row(role) for role in roles]
        return {
            "user": user,
            "modules": final_modules,
            "permissions": sorted(permissions),
            "scope": scopes,
        }

    def _scopes_for_user(self, conn, user_id: int) -> dict[str, list[str]]:
        scope = {
            "company_ids": [],
            "factory_ids": [],
            "warehouse_ids": [],
            "production_line_ids": [],
            "zone_ids": [],
            "camera_ids": [],
        }
        mapping = {
            "company": "company_ids",
            "factory": "factory_ids",
            "warehouse": "warehouse_ids",
            "production_line": "production_line_ids",
            "zone": "zone_ids",
            "camera": "camera_ids",
        }
        rows = conn.execute(
            self._sql("SELECT scope_type, scope_id, effect FROM ac_user_scopes WHERE user_id = ? ORDER BY id"),
            (user_id,),
        ).fetchall()
        denied: dict[str, set[str]] = {key: set() for key in scope}
        allowed: dict[str, list[str]] = {key: [] for key in scope}
        for row in rows:
            key = mapping.get(row["scope_type"])
            if not key:
                continue
            value = str(row["scope_id"])
            if row["effect"] == "deny":
                denied[key].add(value)
            elif value not in allowed[key]:
                allowed[key].append(value)
        for key, values in allowed.items():
            scope[key] = [value for value in values if value not in denied[key]]
        return scope

    @staticmethod
    def empty_dashboard(email: str | None = None) -> dict[str, Any]:
        return {
            "user": {
                "id": None,
                "name": "Unassigned User",
                "email": email or "unassigned@ai-vision.local",
                "roles": [],
            },
            "modules": [],
            "permissions": [],
            "scope": {
                "company_ids": [],
                "factory_ids": [],
                "warehouse_ids": [],
                "production_line_ids": [],
                "zone_ids": [],
                "camera_ids": [],
            },
        }

    def module_allowed(self, dashboard: dict[str, Any], module_code: str) -> bool:
        return any(module["code"] == module_code for module in dashboard.get("modules", []))

    def permission_allowed(self, dashboard: dict[str, Any], permission_code: str) -> bool:
        return permission_code in set(dashboard.get("permissions", []))

    def list_organizations(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM ac_organizations ORDER BY parent_id, type, name").fetchall()
        return [self._row(row) for row in rows]

    def audit_payload(self, old_value: Any = None, new_value: Any = None) -> dict[str, Any]:
        return {"old_value": old_value, "new_value": new_value}
