"""Block and per-camera zone configuration persistence."""
from __future__ import annotations
import json
from database.db import AppDB, id_column_sql


class VisionConfigDB:
    def __init__(self, db_path="database/vision.db"):
        self.db = AppDB(db_path)
        self._init_schema()

    def _init_schema(self):
        with self.db.connect() as conn:
            conn.execute(f"CREATE TABLE IF NOT EXISTS blocks (id {id_column_sql(self.db)}, name TEXT NOT NULL UNIQUE, description TEXT)")
            conn.execute(f"""CREATE TABLE IF NOT EXISTS camera_settings (
                id {id_column_sql(self.db)}, camera_id TEXT NOT NULL UNIQUE,
                block_id INTEGER, confidence REAL NOT NULL DEFAULT .35,
                minimum_track_age INTEGER NOT NULL DEFAULT 4, direction INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(block_id) REFERENCES blocks(id))""")
            conn.execute(f"""CREATE TABLE IF NOT EXISTS zones (
                id {id_column_sql(self.db)}, camera_id TEXT NOT NULL, zone_type TEXT NOT NULL,
                points TEXT NOT NULL, UNIQUE(camera_id, zone_type))""")

    def create_block(self, name, description=None):
        with self.db.connect() as conn:
            if self.db.is_postgres:
                row = conn.execute("INSERT INTO blocks(name,description) VALUES(%s,%s) RETURNING id", (name, description)).fetchone()
                return {"id": row["id"], "name": name, "description": description}
            cursor = conn.execute("INSERT INTO blocks(name,description) VALUES(?,?)", (name, description))
            return {"id": cursor.lastrowid, "name": name, "description": description}

    def list_blocks(self):
        with self.db.connect() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM blocks ORDER BY name").fetchall()]

    def save_camera_rules(self, camera_id, *, block_id, confidence, minimum_track_age, direction, zones):
        if direction not in (-1, 1):
            raise ValueError("direction must be -1 or 1")
        with self.db.connect() as conn:
            existing = conn.execute(self.db.sql("SELECT id FROM camera_settings WHERE camera_id=?"), (camera_id,)).fetchone()
            if existing:
                conn.execute(self.db.sql("UPDATE camera_settings SET block_id=?,confidence=?,minimum_track_age=?,direction=? WHERE camera_id=?"),
                             (block_id, confidence, minimum_track_age, direction, camera_id))
            else:
                conn.execute(self.db.sql("INSERT INTO camera_settings(camera_id,block_id,confidence,minimum_track_age,direction) VALUES(?,?,?,?,?)"),
                             (camera_id, block_id, confidence, minimum_track_age, direction))
            for zone_type, points in zones.items():
                if zone_type not in {"counting_zone", "ignore_zone", "entry_line", "exit_line"}:
                    raise ValueError(f"unsupported zone type: {zone_type}")
                prior = conn.execute(self.db.sql("SELECT id FROM zones WHERE camera_id=? AND zone_type=?"), (camera_id, zone_type)).fetchone()
                payload = json.dumps(points)
                if prior:
                    conn.execute(self.db.sql("UPDATE zones SET points=? WHERE camera_id=? AND zone_type=?"), (payload, camera_id, zone_type))
                else:
                    conn.execute(self.db.sql("INSERT INTO zones(camera_id,zone_type,points) VALUES(?,?,?)"), (camera_id, zone_type, payload))

    def get_camera_rules(self, camera_id):
        with self.db.connect() as conn:
            settings = conn.execute(self.db.sql("SELECT * FROM camera_settings WHERE camera_id=?"), (camera_id,)).fetchone()
            zones = conn.execute(self.db.sql("SELECT zone_type,points FROM zones WHERE camera_id=?"), (camera_id,)).fetchall()
        return {"settings": dict(settings) if settings else None,
                "zones": {row["zone_type"]: json.loads(row["points"]) for row in zones}}
