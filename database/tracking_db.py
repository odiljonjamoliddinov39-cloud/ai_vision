"""
database/tracking_db.py

Persistence for per-object tracking (check-in / check-out) and zone events.

Uses PostgreSQL when DATABASE_URL is set, otherwise SQLite for local
development and tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from database.db import AppDB, id_column_sql


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class OccupancyEvent:
    track_id: int
    camera_name: str
    class_name: str
    event_type: str  # "check_in" | "check_out"
    timestamp: str
    duration_seconds: float | None = None


class TrackingDB:
    def __init__(self, db_path: str = "database/tracking.db"):
        self.db_path = db_path
        self.db = AppDB(db_path)
        self._init_schema()

    def _sql(self, query: str) -> str:
        return self.db.sql(query)

    def _init_schema(self) -> None:
        timestamp_type = "TIMESTAMPTZ" if self.db.is_postgres else "TEXT"
        suspicious_type = "BOOLEAN" if self.db.is_postgres else "INTEGER"
        with self.db.connect() as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS occupancy_events (
                    id {id_column_sql(self.db)},
                    track_id INTEGER NOT NULL,
                    camera_name TEXT NOT NULL,
                    class_name TEXT NOT NULL,
                    event_type TEXT NOT NULL CHECK (event_type IN ('check_in', 'check_out')),
                    timestamp {timestamp_type} NOT NULL,
                    duration_seconds REAL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_occupancy_track
                ON occupancy_events (track_id, camera_name)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_occupancy_timestamp
                ON occupancy_events (timestamp)
                """
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS zone_events (
                    id {id_column_sql(self.db)},
                    zone_name TEXT NOT NULL,
                    camera_name TEXT NOT NULL,
                    track_id INTEGER NOT NULL,
                    class_name TEXT NOT NULL,
                    event_type TEXT NOT NULL
                        CHECK (event_type IN ('item_in', 'item_out', 'person_in', 'person_out')),
                    suspicious {suspicious_type} NOT NULL DEFAULT {'FALSE' if self.db.is_postgres else 0},
                    reasons TEXT,
                    persons_in_zone INTEGER NOT NULL DEFAULT 0,
                    timestamp {timestamp_type} NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_zone_events_ts
                ON zone_events (timestamp)
                """
            )

    def record_check_in(
        self,
        track_id: int,
        camera_name: str,
        class_name: str,
        timestamp: str | None = None,
    ) -> OccupancyEvent:
        ts = timestamp or _now_iso()
        with self.db.connect() as conn:
            conn.execute(
                self._sql(
                    """
                    INSERT INTO occupancy_events
                        (track_id, camera_name, class_name, event_type, timestamp)
                    VALUES (?, ?, ?, 'check_in', ?)
                    """
                ),
                (track_id, camera_name, class_name, ts),
            )
        return OccupancyEvent(track_id, camera_name, class_name, "check_in", ts)

    def record_check_out(
        self,
        track_id: int,
        camera_name: str,
        class_name: str,
        timestamp: str | None = None,
    ) -> OccupancyEvent:
        ts = timestamp or _now_iso()
        duration: float | None = None

        with self.db.connect() as conn:
            row = conn.execute(
                self._sql(
                    """
                    SELECT timestamp FROM occupancy_events
                    WHERE track_id = ? AND camera_name = ? AND event_type = 'check_in'
                    ORDER BY id DESC LIMIT 1
                    """
                ),
                (track_id, camera_name),
            ).fetchone()

            if row is not None:
                try:
                    check_in_time = row["timestamp"]
                    if not isinstance(check_in_time, datetime):
                        check_in_time = datetime.fromisoformat(str(check_in_time))
                    check_out_time = datetime.fromisoformat(ts)
                    duration = (check_out_time - check_in_time.replace(tzinfo=None)).total_seconds()
                except (TypeError, ValueError):
                    duration = None

            conn.execute(
                self._sql(
                    """
                    INSERT INTO occupancy_events
                        (track_id, camera_name, class_name, event_type, timestamp, duration_seconds)
                    VALUES (?, ?, ?, 'check_out', ?, ?)
                    """
                ),
                (track_id, camera_name, class_name, ts, duration),
            )

        return OccupancyEvent(track_id, camera_name, class_name, "check_out", ts, duration)

    def record_zone_event(
        self,
        zone_name: str,
        camera_name: str,
        track_id: int,
        class_name: str,
        event_type: str,
        suspicious: bool = False,
        reasons: list[str] | None = None,
        persons_in_zone: int = 0,
        timestamp: str | None = None,
    ) -> None:
        ts = timestamp or _now_iso()
        with self.db.connect() as conn:
            conn.execute(
                self._sql(
                    """
                    INSERT INTO zone_events
                        (zone_name, camera_name, track_id, class_name, event_type,
                         suspicious, reasons, persons_in_zone, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                ),
                (
                    zone_name,
                    camera_name,
                    track_id,
                    class_name,
                    event_type,
                    self.db.bool_value(suspicious),
                    ",".join(reasons) if reasons else None,
                    persons_in_zone,
                    ts,
                ),
            )

    def current_occupancy(self, camera_name: str | None = None) -> list[dict]:
        query = """
            SELECT e.track_id, e.camera_name, e.class_name, e.timestamp AS since
            FROM occupancy_events e
            INNER JOIN (
                SELECT track_id, camera_name, MAX(id) AS max_id
                FROM occupancy_events
                GROUP BY track_id, camera_name
            ) latest
            ON e.id = latest.max_id
            WHERE e.event_type = 'check_in'
        """
        params: tuple = ()
        if camera_name:
            query += " AND e.camera_name = ?"
            params = (camera_name,)
        query += " ORDER BY e.timestamp DESC"

        with self.db.connect() as conn:
            rows = conn.execute(self._sql(query), params).fetchall()
        return [dict(row) for row in rows]

    def occupancy_counts(self, camera_name: str | None = None) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in self.current_occupancy(camera_name):
            counts[row["class_name"]] = counts.get(row["class_name"], 0) + 1
        return counts

    def recent_events(self, limit: int = 50, camera_name: str | None = None) -> list[dict]:
        query = "SELECT * FROM occupancy_events"
        params: tuple = ()
        if camera_name:
            query += " WHERE camera_name = ?"
            params = (camera_name,)
        query += " ORDER BY id DESC LIMIT ?"
        params = params + (max(1, min(limit, 500)),)

        with self.db.connect() as conn:
            rows = conn.execute(self._sql(query), params).fetchall()
        return [dict(row) for row in rows]

    def recent_zone_events(
        self,
        limit: int = 50,
        camera_name: str | None = None,
        suspicious_only: bool = False,
    ) -> list[dict]:
        query = "SELECT * FROM zone_events"
        clauses = []
        params: tuple = ()
        if camera_name:
            clauses.append("camera_name = ?")
            params += (camera_name,)
        if suspicious_only:
            clauses.append("suspicious = ?")
            params += (self.db.bool_value(True),)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY id DESC LIMIT ?"
        params += (max(1, min(limit, 500)),)

        with self.db.connect() as conn:
            rows = conn.execute(self._sql(query), params).fetchall()
        events = [dict(row) for row in rows]
        for event in events:
            event["suspicious"] = bool(event["suspicious"])
            event["reasons"] = event["reasons"].split(",") if event["reasons"] else []
        return events

    def zone_event_totals(self) -> dict[str, int]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT event_type, suspicious, COUNT(*) AS n
                FROM zone_events GROUP BY event_type, suspicious
                """
            ).fetchall()
        totals = {"item_in": 0, "item_out": 0, "suspicious": 0}
        for row in rows:
            if row["event_type"] in ("item_in", "item_out"):
                totals[row["event_type"]] += row["n"]
                if row["event_type"] == "item_out" and bool(row["suspicious"]):
                    totals["suspicious"] += row["n"]
        return totals
