"""Persistence for camera connection settings.

Uses PostgreSQL when DATABASE_URL is set, otherwise falls back to SQLite for
local development/tests. Raw stream URLs stay server-side; API responses expose
masked URLs so RTSP credentials are not shown again after saving.
"""

from __future__ import annotations

from contextlib import contextmanager
from urllib.parse import urlsplit, urlunsplit

from database.db import AppDB, id_column_sql


class CameraDB:
    def __init__(self, db_path: str = "database/cameras.db"):
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
        is_active_type = "BOOLEAN" if self.db.is_postgres else "INTEGER"
        active_default = "FALSE" if self.db.is_postgres else "0"
        timestamp_type = "TIMESTAMPTZ" if self.db.is_postgres else "DATETIME"
        with self._connect() as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS camera_controllers (
                    id {id_column_sql(self.db)},
                    name TEXT NOT NULL,
                    host TEXT NOT NULL,
                    protocol TEXT NOT NULL,
                    port INTEGER NOT NULL,
                    username TEXT,
                    password TEXT,
                    channel_start INTEGER NOT NULL,
                    channel_count INTEGER NOT NULL,
                    start_slot INTEGER NOT NULL,
                    stream_path_template TEXT NOT NULL,
                    camera_name_template TEXT NOT NULL,
                    status TEXT DEFAULT 'unknown',
                    last_error TEXT,
                    created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
                    updated_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS cameras (
                    id {id_column_sql(self.db)},
                    name TEXT NOT NULL,
                    stream_url TEXT NOT NULL,
                    status TEXT DEFAULT 'unknown',
                    is_active {is_active_type} DEFAULT {active_default},
                    controller_id INTEGER,
                    channel_number INTEGER,
                    slot_number INTEGER,
                    created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
                    updated_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self._ensure_slot_column(conn)
            self._ensure_controller_columns(conn)
            self._backfill_active_slots(conn)

    def _ensure_controller_columns(self, conn) -> None:
        columns = self.db.table_columns(conn, "cameras")
        if "controller_id" not in columns:
            conn.execute("ALTER TABLE cameras ADD COLUMN controller_id INTEGER")
        if "channel_number" not in columns:
            conn.execute("ALTER TABLE cameras ADD COLUMN channel_number INTEGER")

    def _ensure_slot_column(self, conn) -> None:
        columns = self.db.table_columns(conn, "cameras")
        if "slot_number" not in columns:
            conn.execute("ALTER TABLE cameras ADD COLUMN slot_number INTEGER")

    def _backfill_active_slots(self, conn) -> None:
        active_clause = "is_active = TRUE" if self.db.is_postgres else "is_active = 1"
        rows = conn.execute(
            f"""
            SELECT id
            FROM cameras
            WHERE {active_clause} AND slot_number IS NULL
            ORDER BY id
            """
        ).fetchall()
        for slot_number, row in enumerate(rows, start=1):
            conn.execute(
                self._sql("UPDATE cameras SET slot_number = ? WHERE id = ?"),
                (slot_number, row["id"]),
            )

    def add_camera(self, name: str, stream_url: str, status: str = "unknown") -> dict:
        return self.upsert_camera(
            name=name,
            stream_url=stream_url,
            status=status,
            controller_id=None,
            channel_number=None,
            is_active=False,
            slot_number=None,
        )

    def upsert_camera(
        self,
        *,
        name: str,
        stream_url: str,
        status: str,
        controller_id: int | None,
        channel_number: int | None,
        is_active: bool,
        slot_number: int | None,
    ) -> dict:
        with self._connect() as conn:
            row = None
            if controller_id is not None and channel_number is not None:
                row = conn.execute(
                    self._sql(
                        "SELECT id FROM cameras WHERE controller_id = ? AND channel_number = ? ORDER BY id DESC LIMIT 1"
                    ),
                    (controller_id, channel_number),
                ).fetchone()
            if row is None:
                row = conn.execute(
                    self._sql(
                        "SELECT id FROM cameras WHERE stream_url = ? ORDER BY id DESC LIMIT 1"
                    ),
                    (stream_url,),
                ).fetchone()

            if row is None:
                if self.db.is_postgres:
                    row = conn.execute(
                        """
                        INSERT INTO cameras (
                            name, stream_url, status, is_active, controller_id,
                            channel_number, slot_number
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            name,
                            stream_url,
                            status,
                            self.db.bool_value(is_active),
                            controller_id,
                            channel_number,
                            slot_number,
                        ),
                    ).fetchone()
                    camera_id = row["id"]
                else:
                    cursor = conn.execute(
                        """
                        INSERT INTO cameras (
                            name, stream_url, status, is_active, controller_id,
                            channel_number, slot_number
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            name,
                            stream_url,
                            status,
                            self.db.bool_value(is_active),
                            controller_id,
                            channel_number,
                            slot_number,
                        ),
                    )
                    camera_id = cursor.lastrowid
            else:
                camera_id = row["id"]
                conn.execute(
                    self._sql(
                        """
                        UPDATE cameras
                        SET name = ?, stream_url = ?, status = ?, is_active = ?,
                            controller_id = ?, channel_number = ?, slot_number = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """
                    ),
                    (
                        name,
                        stream_url,
                        status,
                        self.db.bool_value(is_active),
                        controller_id,
                        channel_number,
                        slot_number,
                        camera_id,
                    ),
                )

            self._delete_duplicate_camera_rows(conn, camera_id, stream_url, controller_id, channel_number)

        return self.get_camera(camera_id, include_secret=False)

    def _delete_duplicate_camera_rows(
        self,
        conn,
        camera_id: int,
        stream_url: str,
        controller_id: int | None,
        channel_number: int | None,
    ) -> None:
        clauses = ["id <> ?", "stream_url = ?"]
        params: list[object] = [camera_id, stream_url]
        if controller_id is not None and channel_number is not None:
            clauses.append("(controller_id = ? OR channel_number = ?)")
            params.extend([controller_id, channel_number])
        conn.execute(
            self._sql(f"DELETE FROM cameras WHERE {' AND '.join(clauses)}"),
            tuple(params),
        )

    def upsert_controller(
        self,
        *,
        name: str,
        host: str,
        protocol: str,
        port: int,
        username: str | None,
        password: str | None,
        channel_start: int,
        channel_count: int,
        start_slot: int,
        stream_path_template: str,
        camera_name_template: str,
        status: str,
        last_error: str | None,
    ) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                self._sql(
                    """
                    SELECT id
                    FROM camera_controllers
                    WHERE host = ? AND protocol = ? AND port = ? AND COALESCE(username, '') = COALESCE(?, '')
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                (host, protocol, port, username),
            ).fetchone()

            if row is None:
                if self.db.is_postgres:
                    row = conn.execute(
                        """
                        INSERT INTO camera_controllers (
                            name, host, protocol, port, username, password,
                            channel_start, channel_count, start_slot,
                            stream_path_template, camera_name_template,
                            status, last_error
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            name,
                            host,
                            protocol,
                            port,
                            username,
                            password,
                            channel_start,
                            channel_count,
                            start_slot,
                            stream_path_template,
                            camera_name_template,
                            status,
                            last_error,
                        ),
                    ).fetchone()
                    controller_id = row["id"]
                else:
                    cursor = conn.execute(
                        """
                        INSERT INTO camera_controllers (
                            name, host, protocol, port, username, password,
                            channel_start, channel_count, start_slot,
                            stream_path_template, camera_name_template,
                            status, last_error
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            name,
                            host,
                            protocol,
                            port,
                            username,
                            password,
                            channel_start,
                            channel_count,
                            start_slot,
                            stream_path_template,
                            camera_name_template,
                            status,
                            last_error,
                        ),
                    )
                    controller_id = cursor.lastrowid
            else:
                controller_id = row["id"]
                conn.execute(
                    self._sql(
                        """
                        UPDATE camera_controllers
                        SET name = ?, username = ?, password = ?, channel_start = ?,
                            channel_count = ?, start_slot = ?, stream_path_template = ?,
                            camera_name_template = ?, status = ?, last_error = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """
                    ),
                    (
                        name,
                        username,
                        password,
                        channel_start,
                        channel_count,
                        start_slot,
                        stream_path_template,
                        camera_name_template,
                        status,
                        last_error,
                        controller_id,
                    ),
                )

        return self.get_controller(controller_id, include_secret=False)

    def get_controller(self, controller_id: int, include_secret: bool = False) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                self._sql("SELECT * FROM camera_controllers WHERE id = ?"),
                (controller_id,),
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        if not include_secret:
            data.pop("password", None)
        return data

    def replace_controller_cameras(self, controller_id: int, cameras: list[dict]) -> list[dict]:
        saved: list[dict] = []
        keep_ids: list[int] = []
        for camera in cameras:
            record = self.upsert_camera(
                name=str(camera["name"]),
                stream_url=str(camera["stream_url"]),
                status=str(camera.get("status") or "disconnected"),
                controller_id=controller_id,
                channel_number=int(camera["channel_number"]),
                is_active=bool(camera.get("is_active", False)),
                slot_number=int(camera["slot_number"]) if camera.get("slot_number") is not None else None,
            )
            keep_ids.append(int(record["id"]))
            saved.append(record)

        with self._connect() as conn:
            if keep_ids:
                placeholders = ", ".join("?" for _ in keep_ids)
                conn.execute(
                    self._sql(
                        f"DELETE FROM cameras WHERE controller_id = ? AND id NOT IN ({placeholders})"
                    ),
                    (controller_id, *keep_ids),
                )
            else:
                conn.execute(
                    self._sql("DELETE FROM cameras WHERE controller_id = ?"),
                    (controller_id,),
                )
        return saved

    def get_camera(self, camera_id: int, include_secret: bool = False) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                self._sql("SELECT * FROM cameras WHERE id = ?"), (camera_id,)
            ).fetchone()
        return self._serialize(row, include_secret=include_secret) if row else None

    def list_cameras(self, include_secret: bool = False) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM cameras
                ORDER BY is_active DESC, slot_number IS NULL, slot_number ASC, id DESC
                """
            ).fetchall()
        return [self._serialize(row, include_secret=include_secret) for row in rows]

    def list_active_cameras(self, include_secret: bool = False) -> list[dict]:
        active_clause = "is_active = TRUE" if self.db.is_postgres else "is_active = 1"
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM cameras
                WHERE {active_clause}
                ORDER BY slot_number ASC, id ASC
                """
            ).fetchall()
        return [self._serialize(row, include_secret=include_secret) for row in rows]

    def set_status(self, camera_id: int, status: str) -> dict | None:
        with self._connect() as conn:
            conn.execute(
                self._sql(
                    "UPDATE cameras SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
                ),
                (status, camera_id),
            )
        return self.get_camera(camera_id, include_secret=False)

    def set_controller_status(self, controller_id: int, status: str, last_error: str | None = None) -> dict | None:
        with self._connect() as conn:
            conn.execute(
                self._sql(
                    "UPDATE camera_controllers SET status = ?, last_error = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
                ),
                (status, last_error, controller_id),
            )
        return self.get_controller(controller_id, include_secret=False)

    def set_active(self, camera_id: int, slot_number: int = 1) -> dict | None:
        return self.assign_slot(camera_id, slot_number)

    def assign_slot(self, camera_id: int, slot_number: int) -> dict | None:
        camera = self.get_camera(camera_id, include_secret=True)
        if camera is None:
            return None

        with self._connect() as conn:
            conn.execute(
                self._sql(
                    """
                    UPDATE cameras
                    SET is_active = ?, slot_number = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? OR slot_number = ?
                    """
                ),
                (self.db.bool_value(False), camera_id, slot_number),
            )
            conn.execute(
                self._sql(
                    """
                    UPDATE cameras
                    SET is_active = ?, slot_number = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """
                ),
                (self.db.bool_value(True), slot_number, camera_id),
            )
        return self.get_camera(camera_id, include_secret=True)

    def clear_slot(self, slot_number: int) -> None:
        with self._connect() as conn:
            conn.execute(
                self._sql(
                    """
                    UPDATE cameras
                    SET is_active = ?, slot_number = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE slot_number = ?
                    """
                ),
                (self.db.bool_value(False), slot_number),
            )

    def delete_camera(self, camera_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                self._sql("DELETE FROM cameras WHERE id = ?"), (camera_id,)
            )
            return cursor.rowcount > 0

    @staticmethod
    def _serialize(row, include_secret: bool = False) -> dict:
        data = dict(row)
        data["is_active"] = bool(data["is_active"])
        if include_secret:
            return data

        data["masked_stream_url"] = mask_stream_url(data["stream_url"])
        data.pop("stream_url", None)
        return data


def mask_stream_url(stream_url: str) -> str:
    stream_url = stream_url.strip()
    try:
        parsed = urlsplit(stream_url)
    except ValueError:
        return _mask_stream_url_fallback(stream_url)

    if not parsed.username or parsed.password is None:
        return stream_url

    host = parsed.hostname or ""
    try:
        port = parsed.port
    except ValueError:
        return _mask_stream_url_fallback(stream_url)

    if port is not None:
        host = f"{host}:{port}"

    username = parsed.username
    netloc = f"{username}:****@{host}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def _mask_stream_url_fallback(stream_url: str) -> str:
    if "://" not in stream_url or "@" not in stream_url:
        return stream_url

    scheme, rest = stream_url.split("://", 1)
    credentials, endpoint = rest.split("@", 1)
    if ":" not in credentials:
        return stream_url

    username, _password = credentials.split(":", 1)
    return f"{scheme}://{username}:****@{endpoint}"
