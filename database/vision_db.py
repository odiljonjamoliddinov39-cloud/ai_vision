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
            conn.execute(f"""CREATE TABLE IF NOT EXISTS recognitions (
                id {id_column_sql(self.db)}, scan_run_id INTEGER NOT NULL,
                detection_id INTEGER NOT NULL, track_id INTEGER,
                detector_class TEXT NOT NULL, identity TEXT NOT NULL,
                confidence REAL NOT NULL, source TEXT NOT NULL,
                known INTEGER NOT NULL, created_at {timestamp} NOT NULL,
                FOREIGN KEY(scan_run_id) REFERENCES scan_runs(id),
                FOREIGN KEY(detection_id) REFERENCES detections(id))""")
            conn.execute(f"""CREATE TABLE IF NOT EXISTS rule_decisions (
                id {id_column_sql(self.db)}, scan_run_id INTEGER NOT NULL,
                detection_id INTEGER NOT NULL, track_id INTEGER,
                decision TEXT NOT NULL, reason TEXT NOT NULL,
                identity TEXT, created_at {timestamp} NOT NULL,
                FOREIGN KEY(scan_run_id) REFERENCES scan_runs(id),
                FOREIGN KEY(detection_id) REFERENCES detections(id))""")
            conn.execute(f"""CREATE TABLE IF NOT EXISTS operator_actions (
                id {id_column_sql(self.db)}, action TEXT NOT NULL,
                actor TEXT NOT NULL, payload TEXT NOT NULL,
                created_at {timestamp} NOT NULL)""")
            conn.execute(f"""CREATE TABLE IF NOT EXISTS inventory_results (
                id {id_column_sql(self.db)}, camera_id TEXT NOT NULL,
                block_id TEXT, frame_uuid TEXT NOT NULL, target_product TEXT NOT NULL,
                requested_model TEXT, loaded_model TEXT, detector_mode TEXT NOT NULL,
                fallback_used INTEGER NOT NULL, raw_detection_count INTEGER NOT NULL,
                accepted_detection_count INTEGER NOT NULL,
                rejected_detection_count INTEGER NOT NULL,
                final_inventory_count INTEGER NOT NULL, detections TEXT NOT NULL,
                evidence_path TEXT, created_at {timestamp} NOT NULL)""")
            conn.execute(f"""CREATE TABLE IF NOT EXISTS vision_benchmarks (
                id {id_column_sql(self.db)}, inventory_result_id INTEGER NOT NULL,
                camera_id TEXT NOT NULL, block_id TEXT, target_product TEXT NOT NULL,
                ground_truth_count INTEGER NOT NULL, predicted_count INTEGER NOT NULL,
                accuracy REAL NOT NULL, notes TEXT, created_at {timestamp} NOT NULL,
                FOREIGN KEY(inventory_result_id) REFERENCES inventory_results(id))""")
            conn.execute(f"""CREATE TABLE IF NOT EXISTS vision_datasets (
                id TEXT PRIMARY KEY, product_id TEXT NOT NULL, product_name TEXT NOT NULL,
                class_name TEXT NOT NULL, version INTEGER NOT NULL, status TEXT NOT NULL,
                archived INTEGER NOT NULL DEFAULT 0, created_at {timestamp} NOT NULL,
                updated_at {timestamp} NOT NULL)""")
            conn.execute(f"""CREATE TABLE IF NOT EXISTS vision_dataset_images (
                id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL, camera_id TEXT,
                block_id TEXT, source TEXT NOT NULL, original_path TEXT NOT NULL,
                content_hash TEXT NOT NULL, perceptual_hash TEXT NOT NULL,
                capture_timestamp {timestamp} NOT NULL, annotation_status TEXT NOT NULL,
                instance_count INTEGER NOT NULL DEFAULT 0, split TEXT,
                created_at {timestamp} NOT NULL, updated_at {timestamp} NOT NULL,
                FOREIGN KEY(dataset_id) REFERENCES vision_datasets(id))""")
            conn.execute(f"""CREATE TABLE IF NOT EXISTS vision_dataset_annotations (
                id TEXT PRIMARY KEY, image_id TEXT NOT NULL, class_name TEXT NOT NULL,
                x1 REAL NOT NULL, y1 REAL NOT NULL, x2 REAL NOT NULL, y2 REAL NOT NULL,
                provenance TEXT NOT NULL, status TEXT NOT NULL, confidence REAL,
                created_at {timestamp} NOT NULL, updated_at {timestamp} NOT NULL,
                FOREIGN KEY(image_id) REFERENCES vision_dataset_images(id))""")
            conn.execute(f"""CREATE TABLE IF NOT EXISTS vision_models (
                id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL, name TEXT NOT NULL UNIQUE,
                base_model TEXT NOT NULL, weights_path TEXT, status TEXT NOT NULL,
                training_config TEXT NOT NULL, metrics TEXT NOT NULL,
                benchmark_accuracy REAL, deployment_status TEXT NOT NULL,
                started_at {timestamp}, finished_at {timestamp}, deployed_at {timestamp},
                created_at {timestamp} NOT NULL,
                FOREIGN KEY(dataset_id) REFERENCES vision_datasets(id))""")
            conn.execute(f"""CREATE TABLE IF NOT EXISTS vision_model_deployments (
                id {id_column_sql(self.db)}, product_id TEXT NOT NULL, model_id TEXT NOT NULL,
                previous_model_id TEXT, deployed_at {timestamp} NOT NULL,
                FOREIGN KEY(model_id) REFERENCES vision_models(id))""")
            conn.execute(f"""CREATE TABLE IF NOT EXISTS vision_review_queue (
                id TEXT PRIMARY KEY, product_id TEXT NOT NULL, dataset_id TEXT,
                camera_id TEXT, image_path TEXT NOT NULL, reason TEXT NOT NULL,
                confidence REAL, status TEXT NOT NULL, payload TEXT NOT NULL,
                created_at {timestamp} NOT NULL, reviewed_at {timestamp})""")
            conn.execute(f"""CREATE TABLE IF NOT EXISTS counts (
                id {id_column_sql(self.db)}, event_id INTEGER NOT NULL UNIQUE,
                block_id TEXT, camera_id TEXT NOT NULL, class_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL, counted_at {timestamp} NOT NULL,
                FOREIGN KEY(event_id) REFERENCES events(id))""")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_detection_frame_track ON detections(camera_id, frame_uuid, track_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_dataset_images_dataset ON vision_dataset_images(dataset_id, annotation_status)")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_dataset_annotations_image ON vision_dataset_annotations(image_id, status)")

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
                         (event_id, block_id, event["camera_id"], event["class_id"],
                          int(event.get("inventory_delta", event.get("quantity", 1))), created_at))
            return event_id

    def record_recognition(self, scan_run_id: int, detection_id: int, recognition) -> int:
        values = (
            scan_run_id, detection_id, recognition.track_id,
            recognition.detector_class, recognition.identity,
            float(recognition.confidence), recognition.source,
            int(bool(recognition.known)), self.now(),
        )
        sql = """INSERT INTO recognitions(
            scan_run_id,detection_id,track_id,detector_class,identity,
            confidence,source,known,created_at) VALUES(?,?,?,?,?,?,?,?,?)"""
        with self.db.connect() as conn:
            if self.db.is_postgres:
                return int(conn.execute(self.db.sql(sql) + " RETURNING id", values).fetchone()["id"])
            return int(conn.execute(sql, values).lastrowid)

    def record_rule_decision(self, scan_run_id: int, detection_id: int, decision) -> int:
        values = (
            scan_run_id, detection_id, decision.observation.track_id,
            decision.decision, decision.reason,
            decision.observation.recognized_name, self.now(),
        )
        sql = """INSERT INTO rule_decisions(
            scan_run_id,detection_id,track_id,decision,reason,identity,created_at)
            VALUES(?,?,?,?,?,?,?)"""
        with self.db.connect() as conn:
            if self.db.is_postgres:
                return int(conn.execute(self.db.sql(sql) + " RETURNING id", values).fetchone()["id"])
            return int(conn.execute(sql, values).lastrowid)

    def record_operator_action(self, action: str, actor: str, payload: dict) -> int:
        values = (action, actor, json.dumps(payload), self.now())
        sql = "INSERT INTO operator_actions(action,actor,payload,created_at) VALUES(?,?,?,?)"
        with self.db.connect() as conn:
            if self.db.is_postgres:
                return int(conn.execute(self.db.sql(sql) + " RETURNING id", values).fetchone()["id"])
            return int(conn.execute(sql, values).lastrowid)

    def record_inventory_result(self, result: dict) -> int:
        columns = (
            "camera_id", "block_id", "frame_uuid", "target_product",
            "requested_model", "loaded_model", "detector_mode", "fallback_used",
            "raw_detection_count", "accepted_detection_count",
            "rejected_detection_count", "final_inventory_count", "detections",
            "evidence_path", "created_at",
        )
        values = tuple(
            json.dumps(result.get(name, [])) if name == "detections"
            else int(bool(result.get(name))) if name == "fallback_used"
            else result.get(name)
            for name in columns[:-1]
        ) + (self.now(),)
        sql = f"INSERT INTO inventory_results({','.join(columns)}) VALUES({','.join('?' for _ in columns)})"
        with self.db.connect() as conn:
            if self.db.is_postgres:
                return int(conn.execute(self.db.sql(sql) + " RETURNING id", values).fetchone()["id"])
            return int(conn.execute(sql, values).lastrowid)

    def record_benchmark(self, inventory_result_id: int, ground_truth_count: int,
                         notes: str | None = None) -> int:
        with self.db.connect() as conn:
            result = conn.execute(
                self.db.sql("SELECT * FROM inventory_results WHERE id=?"),
                (inventory_result_id,),
            ).fetchone()
            if result is None:
                raise ValueError("inventory result not found")
            predicted = int(result["final_inventory_count"])
            truth = int(ground_truth_count)
            accuracy = 1.0 if truth == predicted == 0 else (
                max(0.0, 1.0 - abs(predicted - truth) / truth) if truth else 0.0
            )
            values = (
                inventory_result_id, result["camera_id"], result["block_id"],
                result["target_product"], truth, predicted, accuracy, notes, self.now(),
            )
            sql = """INSERT INTO vision_benchmarks(
                inventory_result_id,camera_id,block_id,target_product,
                ground_truth_count,predicted_count,accuracy,notes,created_at)
                VALUES(?,?,?,?,?,?,?,?,?)"""
            if self.db.is_postgres:
                return int(conn.execute(self.db.sql(sql) + " RETURNING id", values).fetchone()["id"])
            return int(conn.execute(sql, values).lastrowid)

    def list_benchmarks(self, limit: int = 200) -> list[dict]:
        with self.db.connect() as conn:
            rows = conn.execute(
                self.db.sql("SELECT * FROM vision_benchmarks ORDER BY id DESC LIMIT ?"),
                (max(1, min(int(limit), 500)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def dataset_execute(self, sql: str, params: tuple = ()):
        """Execute Dataset Builder SQL through the shared VisionDB connection."""
        with self.db.connect() as conn:
            return conn.execute(self.db.sql(sql), params)

    def dataset_fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        with self.db.connect() as conn:
            row = conn.execute(self.db.sql(sql), params).fetchone()
        return dict(row) if row is not None else None

    def dataset_fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        with self.db.connect() as conn:
            rows = conn.execute(self.db.sql(sql), params).fetchall()
        return [dict(row) for row in rows]

    def record_event(self, scan_run_id: int, detection_id: int | None, event: dict) -> int:
        """Persist any rule event; count events additionally update counts."""
        created_at = str(event.get("timestamp") or self.now())
        payload = dict(event)
        with self.db.connect() as conn:
            sql = "INSERT INTO events(scan_run_id,detection_id,event_type,camera_id,stream_id,frame_uuid,track_id,payload,created_at) VALUES(?,?,?,?,?,?,?,?,?)"
            params = (scan_run_id, detection_id, event["event_type"], event["camera_id"],
                      event["stream_id"], event["frame_uuid"], event.get("track_id"),
                      json.dumps(payload), created_at)
            if self.db.is_postgres:
                return int(conn.execute(self.db.sql(sql) + " RETURNING id", params).fetchone()["id"])
            return int(conn.execute(sql, params).lastrowid)

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

    def scan_details(self, scan_run_id: int) -> dict | None:
        with self.db.connect() as conn:
            scan = conn.execute(self.db.sql("SELECT * FROM scan_runs WHERE id=?"), (scan_run_id,)).fetchone()
            if not scan:
                return None
            detections = [dict(row) for row in conn.execute(
                self.db.sql("SELECT * FROM detections WHERE scan_run_id=? ORDER BY id"), (scan_run_id,)
            ).fetchall()]
            events = [dict(row) for row in conn.execute(
                self.db.sql("SELECT * FROM events WHERE scan_run_id=? ORDER BY id"), (scan_run_id,)
            ).fetchall()]
            recognitions = [dict(row) for row in conn.execute(
                self.db.sql("SELECT * FROM recognitions WHERE scan_run_id=? ORDER BY id"), (scan_run_id,)
            ).fetchall()]
            decisions = [dict(row) for row in conn.execute(
                self.db.sql("SELECT * FROM rule_decisions WHERE scan_run_id=? ORDER BY id"), (scan_run_id,)
            ).fetchall()]
        for detection in detections:
            detection["bbox"] = json.loads(detection["bbox"])
        for event in events:
            event["payload"] = json.loads(event["payload"])
        return {"scan": dict(scan), "detections": detections, "recognitions": recognitions,
                "rule_decisions": decisions, "events": events}

    def list_events(self, limit: int = 100, camera_id: str | None = None,
                    block_id: str | None = None, class_id: int | None = None,
                    date_from: str | None = None, date_to: str | None = None) -> list[dict]:
        query = """SELECT e.*, sr.block_id, d.class_id, d.confidence, d.recognition_source
                   FROM events e
                   LEFT JOIN scan_runs sr ON sr.id=e.scan_run_id
                   LEFT JOIN detections d ON d.id=e.detection_id"""
        clauses, params = [], []
        if camera_id:
            clauses.append("e.camera_id = ?")
            params.append(camera_id)
        if block_id:
            clauses.append("sr.block_id = ?")
            params.append(block_id)
        if class_id is not None:
            clauses.append("d.class_id = ?")
            params.append(class_id)
        if date_from:
            clauses.append("e.created_at >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("e.created_at <= ?")
            params.append(date_to)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY e.id DESC LIMIT ?"
        params.append(max(1, min(limit, 500)))
        with self.db.connect() as conn:
            rows = [dict(row) for row in conn.execute(self.db.sql(query), tuple(params)).fetchall()]
        for row in rows:
            row["payload"] = json.loads(row["payload"])
        return rows

    def analytics_summary(self, block_id: str | None = None, camera_id: str | None = None) -> dict:
        clauses, params = [], []
        if block_id:
            clauses.append("block_id=?"); params.append(block_id)
        if camera_id:
            clauses.append("camera_id=?"); params.append(camera_id)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.db.connect() as conn:
            scans = conn.execute(self.db.sql(
                "SELECT COUNT(*) AS scans, COALESCE(SUM(frames),0) AS frames, COALESCE(SUM(detections),0) AS detections FROM scan_runs" + where
            ), tuple(params)).fetchone()
            counts = conn.execute(self.db.sql(
                "SELECT COALESCE(SUM(quantity),0) AS total_count, COUNT(*) AS events FROM counts" + where
            ), tuple(params)).fetchone()
        return {**dict(scans), **dict(counts)}

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
