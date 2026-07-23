"""Persistent enrolled-item catalog and scheduled recognition results."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from database.db import AppDB


class CatalogDB:
    def __init__(self, db_path: str = "database/catalog.db"):
        self.db_path = db_path
        self.db = AppDB(db_path)
        self._init_schema()

    def _sql(self, query: str) -> str:
        return self.db.sql(query)

    def _init_schema(self) -> None:
        timestamp_type = "TIMESTAMPTZ" if self.db.is_postgres else "DATETIME"
        with self.db.connect() as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS catalog_items (
                    id TEXT PRIMARY KEY,
                    scope_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    active INTEGER DEFAULT 1,
                    created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
                    updated_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(scope_id, name)
                )
                """
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS catalog_images (
                    id TEXT PRIMARY KEY,
                    item_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    url TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    width_px INTEGER,
                    height_px INTEGER,
                    created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS catalog_recognition_runs (
                    id TEXT PRIMARY KEY,
                    scope_id TEXT NOT NULL,
                    started_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
                    completed_at {timestamp_type},
                    interval_hours INTEGER DEFAULT 12,
                    camera_count INTEGER DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'running'
                )
                """
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS catalog_recognition_results (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 0,
                    confidence REAL NOT NULL DEFAULT 0,
                    width_m REAL,
                    height_m REAL,
                    depth_m REAL,
                    measurement_method TEXT,
                    created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self._ensure_results_camera_counts_column(conn)

    def _ensure_results_camera_counts_column(self, conn) -> None:
        columns = self.db.table_columns(conn, "catalog_recognition_results")
        if "camera_counts" not in columns:
            conn.execute("ALTER TABLE catalog_recognition_results ADD COLUMN camera_counts TEXT")

    def create_item(self, scope_id: str, name: str) -> dict[str, Any]:
        item_id = uuid.uuid4().hex
        with self.db.connect() as conn:
            conn.execute(
                self._sql(
                    "INSERT INTO catalog_items (id, scope_id, name, active) VALUES (?, ?, ?, 1)"
                ),
                (item_id, scope_id, name),
            )
        return self.get_item(item_id) or {"id": item_id, "scope_id": scope_id, "name": name}

    def add_image(
        self,
        item_id: str,
        filename: str,
        url: str,
        embedding: list[float],
        width_px: int,
        height_px: int,
    ) -> dict[str, Any]:
        image_id = uuid.uuid4().hex
        with self.db.connect() as conn:
            conn.execute(
                self._sql(
                    """
                    INSERT INTO catalog_images (
                        id, item_id, filename, url, embedding, width_px, height_px
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """
                ),
                (
                    image_id,
                    item_id,
                    filename,
                    url,
                    json.dumps(embedding, separators=(",", ":")),
                    width_px,
                    height_px,
                ),
            )
        return {
            "id": image_id,
            "item_id": item_id,
            "filename": filename,
            "url": url,
            "width_px": width_px,
            "height_px": height_px,
        }

    def get_item(self, item_id: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                self._sql(
                    "SELECT id, scope_id, name, active, created_at, updated_at FROM catalog_items WHERE id = ?"
                ),
                (item_id,),
            ).fetchone()
        return self._item_payload(row) if row else None

    def list_items(self, scope_id: str, active_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT id, scope_id, name, active, created_at, updated_at FROM catalog_items WHERE scope_id = ?"
        if active_only:
            query += " AND active = 1"
        query += " ORDER BY name"
        with self.db.connect() as conn:
            rows = conn.execute(self._sql(query), (scope_id,)).fetchall()
        return [self._item_payload(row) for row in rows]

    def list_scopes(self) -> list[str]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT scope_id FROM catalog_items WHERE active = 1 ORDER BY scope_id"
            ).fetchall()
        return [str(row["scope_id"]) for row in rows]

    def reference_candidates(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT i.id AS item_id, i.name, r.embedding
                FROM catalog_items i
                JOIN catalog_images r ON r.item_id = i.id
                WHERE i.active = 1
                ORDER BY i.name, r.created_at, r.id
                """
            ).fetchall()
        candidates = []
        for row in rows:
            payload = dict(row)
            try:
                payload["embedding"] = json.loads(payload.get("embedding") or "[]")
            except json.JSONDecodeError:
                payload["embedding"] = []
            candidates.append(payload)
        return candidates

    def list_images(self, item_id: str, include_embeddings: bool = False) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                self._sql(
                    """
                    SELECT id, item_id, filename, url, embedding, width_px, height_px, created_at
                    FROM catalog_images WHERE item_id = ? ORDER BY created_at, id
                    """
                ),
                (item_id,),
            ).fetchall()
        images = []
        for row in rows:
            payload = dict(row)
            raw = payload.pop("embedding", None)
            if include_embeddings:
                try:
                    payload["embedding"] = json.loads(raw or "[]")
                except json.JSONDecodeError:
                    payload["embedding"] = []
            images.append(payload)
        return images

    def delete_item(self, item_id: str) -> list[str]:
        images = self.list_images(item_id)
        with self.db.connect() as conn:
            conn.execute(self._sql("DELETE FROM catalog_images WHERE item_id = ?"), (item_id,))
            conn.execute(self._sql("DELETE FROM catalog_items WHERE id = ?"), (item_id,))
        return [str(image["filename"]) for image in images]

    def start_run(self, scope_id: str, interval_hours: int, camera_count: int) -> str:
        run_id = uuid.uuid4().hex
        with self.db.connect() as conn:
            conn.execute(
                self._sql(
                    """
                    INSERT INTO catalog_recognition_runs (
                        id, scope_id, interval_hours, camera_count, status
                    ) VALUES (?, ?, ?, ?, 'running')
                    """
                ),
                (run_id, scope_id, interval_hours, camera_count),
            )
        return run_id

    def add_result(
        self,
        run_id: str,
        item_id: str,
        item_name: str,
        quantity: int,
        confidence: float,
        dimensions_m: tuple[float, float, float] | None = None,
        measurement_method: str | None = None,
        camera_counts: list[dict[str, Any]] | None = None,
    ) -> None:
        result_id = uuid.uuid4().hex
        with self.db.connect() as conn:
            conn.execute(
                self._sql(
                    """
                    INSERT INTO catalog_recognition_results (
                        id, run_id, item_id, item_name, quantity, confidence,
                        width_m, height_m, depth_m, measurement_method, camera_counts
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                ),
                (
                    result_id,
                    run_id,
                    item_id,
                    item_name,
                    max(0, int(quantity)),
                    max(0.0, min(1.0, float(confidence))),
                    dimensions_m[0] if dimensions_m else None,
                    dimensions_m[1] if dimensions_m else None,
                    dimensions_m[2] if dimensions_m else None,
                    measurement_method,
                    json.dumps(camera_counts or [], separators=(",", ":")),
                ),
            )

    def complete_run(self, run_id: str, status: str = "completed") -> None:
        with self.db.connect() as conn:
            conn.execute(
                self._sql(
                    """
                    UPDATE catalog_recognition_runs
                    SET status = ?, completed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """
                ),
                (status, run_id),
            )

    def latest_run(self, scope_id: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                self._sql(
                    """
                    SELECT id, scope_id, started_at, completed_at, interval_hours, camera_count, status
                    FROM catalog_recognition_runs
                    WHERE scope_id = ? AND status = 'completed'
                    ORDER BY completed_at DESC, started_at DESC
                    LIMIT 1
                    """
                ),
                (scope_id,),
            ).fetchone()
        if not row:
            return None
        payload = dict(row)
        for key in ("started_at", "completed_at"):
            payload[key] = self._iso_timestamp(payload.get(key))
        return payload

    def latest_results(self, scope_id: str, detected_only: bool = False) -> list[dict[str, Any]]:
        latest = self.latest_run(scope_id)
        if not latest:
            return []
        query = """
            SELECT r.id, r.run_id, r.item_id, r.item_name, r.quantity, r.confidence,
                   r.width_m, r.height_m, r.depth_m, r.measurement_method, r.camera_counts, r.created_at
            FROM catalog_recognition_results r
            JOIN catalog_items i ON i.id = r.item_id AND i.active = 1
            WHERE r.run_id = ?
        """
        if detected_only:
            query += " AND r.quantity > 0"
        query += " ORDER BY r.quantity DESC, r.item_name"
        with self.db.connect() as conn:
            rows = conn.execute(self._sql(query), (latest["id"],)).fetchall()
        return [self._result_payload(row) for row in rows]

    def result_history(self, scope_id: str, limit: int = 200) -> list[dict[str, Any]]:
        query = """
            SELECT r.id, r.run_id, r.item_id, r.item_name, r.quantity, r.confidence,
                   r.width_m, r.height_m, r.depth_m, r.measurement_method, r.camera_counts,
                   r.created_at, run.scope_id, run.started_at, run.completed_at,
                   run.interval_hours, run.camera_count, run.status
            FROM catalog_recognition_results r
            JOIN catalog_recognition_runs run ON run.id = r.run_id
            WHERE run.scope_id = ?
            ORDER BY COALESCE(run.completed_at, run.started_at) DESC, r.quantity DESC, r.item_name
            LIMIT ?
        """
        with self.db.connect() as conn:
            rows = conn.execute(self._sql(query), (scope_id, max(1, min(int(limit), 1000)))).fetchall()
        history = []
        for row in rows:
            payload = self._result_payload(row)
            for key in ("created_at", "started_at", "completed_at"):
                payload[key] = self._iso_timestamp(payload.get(key))
            history.append(payload)
        return history

    def _item_payload(self, row) -> dict[str, Any]:
        item = dict(row)
        item["active"] = bool(item.get("active"))
        item["images"] = self.list_images(str(item["id"]))
        item["image_count"] = len(item["images"])
        return item

    @staticmethod
    def _result_payload(row) -> dict[str, Any]:
        result = dict(row)
        raw = result.get("camera_counts")
        try:
            parsed = json.loads(raw or "[]")
        except json.JSONDecodeError:
            parsed = []
        result["camera_counts"] = parsed if isinstance(parsed, list) else []
        return result

    @staticmethod
    def _iso_timestamp(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            parsed = value
        else:
            try:
                parsed = datetime.fromisoformat(str(value).replace(" ", "T"))
            except ValueError:
                return str(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
