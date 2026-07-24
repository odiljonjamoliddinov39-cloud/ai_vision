"""Companies, roles (accounts), and the admin profile for Company Control.

Replaces the browser-localStorage version of this feature: companies,
their roles/credentials, camera configuration, and account links are
now shared server state so an account link works on any device.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import uuid
from typing import Any

from database.db import AppDB, id_column_sql


def hash_password(password: str) -> str:
    iterations = 260_000
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(password: str, password_hash: str | None) -> bool:
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


DEFAULT_CAMERA_CONFIG = {"nvrs": [], "quality": "high", "feedGroups": {}}


class AccountsDB:
    def __init__(self, db_path: str = "database/accounts.db"):
        self.db_path = db_path
        self.db = AppDB(db_path)
        self._init_schema()

    def _sql(self, query: str) -> str:
        return self.db.sql(query)

    def _init_schema(self) -> None:
        timestamp_type = "TIMESTAMPTZ" if self.db.is_postgres else "DATETIME"
        bool_type = "BOOLEAN" if self.db.is_postgres else "INTEGER"
        with self.db.connect() as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS cc_companies (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    camera_config TEXT NOT NULL DEFAULT '{{}}',
                    created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
                    updated_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS cc_roles (
                    id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    login TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    access_camera {bool_type} NOT NULL DEFAULT {"FALSE" if self.db.is_postgres else 0},
                    access_analytics {bool_type} NOT NULL DEFAULT {"FALSE" if self.db.is_postgres else 0},
                    created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
                    updated_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(company_id, login)
                )
                """
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS cc_admin_profile (
                    id {id_column_sql(self.db)},
                    login TEXT NOT NULL DEFAULT 'admin',
                    password_hash TEXT,
                    avatar TEXT,
                    updated_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    # ---- serialization -------------------------------------------------

    def _serialize_role(self, row: Any) -> dict[str, Any]:
        data = self.db.serialize_row(row)
        return {
            "id": data["id"],
            "companyId": data["company_id"],
            "name": data["name"],
            "login": data["login"],
            "access": {
                "camera": bool(data["access_camera"]),
                "analytics": bool(data["access_analytics"]),
            },
        }

    def _serialize_company(self, row: Any, roles: list[dict[str, Any]]) -> dict[str, Any]:
        data = self.db.serialize_row(row)
        try:
            camera_config = json.loads(data.get("camera_config") or "{}")
        except (TypeError, ValueError):
            camera_config = {}
        if not camera_config:
            camera_config = dict(DEFAULT_CAMERA_CONFIG)
        camera_config.setdefault("nvrs", [])
        camera_config.setdefault("quality", "high")
        camera_config.setdefault("feedGroups", {})
        return {
            "id": data["id"],
            "name": data["name"],
            "cameraConfig": camera_config,
            "roles": roles,
        }

    # ---- companies -------------------------------------------------------

    def list_companies(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            company_rows = conn.execute(
                self._sql("SELECT * FROM cc_companies ORDER BY created_at ASC")
            ).fetchall()
            role_rows = conn.execute(
                self._sql("SELECT * FROM cc_roles ORDER BY created_at ASC")
            ).fetchall()
        roles_by_company: dict[str, list[dict[str, Any]]] = {}
        for row in role_rows:
            role = self._serialize_role(row)
            roles_by_company.setdefault(role["companyId"], []).append(role)
        return [
            self._serialize_company(row, roles_by_company.get(self.db.serialize_row(row)["id"], []))
            for row in company_rows
        ]

    def get_company(self, company_id: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                self._sql("SELECT * FROM cc_companies WHERE id = ?"), (company_id,)
            ).fetchone()
            if row is None:
                return None
            role_rows = conn.execute(
                self._sql("SELECT * FROM cc_roles WHERE company_id = ? ORDER BY created_at ASC"),
                (company_id,),
            ).fetchall()
        return self._serialize_company(row, [self._serialize_role(r) for r in role_rows])

    def create_company(self, name: str) -> dict[str, Any]:
        company_id = uuid.uuid4().hex
        with self.db.connect() as conn:
            conn.execute(
                self._sql("INSERT INTO cc_companies (id, name, camera_config) VALUES (?, ?, ?)"),
                (company_id, name, json.dumps(DEFAULT_CAMERA_CONFIG)),
            )
        return self.get_company(company_id)  # type: ignore[return-value]

    def rename_company(self, company_id: str, name: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            conn.execute(
                self._sql("UPDATE cc_companies SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"),
                (name, company_id),
            )
        return self.get_company(company_id)

    def set_camera_config(self, company_id: str, camera_config: dict[str, Any]) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            conn.execute(
                self._sql(
                    "UPDATE cc_companies SET camera_config = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
                ),
                (json.dumps(camera_config), company_id),
            )
        return self.get_company(company_id)

    def delete_company(self, company_id: str) -> bool:
        with self.db.connect() as conn:
            conn.execute(self._sql("DELETE FROM cc_roles WHERE company_id = ?"), (company_id,))
            cursor = conn.execute(self._sql("DELETE FROM cc_companies WHERE id = ?"), (company_id,))
            return bool(getattr(cursor, "rowcount", 0))

    # ---- roles -------------------------------------------------------------

    def create_role(
        self,
        company_id: str,
        name: str,
        login: str,
        password: str,
        access_camera: bool = False,
        access_analytics: bool = False,
    ) -> dict[str, Any]:
        with self.db.connect() as conn:
            existing = conn.execute(
                self._sql("SELECT id FROM cc_roles WHERE company_id = ? AND login = ?"),
                (company_id, login),
            ).fetchone()
            if existing is not None:
                raise ValueError("A role with this login already exists for this company.")
            role_id = uuid.uuid4().hex
            conn.execute(
                self._sql(
                    """
                    INSERT INTO cc_roles
                        (id, company_id, name, login, password_hash, access_camera, access_analytics)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """
                ),
                (
                    role_id,
                    company_id,
                    name,
                    login,
                    hash_password(password),
                    self.db.bool_value(access_camera),
                    self.db.bool_value(access_analytics),
                ),
            )
            row = conn.execute(self._sql("SELECT * FROM cc_roles WHERE id = ?"), (role_id,)).fetchone()
        return self._serialize_role(row)

    def update_role(
        self,
        role_id: str,
        *,
        name: str | None = None,
        login: str | None = None,
        password: str | None = None,
        access_camera: bool | None = None,
        access_analytics: bool | None = None,
    ) -> dict[str, Any] | None:
        fields: list[str] = []
        params: list[Any] = []
        if name is not None:
            fields.append("name = ?")
            params.append(name)
        if login is not None:
            fields.append("login = ?")
            params.append(login)
        if password is not None:
            fields.append("password_hash = ?")
            params.append(hash_password(password))
        if access_camera is not None:
            fields.append("access_camera = ?")
            params.append(self.db.bool_value(access_camera))
        if access_analytics is not None:
            fields.append("access_analytics = ?")
            params.append(self.db.bool_value(access_analytics))
        if not fields:
            return self.get_role(role_id)
        fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(role_id)
        with self.db.connect() as conn:
            conn.execute(self._sql(f"UPDATE cc_roles SET {', '.join(fields)} WHERE id = ?"), tuple(params))
        return self.get_role(role_id)

    def get_role(self, role_id: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(self._sql("SELECT * FROM cc_roles WHERE id = ?"), (role_id,)).fetchone()
        return self._serialize_role(row) if row is not None else None

    def get_role_public(self, role_id: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            role_row = conn.execute(self._sql("SELECT * FROM cc_roles WHERE id = ?"), (role_id,)).fetchone()
            if role_row is None:
                return None
            role = self._serialize_role(role_row)
            company_row = conn.execute(
                self._sql("SELECT * FROM cc_companies WHERE id = ?"), (role["companyId"],)
            ).fetchone()
        if company_row is None:
            return None
        company = self._serialize_company(company_row, [])
        return {
            "role": {"id": role["id"], "name": role["name"], "login": role["login"], "access": role["access"]},
            "company": {"id": company["id"], "name": company["name"], "cameraConfig": company["cameraConfig"]},
        }

    def delete_role(self, role_id: str) -> bool:
        with self.db.connect() as conn:
            cursor = conn.execute(self._sql("DELETE FROM cc_roles WHERE id = ?"), (role_id,))
            return bool(getattr(cursor, "rowcount", 0))

    # ---- admin profile -------------------------------------------------------

    def get_profile(self) -> dict[str, Any]:
        with self.db.connect() as conn:
            row = conn.execute(self._sql("SELECT * FROM cc_admin_profile WHERE id = 1")).fetchone()
            if row is None:
                conn.execute("INSERT INTO cc_admin_profile (id, login) VALUES (1, 'admin')")
                row = conn.execute(self._sql("SELECT * FROM cc_admin_profile WHERE id = 1")).fetchone()
        data = self.db.serialize_row(row)
        return {"login": data["login"], "avatar": data.get("avatar")}

    def update_profile(
        self, *, login: str | None = None, password: str | None = None, avatar: str | None = "__unset__"
    ) -> dict[str, Any]:
        self.get_profile()  # ensures the singleton row exists
        fields: list[str] = []
        params: list[Any] = []
        if login is not None:
            fields.append("login = ?")
            params.append(login)
        if password is not None:
            fields.append("password_hash = ?")
            params.append(hash_password(password))
        if avatar != "__unset__":
            fields.append("avatar = ?")
            params.append(avatar)
        if fields:
            fields.append("updated_at = CURRENT_TIMESTAMP")
            with self.db.connect() as conn:
                conn.execute(self._sql(f"UPDATE cc_admin_profile SET {', '.join(fields)} WHERE id = 1"), tuple(params))
        return self.get_profile()
