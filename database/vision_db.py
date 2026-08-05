"""Persistent live-pipeline history for scans, detections, events, and counts."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from database.db import AppDB, id_column_sql


class VisionDB:
    def __init__(self, db_path: str = "database/vision.db"):
        self.db = AppDB(db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        timestamp = "TIMESTAMPTZ" if self.db.is_postgres else "TEXT"
        with self.db.connect() as conn:
            conn.execute(f"""CREATE TABLE IF NOT EXISTS scan_runs (
                id {id_column_sql(self.db)}, stream_id TEXT NOT NULL,
                camera_id TEXT NOT NULL, block_id TEXT, status TEXT NOT NULL,
                started_at {timestamp} NOT NULL, completed_at {timestamp},
                frames INTEGER NOT NULL DEFAULT 0,
                detections INTEGER NOT NULL DEFAULT 0, error_code TEXT)""")
            conn.execute(f"""CREATE TABLE IF NOT EXISTS detections (
                id {id_column_sql(self.db)}, scan_run_id INTEGER NOT NULL,
                camera_id TEXT NOT NULL, stream_id TEXT NOT NULL,
                frame_uuid TEXT NOT NULL, frame_timestamp {timestamp} NOT NULL,
                detection_timestamp {timestamp} NOT NULL, track_id INTEGER,
                class_id INTEGER NOT NULL, confidence REAL NOT NULL, bbox TEXT NOT NULL,
                pipeline_version TEXT NOT NULL, detector_version TEXT NOT NULL,
                recognition_source TEXT NOT NULL, processing_latency_ms REAL NOT NULL,
                FOREIGN KEY(scan_run_id) REFERENCES scan_runs(id))""")
            conn.execute(f"""CREATE TABLE IF NOT EXISTS events (
                id {id_column_sql(self.db)}, scan_run_id INTEGER NOT NULL,
                detection_id INTEGER, event_type TEXT NOT NULL, camera_id TEXT NOT NULL,
                stream_id TEXT NOT NULL, frame_uuid TEXT NOT NULL,
                track_id INTEGER, payload TEXT NOT NULL, created_at {timestamp} NOT NULL,
                FOREIGN KEY(scan_run_id) REFERENCES scan_runs(id))""")
            conn.execute(f"""CREATE TABLE IF NOT EXISTS counts (
                id {id_column_sql(self.db)}, event_id INTEGER NOT NULL UNIQUE,
                block_id TEXT, camera_id TEXT NOT NULL, class_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL, counted_at {timestamp} NOT NULL,
                FOREIGN KEY(event_id) REFERENCES events(id))""")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_detection_frame_track ON detections(camera_id, frame_uuid, track_id)")

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def start_scan(self, stream_id: str, camera_id: str, block_id: str | None = None) -> int:
        with self.db.connect() as conn:
            sql = "INSERT INTO scan_runs(stream_id,camera_id,block_id,status,started_at) VALUES(?,?,?,?,?)"
            values = (stream_id, camera_id, block_id, "running", self.now())
            if self.db.is_postgres:
                return int(conn.execute(self.db.sql(sql) + " RETURNING id", values).fetchone()["id"])
            return int(conn.execute(sql, values).lastrowid)

    def record_detection(self, scan_run_id: int, detection: dict) -> int:
        required = {"camera_id", "stream_id", "frame_uuid", "frame_timestamp", "detection_timestamp",
                    "class_id", "confidence", "bbox", "pipeline_version", "detector_version",
                    "recognition_source", "processing_latency_ms"}
        missing = required - detection.keys()
        if missing:
            raise ValueError(f"missing detection trace fields: {sorted(missing)}")
        columns = (*required, "track_id")
        values = [json.dumps(detection[name]) if name == "bbox" else detection.get(name) for name in columns]
        placeholders = ",".join("?" for _ in columns)
        with self.db.connect() as conn:
            sql = f"INSERT INTO detections(scan_run_id,{','.join(columns)}) VALUES(?,{placeholders})"
            params = (scan_run_id, *values)
            if self.db.is_postgres:
                return int(conn.execute(self.db.sql(sql) + " RETURNING id", params).fetchone()["id"])
            return int(conn.execute(sql, params).lastrowid)

    def record_count(self, scan_run_id: int, detection_id: int, event: dict, block_id: str | None) -> int:
        with self.db.connect() as conn:
            created_at = self.now()
            event_sql = "INSERT INTO events(scan_run_id,detection_id,event_type,camera_id,stream_id,frame_uuid,track_id,payload,created_at) VALUES(?,?,?,?,?,?,?,?,?)"
            params = (scan_run_id, detection_id, "object_counted", event["camera_id"], event["stream_id"], event["frame_uuid"], event["track_id"], json.dumps(event), created_at)
            if self.db.is_postgres:
                event_id = int(conn.execute(self.db.sql(event_sql) + " RETURNING id", params).fetchone()["id"])
            else:
                event_id = int(conn.execute(event_sql, params).lastrowid)
            conn.execute(self.db.sql("INSERT INTO counts(event_id,block_id,camera_id,class_id,quantity,counted_at) VALUES(?,?,?,?,?,?)"),
                         (event_id, block_id, event["camera_id"], event["class_id"], 1, created_at))
            return event_id

    def finish_scan(self, scan_run_id: int, *, frames: int, detections: int, status: str = "completed", error_code: str | None = None) -> None:
        with self.db.connect() as conn:
            conn.execute(self.db.sql("UPDATE scan_runs SET status=?,completed_at=?,frames=?,detections=?,error_code=? WHERE id=?"),
                         (status, self.now(), frames, detections, error_code, scan_run_id))

    def list_scans(self, limit: int = 100, block_id: str | None = None) -> list[dict]:
        query = "SELECT * FROM scan_runs"
        params = []
        if block_id:
            query += " WHERE block_id = ?"
            params.append(block_id)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(max(1, min(limit, 500)))
        with self.db.connect() as conn:
            return [dict(row) for row in conn.execute(self.db.sql(query), tuple(params)).fetchall()]

    def list_events(self, limit: int = 100, camera_id: str | None = None) -> list[dict]:
        query = "SELECT * FROM events"
        params = []
        if camera_id:
            query += " WHERE camera_id = ?"
            params.append(camera_id)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(max(1, min(limit, 500)))
        with self.db.connect() as conn:
            rows = [dict(row) for row in conn.execute(self.db.sql(query), tuple(params)).fetchall()]
        for row in rows:
            row["payload"] = json.loads(row["payload"])
        return rows

    def count_summary(self, block_id: str | None = None, camera_id: str | None = None) -> list[dict]:
        clauses, params = [], []
        if block_id:
            clauses.append("block_id = ?"); params.append(block_id)
        if camera_id:
            clauses.append("camera_id = ?"); params.append(camera_id)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        query = "SELECT block_id,camera_id,class_id,SUM(quantity) AS quantity FROM counts" + where + " GROUP BY block_id,camera_id,class_id"
        with self.db.connect() as conn:
            return [dict(row) for row in conn.execute(self.db.sql(query), tuple(params)).fetchall()]
