"""
database/tracking_db.py

SQLite persistence for per-object tracking (check-in / check-out).

This is the Phase 3 counterpart to database/event_log.py: where the flat
event log records "a person was seen at 14:21", this module records
"track #17 (person) entered Camera 2 at 14:21 and left at 14:26 after
5m12s" — i.e. it turns raw per-frame detections (with persistent track
IDs from tracking/tracker.py) into occupancy sessions.

Schema
------
occupancy_events:
    id               INTEGER PRIMARY KEY
    track_id         INTEGER   -- the tracker-assigned ID (ByteTrack)
    camera_name      TEXT
    class_name       TEXT
    event_type       TEXT      -- 'check_in' | 'check_out'
    timestamp        TEXT      -- ISO 8601, local time
    duration_seconds REAL      -- only set on check_out rows

No ORM/SQLAlchemy dependency is needed: sqlite3 is in the Python
standard library, which keeps Phase 1's "no extra deps" requirements
mostly intact while giving us real persistence and queryability
(unlike the flat text log).
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


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
                CREATE TABLE IF NOT EXISTS occupancy_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_id INTEGER NOT NULL,
                    camera_name TEXT NOT NULL,
                    class_name TEXT NOT NULL,
                    event_type TEXT NOT NULL CHECK (event_type IN ('check_in', 'check_out')),
                    timestamp TEXT NOT NULL,
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
                """
                CREATE TABLE IF NOT EXISTS zone_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    zone_name TEXT NOT NULL,
                    camera_name TEXT NOT NULL,
                    track_id INTEGER NOT NULL,
                    class_name TEXT NOT NULL,
                    event_type TEXT NOT NULL
                        CHECK (event_type IN ('item_in', 'item_out', 'person_in', 'person_out')),
                    suspicious INTEGER NOT NULL DEFAULT 0,
                    reasons TEXT,          -- comma-separated rule names, e.g. 'after_hours,unattended'
                    persons_in_zone INTEGER NOT NULL DEFAULT 0,
                    timestamp TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_zone_events_ts
                ON zone_events (timestamp)
                """
            )

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def record_check_in(
        self,
        track_id: int,
        camera_name: str,
        class_name: str,
        timestamp: str | None = None,
    ) -> OccupancyEvent:
        ts = timestamp or _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO occupancy_events
                    (track_id, camera_name, class_name, event_type, timestamp)
                VALUES (?, ?, ?, 'check_in', ?)
                """,
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

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT timestamp FROM occupancy_events
                WHERE track_id = ? AND camera_name = ? AND event_type = 'check_in'
                ORDER BY id DESC LIMIT 1
                """,
                (track_id, camera_name),
            ).fetchone()

            if row is not None:
                try:
                    check_in_time = datetime.fromisoformat(row["timestamp"])
                    duration = (datetime.fromisoformat(ts) - check_in_time).total_seconds()
                except ValueError:
                    duration = None

            conn.execute(
                """
                INSERT INTO occupancy_events
                    (track_id, camera_name, class_name, event_type, timestamp, duration_seconds)
                VALUES (?, ?, ?, 'check_out', ?, ?)
                """,
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
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO zone_events
                    (zone_name, camera_name, track_id, class_name, event_type,
                     suspicious, reasons, persons_in_zone, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    zone_name,
                    camera_name,
                    track_id,
                    class_name,
                    event_type,
                    1 if suspicious else 0,
                    ",".join(reasons) if reasons else None,
                    persons_in_zone,
                    ts,
                ),
            )

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def current_occupancy(self, camera_name: str | None = None) -> list[dict]:
        """
        Returns objects that are currently "checked in": their most recent
        event (per track_id + camera) is a check_in with no later check_out.
        """
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

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
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
        params = params + (limit,)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
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
            clauses.append("suspicious = 1")
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY id DESC LIMIT ?"
        params += (limit,)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        events = [dict(row) for row in rows]
        for event in events:
            event["suspicious"] = bool(event["suspicious"])
            event["reasons"] = event["reasons"].split(",") if event["reasons"] else []
        return events

    def zone_event_totals(self) -> dict[str, int]:
        """Lifetime totals: items in, items out, suspicious removals."""
        with self._connect() as conn:
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
                if row["event_type"] == "item_out" and row["suspicious"]:
                    totals["suspicious"] += row["n"]
        return totals
