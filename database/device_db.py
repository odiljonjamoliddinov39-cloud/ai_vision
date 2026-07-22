"""Device-first persistence for AI Vision V2.

This lives beside the legacy camera table during migration, but represents the
new source of truth: devices, discovered services, channels, stream sessions,
and per-channel analytics configuration.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from database.db import AppDB, id_column_sql


class DeviceDB:
    def __init__(self, db_path: str = "database/devices.db"):
        self.db_path = db_path
        self.db = AppDB(db_path)
        self._init_schema()

    @contextmanager
    def _connect(self):
        with self.db.connect() as conn:
            yield conn

    def _sql(self, query: str) -> str:
        return self.db.sql(query)

    def _init_schema(self) -> None:
        timestamp_type = "TIMESTAMPTZ" if self.db.is_postgres else "DATETIME"
        bool_type = "BOOLEAN" if self.db.is_postgres else "INTEGER"
        bool_false = "FALSE" if self.db.is_postgres else "0"
        bool_true = "TRUE" if self.db.is_postgres else "1"
        with self._connect() as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS devices (
                    id {id_column_sql(self.db)},
                    name TEXT NOT NULL,
                    host TEXT NOT NULL,
                    vendor TEXT,
                    model TEXT,
                    device_type TEXT DEFAULT 'unknown',
                    discovery_status TEXT DEFAULT 'unknown',
                    auth_required {bool_type} DEFAULT {bool_false},
                    credentials_reference TEXT,
                    created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
                    updated_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS device_services (
                    id {id_column_sql(self.db)},
                    device_id INTEGER NOT NULL,
                    protocol TEXT NOT NULL,
                    port INTEGER NOT NULL,
                    service_type TEXT,
                    status TEXT DEFAULT 'unknown',
                    metadata TEXT DEFAULT '{{}}',
                    created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
                    updated_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS channels (
                    id {id_column_sql(self.db)},
                    device_id INTEGER NOT NULL,
                    external_channel_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    profile TEXT,
                    enabled {bool_type} DEFAULT {bool_true},
                    stream_reference TEXT NOT NULL,
                    camera_id INTEGER,
                    slot_number INTEGER,
                    created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
                    updated_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS stream_sessions (
                    id {id_column_sql(self.db)},
                    channel_id INTEGER NOT NULL,
                    status TEXT DEFAULT 'offline',
                    codec TEXT,
                    width INTEGER,
                    height INTEGER,
                    fps REAL,
                    last_frame_at TEXT,
                    reconnect_count INTEGER DEFAULT 0,
                    last_error TEXT,
                    created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
                    updated_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS analytics_config (
                    id {id_column_sql(self.db)},
                    channel_id INTEGER NOT NULL,
                    enabled {bool_type} DEFAULT {bool_false},
                    model TEXT,
                    target_fps REAL,
                    confidence_threshold REAL,
                    tracking_enabled {bool_type} DEFAULT {bool_true},
                    created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
                    updated_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def upsert_device_from_discovery(self, name: str, host: str, result: dict[str, Any]) -> dict[str, Any]:
        fingerprint = result.get("fingerprint") or {}
        services = result.get("services") or []
        with self._connect() as conn:
            row = conn.execute(
                self._sql("SELECT id FROM devices WHERE host = ? ORDER BY id DESC LIMIT 1"),
                (host,),
            ).fetchone()
            if row:
                device_id = row["id"]
                conn.execute(
                    self._sql(
                        """
                        UPDATE devices
                        SET name = ?, vendor = ?, model = ?, device_type = ?,
                            discovery_status = ?, auth_required = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """
                    ),
                    (
                        name,
                        fingerprint.get("vendor"),
                        fingerprint.get("model"),
                        fingerprint.get("device_type", "unknown"),
                        "reachable" if result.get("reachable") else "unreachable",
                        self.db.bool_value(any(bool(svc.get("requires_auth")) for svc in services)),
                        device_id,
                    ),
                )
            else:
                if self.db.is_postgres:
                    inserted = conn.execute(
                        """
                        INSERT INTO devices
                            (name, host, vendor, model, device_type, discovery_status, auth_required)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            name,
                            host,
                            fingerprint.get("vendor"),
                            fingerprint.get("model"),
                            fingerprint.get("device_type", "unknown"),
                            "reachable" if result.get("reachable") else "unreachable",
                            self.db.bool_value(any(bool(svc.get("requires_auth")) for svc in services)),
                        ),
                    ).fetchone()
                    device_id = inserted["id"]
                else:
                    cursor = conn.execute(
                        """
                        INSERT INTO devices
                            (name, host, vendor, model, device_type, discovery_status, auth_required)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            name,
                            host,
                            fingerprint.get("vendor"),
                            fingerprint.get("model"),
                            fingerprint.get("device_type", "unknown"),
                            "reachable" if result.get("reachable") else "unreachable",
                            self.db.bool_value(any(bool(svc.get("requires_auth")) for svc in services)),
                        ),
                    )
                    device_id = cursor.lastrowid

            conn.execute(self._sql("DELETE FROM device_services WHERE device_id = ?"), (device_id,))
            for service in services:
                conn.execute(
                    self._sql(
                        """
                        INSERT INTO device_services
                            (device_id, protocol, port, service_type, status, metadata)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """
                    ),
                    (
                        device_id,
                        service.get("protocol"),
                        service.get("port"),
                        str(service.get("protocol", "")).lower(),
                        service.get("status"),
                        "{}",
                    ),
                )
        return self.get_device(device_id)

    def add_channel(
        self,
        device_id: int,
        external_channel_id: str,
        name: str,
        stream_reference: str,
        profile: str | None = None,
        camera_id: int | None = None,
        slot_number: int | None = None,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            if self.db.is_postgres:
                row = conn.execute(
                    """
                    INSERT INTO channels
                        (device_id, external_channel_id, name, profile, stream_reference, camera_id, slot_number)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (device_id, external_channel_id, name, profile, stream_reference, camera_id, slot_number),
                ).fetchone()
                channel_id = row["id"]
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO channels
                        (device_id, external_channel_id, name, profile, stream_reference, camera_id, slot_number)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (device_id, external_channel_id, name, profile, stream_reference, camera_id, slot_number),
                )
                channel_id = cursor.lastrowid
            conn.execute(
                self._sql(
                    """
                    INSERT INTO stream_sessions (channel_id, status)
                    VALUES (?, 'offline')
                    """
                ),
                (channel_id,),
            )
            conn.execute(
                self._sql(
                    """
                    INSERT INTO analytics_config
                        (channel_id, enabled, model, target_fps, confidence_threshold, tracking_enabled)
                    VALUES (?, ?, NULL, NULL, NULL, ?)
                    """
                ),
                (channel_id, self.db.bool_value(False), self.db.bool_value(True)),
            )
        return self.get_channel(channel_id, include_secret=False)

    def list_devices(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM devices ORDER BY updated_at DESC, id DESC").fetchall()
        return [self._serialize_device(row) for row in rows]

    def get_device(self, device_id: int) -> dict[str, Any]:
        with self._connect() as conn:
            device = conn.execute(
                self._sql("SELECT * FROM devices WHERE id = ?"), (device_id,)
            ).fetchone()
            services = conn.execute(
                self._sql("SELECT * FROM device_services WHERE device_id = ? ORDER BY port"),
                (device_id,),
            ).fetchall()
            channels = conn.execute(
                self._sql("SELECT * FROM channels WHERE device_id = ? ORDER BY slot_number IS NULL, slot_number, id"),
                (device_id,),
            ).fetchall()
        data = self._serialize_device(device) if device else {}
        data["services"] = [dict(row) for row in services]
        data["channels"] = [self._serialize_channel(row, include_secret=False) for row in channels]
        return data

    def get_channel(self, channel_id: int, include_secret: bool = False) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                self._sql("SELECT * FROM channels WHERE id = ?"), (channel_id,)
            ).fetchone()
        return self._serialize_channel(row, include_secret=include_secret) if row else {}

    def list_channels(self, include_secret: bool = False) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM channels ORDER BY slot_number IS NULL, slot_number, id").fetchall()
        return [self._serialize_channel(row, include_secret=include_secret) for row in rows]

    def update_stream_session(self, channel_id: int, status: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                self._sql(
                    """
                    UPDATE stream_sessions
                    SET status = ?, codec = ?, width = ?, height = ?, fps = ?,
                        last_frame_at = ?, reconnect_count = ?, last_error = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE channel_id = ?
                    """
                ),
                (
                    status.get("status"),
                    status.get("codec"),
                    status.get("width"),
                    status.get("height"),
                    status.get("fps"),
                    status.get("last_frame_at"),
                    status.get("reconnect_count", 0),
                    status.get("last_error"),
                    channel_id,
                ),
            )

    def set_analytics_enabled(self, channel_id: int, enabled: bool) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute(
                self._sql(
                    """
                    UPDATE analytics_config
                    SET enabled = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE channel_id = ?
                    """
                ),
                (self.db.bool_value(enabled), channel_id),
            )
        return self.get_channel(channel_id, include_secret=False)

    @staticmethod
    def _serialize_device(row) -> dict[str, Any]:
        data = dict(row)
        data["auth_required"] = bool(data.get("auth_required"))
        data.pop("credentials_reference", None)
        return data

    @staticmethod
    def _serialize_channel(row, include_secret: bool = False) -> dict[str, Any]:
        data = dict(row)
        data["enabled"] = bool(data.get("enabled"))
        if not include_secret:
            data["masked_stream_reference"] = _mask_stream_reference(str(data.get("stream_reference", "")))
            data.pop("stream_reference", None)
        return data


def _mask_stream_reference(value: str) -> str:
    if "://" not in value or "@" not in value:
        return value
    scheme, rest = value.split("://", 1)
    credentials, endpoint = rest.split("@", 1)
    if ":" not in credentials:
        return value
    username, _password = credentials.split(":", 1)
    return f"{scheme}://{username}:****@{endpoint}"
