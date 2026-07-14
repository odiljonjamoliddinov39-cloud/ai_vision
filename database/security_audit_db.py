"""Tamper-evident security audit log.

Uses PostgreSQL when DATABASE_URL is set, otherwise SQLite. Each row stores a
hash of the event payload plus the previous row hash. Editing/deleting an old
event breaks verification for everything after it.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from database.db import AppDB, id_column_sql


class SecurityAuditDB:
    def __init__(self, db_path: str):
        self.db = AppDB(db_path)
        self._init_db()

    def _sql(self, query: str) -> str:
        return self.db.sql(query)

    def _init_db(self) -> None:
        timestamp_type = "DOUBLE PRECISION" if self.db.is_postgres else "REAL"
        with self.db.connect() as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS security_audit_log (
                    id {id_column_sql(self.db)},
                    created_at {timestamp_type} NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    current_hash TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_security_audit_created_at
                ON security_audit_log(created_at DESC)
                """
            )

    @staticmethod
    def _canonical_json(value: dict[str, Any]) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)

    @staticmethod
    def _hash_text(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _last_hash(self, conn) -> str:
        row = conn.execute(
            "SELECT current_hash FROM security_audit_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return str(row["current_hash"]) if row else "GENESIS"

    def append(self, actor: str, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        created_at = time.time()
        payload_json = self._canonical_json(payload)
        payload_hash = self._hash_text(payload_json)
        with self.db.connect() as conn:
            previous_hash = self._last_hash(conn)
            current_hash = self._hash_text(
                self._canonical_json(
                    {
                        "created_at": created_at,
                        "actor": actor,
                        "action": action,
                        "payload_hash": payload_hash,
                        "previous_hash": previous_hash,
                    }
                )
            )
            if self.db.is_postgres:
                row = conn.execute(
                    """
                    INSERT INTO security_audit_log (
                        created_at, actor, action, payload_json, payload_hash,
                        previous_hash, current_hash
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        created_at,
                        actor,
                        action,
                        payload_json,
                        payload_hash,
                        previous_hash,
                        current_hash,
                    ),
                ).fetchone()
                audit_id = row["id"]
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO security_audit_log (
                        created_at, actor, action, payload_json, payload_hash,
                        previous_hash, current_hash
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        created_at,
                        actor,
                        action,
                        payload_json,
                        payload_hash,
                        previous_hash,
                        current_hash,
                    ),
                )
                audit_id = cursor.lastrowid
            return {
                "id": audit_id,
                "created_at": created_at,
                "actor": actor,
                "action": action,
                "payload_hash": payload_hash,
                "previous_hash": previous_hash,
                "current_hash": current_hash,
            }

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                self._sql(
                    """
                    SELECT id, created_at, actor, action, payload_hash, previous_hash, current_hash
                    FROM security_audit_log
                    ORDER BY id DESC
                    LIMIT ?
                    """
                ),
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def verify(self) -> dict[str, Any]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, actor, action, payload_json, payload_hash,
                       previous_hash, current_hash
                FROM security_audit_log
                ORDER BY id ASC
                """
            ).fetchall()

        previous_hash = "GENESIS"
        for row in rows:
            payload_json = str(row["payload_json"])
            expected_payload_hash = self._hash_text(payload_json)
            if row["payload_hash"] != expected_payload_hash:
                return {
                    "verified": False,
                    "event_count": len(rows),
                    "broken_at_id": row["id"],
                    "reason": "payload_hash_mismatch",
                }
            if row["previous_hash"] != previous_hash:
                return {
                    "verified": False,
                    "event_count": len(rows),
                    "broken_at_id": row["id"],
                    "reason": "previous_hash_mismatch",
                }
            expected_current_hash = self._hash_text(
                self._canonical_json(
                    {
                        "created_at": row["created_at"],
                        "actor": row["actor"],
                        "action": row["action"],
                        "payload_hash": row["payload_hash"],
                        "previous_hash": row["previous_hash"],
                    }
                )
            )
            if row["current_hash"] != expected_current_hash:
                return {
                    "verified": False,
                    "event_count": len(rows),
                    "broken_at_id": row["id"],
                    "reason": "current_hash_mismatch",
                }
            previous_hash = str(row["current_hash"])

        return {
            "verified": True,
            "event_count": len(rows),
            "latest_hash": previous_hash,
        }
