from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from typing import Any

from database.db import AppDB


class CompanyPortalDB:
    """Persistent company/user-link store for Dashboard V2.

    The complete Company Control document is stored server-side. Public account
    links use cryptographically-random tokens. Passwords are never stored as
    plaintext.
    """

    def __init__(self, db_path: str = "database/company_portal.db"):
        self.db = AppDB(db_path)
        self._init_schema()

    def _sql(self, query: str) -> str:
        return self.db.sql(query)

    def _init_schema(self) -> None:
        timestamp_type = "TIMESTAMPTZ" if self.db.is_postgres else "DATETIME"
        with self.db.connect() as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS company_portal_accounts (
                    token TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL,
                    role_id TEXT NOT NULL UNIQUE,
                    company_json TEXT NOT NULL,
                    role_json TEXT NOT NULL,
                    password_hash TEXT,
                    created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
                    updated_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    @staticmethod
    def _hash_password(password: str) -> str:
        iterations = 260_000
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        ).hex()
        return f"pbkdf2_sha256${iterations}${salt}${digest}"

    @staticmethod
    def _safe_role(role: dict[str, Any], token: str) -> dict[str, Any]:
        result = dict(role)
        result.pop("password", None)
        result["token"] = token
        result["has_password"] = True
        return result

    def save_companies(
        self,
        companies: list[dict[str, Any]],
        public_dashboard_url: str,
    ) -> list[dict[str, Any]]:
        public_dashboard_url = public_dashboard_url.rstrip("/")
        saved_companies: list[dict[str, Any]] = []
        seen_role_ids: set[str] = set()

        with self.db.connect() as conn:
            for company in companies:
                company_copy = dict(company)
                company_id = str(company_copy.get("id") or secrets.token_urlsafe(8))
                company_copy["id"] = company_id
                saved_roles: list[dict[str, Any]] = []

                for role in company_copy.get("roles") or []:
                    role_copy = dict(role)
                    role_id = str(role_copy.get("id") or secrets.token_urlsafe(8))
                    role_copy["id"] = role_id
                    seen_role_ids.add(role_id)

                    existing = conn.execute(
                        self._sql(
                            "SELECT token, password_hash FROM company_portal_accounts WHERE role_id = ?"
                        ),
                        (role_id,),
                    ).fetchone()

                    token = str(existing["token"]) if existing else secrets.token_urlsafe(32)
                    password = str(role_copy.pop("password", "") or "")
                    password_hash = (
                        self._hash_password(password)
                        if password
                        else (existing["password_hash"] if existing else None)
                    )

                    safe_role = self._safe_role(role_copy, token)
                    safe_role["has_password"] = bool(password_hash)
                    safe_role["link"] = (
                        f"{public_dashboard_url}/dashboard-v2#acc={token}"
                    )

                    company_for_account = dict(company_copy)
                    company_for_account["roles"] = []

                    params = (
                        token,
                        company_id,
                        role_id,
                        json.dumps(company_for_account, ensure_ascii=False),
                        json.dumps(safe_role, ensure_ascii=False),
                        password_hash,
                    )

                    if self.db.is_postgres:
                        conn.execute(
                            """
                            INSERT INTO company_portal_accounts (
                                token, company_id, role_id, company_json,
                                role_json, password_hash
                            )
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (role_id) DO UPDATE SET
                                company_id = EXCLUDED.company_id,
                                company_json = EXCLUDED.company_json,
                                role_json = EXCLUDED.role_json,
                                password_hash = EXCLUDED.password_hash,
                                updated_at = CURRENT_TIMESTAMP
                            """,
                            params,
                        )
                    else:
                        conn.execute(
                            """
                            INSERT INTO company_portal_accounts (
                                token, company_id, role_id, company_json,
                                role_json, password_hash
                            )
                            VALUES (?, ?, ?, ?, ?, ?)
                            ON CONFLICT(role_id) DO UPDATE SET
                                company_id = excluded.company_id,
                                company_json = excluded.company_json,
                                role_json = excluded.role_json,
                                password_hash = excluded.password_hash,
                                updated_at = CURRENT_TIMESTAMP
                            """,
                            params,
                        )

                    saved_roles.append(safe_role)

                company_copy["roles"] = saved_roles
                saved_companies.append(company_copy)

            rows = conn.execute(
                "SELECT role_id FROM company_portal_accounts"
            ).fetchall()
            for row in rows:
                role_id = str(row["role_id"])
                if role_id not in seen_role_ids:
                    conn.execute(
                        self._sql(
                            "DELETE FROM company_portal_accounts WHERE role_id = ?"
                        ),
                        (role_id,),
                    )

        return saved_companies

    def list_companies(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT company_id, company_json, role_json
                FROM company_portal_accounts
                ORDER BY company_id, role_id
                """
            ).fetchall()

        companies: dict[str, dict[str, Any]] = {}
        for row in rows:
            company_id = str(row["company_id"])
            if company_id not in companies:
                company = json.loads(row["company_json"])
                company["roles"] = []
                companies[company_id] = company
            companies[company_id]["roles"].append(json.loads(row["role_json"]))

        return list(companies.values())

    def get_public_account(self, token: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                self._sql(
                    """
                    SELECT company_json, role_json
                    FROM company_portal_accounts
                    WHERE token = ?
                    """
                ),
                (token,),
            ).fetchone()

        if not row:
            return None

        company = json.loads(row["company_json"])
        role = json.loads(row["role_json"])
        return {
            "company": company,
            "role": role,
            "missing": False,
        }

    def update_public_company(
        self,
        token: str,
        company: dict[str, Any],
    ) -> dict[str, Any] | None:
        account = self.get_public_account(token)
        if not account:
            return None

        company_copy = dict(company)
        company_copy["roles"] = []
        company_json = json.dumps(company_copy, ensure_ascii=False)

        with self.db.connect() as conn:
            conn.execute(
                self._sql(
                    """
                    UPDATE company_portal_accounts
                    SET company_json = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE company_id = (
                        SELECT company_id
                        FROM company_portal_accounts
                        WHERE token = ?
                    )
                    """
                ),
                (company_json, token),
            )

        return self.get_public_account(token)
