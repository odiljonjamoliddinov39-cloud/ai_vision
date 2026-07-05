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

    def record_movement(
        self,
        product_name: str,
        direction: str,
        camera_id: str,
        tracking_id: int,
        confidence: float,
        screenshot_path: str | None = None,
        quantity: int = 1,
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
                    product_name, direction, quantity, camera_id, tracking_id, confidence, screenshot_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product_name,
                    direction,
                    quantity,
                    camera_id,
                    tracking_id,
                    confidence,
                    screenshot_path,
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
