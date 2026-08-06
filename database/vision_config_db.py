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
            rows = conn.execute(
                """SELECT b.*, COUNT(cs.id) AS camera_count
                   FROM blocks b LEFT JOIN camera_settings cs ON cs.block_id = b.id
                   GROUP BY b.id, b.name, b.description ORDER BY b.name"""
            ).fetchall()
            return [dict(row) for row in rows]

    def update_block(self, block_id, *, name, description=None):
        with self.db.connect() as conn:
            cursor = conn.execute(
                self.db.sql("UPDATE blocks SET name=?,description=? WHERE id=?"),
                (name, description, block_id),
            )
            if cursor.rowcount == 0:
                return None
        return next((row for row in self.list_blocks() if int(row["id"]) == int(block_id)), None)

    def delete_block(self, block_id):
        with self.db.connect() as conn:
            conn.execute(self.db.sql("UPDATE camera_settings SET block_id=NULL WHERE block_id=?"), (block_id,))
            cursor = conn.execute(self.db.sql("DELETE FROM blocks WHERE id=?"), (block_id,))
            return cursor.rowcount > 0

    def get_camera_settings_map(self, camera_ids=None):
        """Return persisted operator configuration keyed by camera id."""
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT cs.*, b.name AS block_name, b.description AS block_description
                   FROM camera_settings cs
                   LEFT JOIN blocks b ON b.id = cs.block_id
                   ORDER BY cs.camera_id"""
            ).fetchall()
        result = {str(row["camera_id"]): dict(row) for row in rows}
        if camera_ids is None:
            return result
        return {str(camera_id): result.get(str(camera_id)) for camera_id in camera_ids}

    def assign_camera_block(self, camera_id, block_id):
        """Persist a block assignment without overwriting that camera's rules."""
        with self.db.connect() as conn:
            if block_id is not None:
                block = conn.execute(self.db.sql("SELECT id FROM blocks WHERE id=?"), (block_id,)).fetchone()
                if not block:
                    raise ValueError("block does not exist")
            existing = conn.execute(self.db.sql("SELECT id FROM camera_settings WHERE camera_id=?"), (str(camera_id),)).fetchone()
            if existing:
                conn.execute(self.db.sql("UPDATE camera_settings SET block_id=? WHERE camera_id=?"), (block_id, str(camera_id)))
            else:
                conn.execute(self.db.sql("INSERT INTO camera_settings(camera_id,block_id) VALUES(?,?)"), (str(camera_id), block_id))
        return self.get_camera_settings_map([camera_id])[str(camera_id)]

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
