"""
SQLite persistence for camera connection settings.

Raw stream URLs stay server-side. API responses expose masked URLs so
RTSP credentials are not shown again after saving.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


class CameraDB:
    def __init__(self, db_path: str = "database/cameras.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cameras (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    stream_url TEXT NOT NULL,
                    status TEXT DEFAULT 'unknown',
                    is_active INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def add_camera(self, name: str, stream_url: str, status: str = "unknown") -> dict:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO cameras (name, stream_url, status, is_active)
                VALUES (?, ?, ?, 0)
                """,
                (name, stream_url, status),
            )
            camera_id = cursor.lastrowid
        return self.get_camera(camera_id, include_secret=False)

    def get_camera(self, camera_id: int, include_secret: bool = False) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM cameras WHERE id = ?", (camera_id,)).fetchone()
        return self._serialize(row, include_secret=include_secret) if row else None

    def list_cameras(self, include_secret: bool = False) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM cameras ORDER BY is_active DESC, id DESC").fetchall()
        return [self._serialize(row, include_secret=include_secret) for row in rows]

    def set_status(self, camera_id: int, status: str) -> dict | None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE cameras SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, camera_id),
            )
        return self.get_camera(camera_id, include_secret=False)

    def set_active(self, camera_id: int) -> dict | None:
        camera = self.get_camera(camera_id, include_secret=True)
        if camera is None:
            return None

        with self._connect() as conn:
            conn.execute("UPDATE cameras SET is_active = 0")
            conn.execute(
                """
                UPDATE cameras
                SET is_active = 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (camera_id,),
            )
        return self.get_camera(camera_id, include_secret=True)

    def ensure_default_camera(self, name: str, stream_url: str) -> None:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS count FROM cameras").fetchone()
            if int(row["count"]) > 0:
                return

            conn.execute(
                """
                INSERT INTO cameras (name, stream_url, status, is_active)
                VALUES (?, ?, 'unknown', 1)
                """,
                (name, stream_url),
            )

    @staticmethod
    def _serialize(row: sqlite3.Row, include_secret: bool = False) -> dict:
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
