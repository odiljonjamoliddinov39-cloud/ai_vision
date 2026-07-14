"""Small database compatibility layer.

Production uses PostgreSQL when DATABASE_URL is present. Local development and
tests continue to use SQLite paths passed by the existing DB classes.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


def _is_postgres_url(value: str | None) -> bool:
    return bool(value and value.startswith(("postgres://", "postgresql://")))


class AppDB:
    def __init__(self, sqlite_path: str | Path, database_url: str | None = None):
        self.database_url = database_url if database_url is not None else os.getenv("DATABASE_URL")
        self.is_postgres = _is_postgres_url(self.database_url)
        self.sqlite_path = Path(sqlite_path)
        if not self.is_postgres:
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[Any]:
        if self.is_postgres:
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError as exc:  # pragma: no cover - only hit in misconfigured prod
                raise RuntimeError(
                    "DATABASE_URL points to PostgreSQL, but psycopg is not installed."
                ) from exc

            conn = psycopg.connect(self.database_url, row_factory=dict_row)
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()
            return

        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def sql(self, query: str) -> str:
        """Convert simple sqlite-style parameter placeholders to PostgreSQL."""
        return query.replace("?", "%s") if self.is_postgres else query

    def bool_value(self, value: bool) -> bool | int:
        return value if self.is_postgres else int(value)

    def serialize_row(self, row: Any) -> dict:
        return dict(row)

    def table_columns(self, conn: Any, table_name: str) -> set[str]:
        if self.is_postgres:
            rows = conn.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                """,
                (table_name,),
            ).fetchall()
            return {row["column_name"] for row in rows}

        return {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}


def id_column_sql(db: AppDB) -> str:
    return "SERIAL PRIMARY KEY" if db.is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
