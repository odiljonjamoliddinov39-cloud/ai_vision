"""
SQLite stock ledger for warehouse IN/OUT counting.

This database is separate from the existing tracking occupancy database:
occupancy answers "what is visible/present?", while this ledger answers
"what crossed the warehouse line and how did stock change?"
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path


class WarehouseDB:
    def __init__(self, db_path: str = "database/warehouse.db"):
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
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    category TEXT,
                    current_stock INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS movements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_name TEXT NOT NULL,
                    direction TEXT NOT NULL CHECK (direction IN ('IN', 'OUT')),
                    quantity INTEGER DEFAULT 1,
                    camera_id TEXT,
                    tracking_id INTEGER,
                    confidence REAL,
                    screenshot_path TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self._ensure_movement_columns(conn)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS unknown_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tracking_id INTEGER,
                    confidence REAL,
                    screenshot_path TEXT,
                    camera_id TEXT,
                    status TEXT DEFAULT 'NEEDS_REVIEW',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    @staticmethod
    def _ensure_movement_columns(conn) -> None:
        existing = {
            row["name"] for row in conn.execute("PRAGMA table_info(movements)").fetchall()
        }
        columns = {
            "object_type": "TEXT",
            "estimated_width_m": "REAL",
            "estimated_height_m": "REAL",
            "estimated_depth_m": "REAL",
            "estimated_distance_m": "REAL",
            "quantity_grid": "TEXT",
            "measurement_method": "TEXT",
        }
        for name, sql_type in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE movements ADD COLUMN {name} {sql_type}")

    def record_movement(
        self,
        product_name: str,
        direction: str,
        camera_id: str,
        tracking_id: int,
        confidence: float,
        screenshot_path: str | None = None,
        quantity: int = 1,
        object_type: str | None = None,
        dimensions_m: tuple[float, float, float] | None = None,
        distance_m: float | None = None,
        quantity_grid: tuple[int, int, int] | None = None,
        measurement_method: str | None = None,
    ) -> int:
        if direction not in {"IN", "OUT"}:
            raise ValueError("direction must be IN or OUT")

        delta = quantity if direction == "IN" else -quantity
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO products (name, current_stock) VALUES (?, 0)",
                (product_name,),
            )
            conn.execute(
                "UPDATE products SET current_stock = current_stock + ? WHERE name = ?",
                (delta, product_name),
            )
            conn.execute(
                """
                INSERT INTO movements (
                    product_name,
                    direction,
                    quantity,
                    camera_id,
                    tracking_id,
                    confidence,
                    screenshot_path,
                    object_type,
                    estimated_width_m,
                    estimated_height_m,
                    estimated_depth_m,
                    estimated_distance_m,
                    quantity_grid,
                    measurement_method
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product_name,
                    direction,
                    quantity,
                    camera_id,
                    tracking_id,
                    confidence,
                    screenshot_path,
                    object_type,
                    dimensions_m[0] if dimensions_m else None,
                    dimensions_m[1] if dimensions_m else None,
                    dimensions_m[2] if dimensions_m else None,
                    distance_m,
                    "x".join(str(value) for value in quantity_grid)
                    if quantity_grid
                    else None,
                    measurement_method,
                ),
            )

        return self.get_stock(product_name)

    def record_unknown_item(
        self,
        tracking_id: int,
        confidence: float,
        screenshot_path: str | None,
        camera_id: str,
        status: str = "NEEDS_REVIEW",
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO unknown_items (tracking_id, confidence, screenshot_path, camera_id, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (tracking_id, confidence, screenshot_path, camera_id, status),
            )

    def get_stock(self, product_name: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT current_stock FROM products WHERE name = ?",
                (product_name,),
            ).fetchone()
        return int(row["current_stock"]) if row else 0

    def get_all_stock(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT name, category, current_stock, created_at FROM products ORDER BY name"
            ).fetchall()
        return [dict(row) for row in rows]

    def recent_movements(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    id,
                    product_name,
                    direction,
                    quantity,
                    camera_id,
                    tracking_id,
                    confidence,
                    screenshot_path,
                    object_type,
                    estimated_width_m,
                    estimated_height_m,
                    estimated_depth_m,
                    estimated_distance_m,
                    quantity_grid,
                    measurement_method,
                    created_at
                FROM movements
                ORDER BY id DESC
                LIMIT ?
                """,
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def movement_counts(self) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT direction, SUM(quantity) AS total FROM movements GROUP BY direction"
            ).fetchall()
        return {row["direction"]: int(row["total"] or 0) for row in rows}
