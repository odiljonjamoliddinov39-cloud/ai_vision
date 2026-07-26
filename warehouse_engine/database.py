from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from warehouse_engine.events import WarehouseEvent


class EngineDatabase:
    def __init__(self, path: str = "database/warehouse_engine.db"):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init(self) -> None:
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS warehouse_objects (
                    object_id TEXT PRIMARY KEY, product_name TEXT, class_name TEXT,
                    current_zone TEXT, entry_time TEXT, exit_time TEXT,
                    last_camera TEXT, current_status TEXT, confidence REAL,
                    last_seen_at TEXT, metadata TEXT
                );
                CREATE TABLE IF NOT EXISTS warehouse_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT,
                    object_id TEXT, camera_id TEXT, timestamp TEXT, zone TEXT,
                    previous_zone TEXT, product_name TEXT, confidence REAL,
                    inventory_delta INTEGER, details TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_engine_events_time
                    ON warehouse_events(timestamp DESC);
                """
            )

    def upsert_object(self, payload: dict) -> None:
        with self.connect() as db:
            db.execute(
                """
                INSERT INTO warehouse_objects (
                    object_id, product_name, class_name, current_zone, entry_time,
                    exit_time, last_camera, current_status, confidence,
                    last_seen_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(object_id) DO UPDATE SET
                    product_name=excluded.product_name, class_name=excluded.class_name,
                    current_zone=excluded.current_zone, exit_time=excluded.exit_time,
                    last_camera=excluded.last_camera,
                    current_status=excluded.current_status,
                    confidence=excluded.confidence,
                    last_seen_at=excluded.last_seen_at, metadata=excluded.metadata
                """,
                (
                    payload["object_id"], payload["product_name"], payload["class_name"],
                    payload["current_zone"], payload["entry_time"], payload.get("exit_time"),
                    payload["last_camera"], payload["current_status"],
                    payload["confidence"], payload["last_seen_at"],
                    json.dumps(payload.get("metadata") or {}),
                ),
            )

    def add_event(self, event: WarehouseEvent) -> None:
        with self.connect() as db:
            db.execute(
                """
                INSERT INTO warehouse_events (
                    event_type, object_id, camera_id, timestamp, zone,
                    previous_zone, product_name, confidence, inventory_delta, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_type, event.object_id, event.camera_id, event.timestamp,
                    event.zone, event.previous_zone, event.product_name,
                    event.confidence, event.inventory_delta,
                    json.dumps(event.details or {}),
                ),
            )

    def objects(self, limit: int = 500) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM warehouse_objects ORDER BY last_seen_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def events(self, limit: int = 500) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM warehouse_events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]
