"""
Site Register — Snapshot Manager

Manages frozen assessment snapshots in data/site_register.db.
Each snapshot captures the species list, computed metrics, and
the Codex/Pantheon version used at the time of assessment.

A site can have multiple snapshots (different survey years or projects).
Each snapshot can be frozen in either CODEX_FULL or PANTHEON_ONLY mode,
or both (two records with different analysis_mode values).

Usage:
    from Site_Register.snapshot_manager import SnapshotManager
import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

    mgr = SnapshotManager()
    mgr.freeze_snapshot(site_name, project_name, survey_year,
                        species_data, metrics, mode="codex_full")
    snapshots = mgr.get_snapshots(site_name)
    snapshot = mgr.get_snapshot(snapshot_id)
"""

import sqlite3
import os
from dataclasses import dataclass, field
from datetime import datetime
import paths


DB_PATH = paths.EXAMEN_DB


SCHEMA = """
    CREATE TABLE IF NOT EXISTS site_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        site_name TEXT NOT NULL,
        project_name TEXT DEFAULT '',
        client TEXT DEFAULT '',
        survey_year INTEGER NOT NULL,
        first_visit TEXT,
        last_visit TEXT,
        visit_count INTEGER DEFAULT 0,

        -- Frozen metrics
        species_count INTEGER DEFAULT 0,
        key_species_count INTEGER DEFAULT 0,
        key_species_pct REAL DEFAULT 0.0,
        rare_count INTEGER DEFAULT 0,
        scarce_count INTEGER DEFAULT 0,
        priority_count INTEGER DEFAULT 0,
        sqi REAL DEFAULT 0.0,
        sqi_reliable INTEGER DEFAULT 1,
        scoring_species INTEGER DEFAULT 0,

        -- Provenance
        analysis_mode TEXT NOT NULL DEFAULT 'codex_full',
        codex_version TEXT DEFAULT '',
        pantheon_version TEXT DEFAULT '',
        frozen_date TEXT NOT NULL,
        notes TEXT DEFAULT '',

        UNIQUE(site_name, project_name, survey_year, analysis_mode)
    );

    CREATE TABLE IF NOT EXISTS snapshot_species (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER NOT NULL REFERENCES site_snapshots(id) ON DELETE CASCADE,
        tvk TEXT NOT NULL,
        species_name TEXT NOT NULL,
        short_status TEXT DEFAULT '',
        tier TEXT DEFAULT '',
        sqs INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS snapshot_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER NOT NULL REFERENCES site_snapshots(id),
        action TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        notes TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_snap_site ON site_snapshots(site_name);
    CREATE INDEX IF NOT EXISTS idx_snap_project ON site_snapshots(project_name);
    CREATE INDEX IF NOT EXISTS idx_snap_year ON site_snapshots(survey_year);
    CREATE INDEX IF NOT EXISTS idx_snapsp_id ON snapshot_species(snapshot_id);
"""


@dataclass
class Snapshot:
    """A frozen assessment record."""
    id: int
    site_name: str
    project_name: str = ""
    client: str = ""
    survey_year: int = 0
    first_visit: str = ""
    last_visit: str = ""
    visit_count: int = 0
    species_count: int = 0
    key_species_count: int = 0
    key_species_pct: float = 0.0
    rare_count: int = 0
    scarce_count: int = 0
    priority_count: int = 0
    sqi: float = 0.0
    sqi_reliable: bool = True
    scoring_species: int = 0
    analysis_mode: str = "codex_full"
    codex_version: str = ""
    pantheon_version: str = ""
    frozen_date: str = ""
    notes: str = ""
    species: list = field(default_factory=list)  # [(tvk, name, status, tier, sqs)]


class SnapshotManager:
    """Manages frozen assessment snapshots."""

    def __init__(self, db_path: str = None):
        self._db_path = str(db_path or DB_PATH)
        self._conn = None
        self._ensure_db()

    def _ensure_db(self):
        """Create database and tables if they don't exist."""
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.executescript(SCHEMA)
        conn.commit()
        conn.close()

    def _get_conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def freeze_snapshot(self, site_name: str, project_name: str,
                        client: str, survey_year: int,
                        first_visit: str, last_visit: str, visit_count: int,
                        species_data: list, metrics: dict,
                        analysis_mode: str = "codex_full",
                        codex_version: str = "", pantheon_version: str = "",
                        notes: str = "") -> int:
        """
        Create a frozen snapshot.

        Args:
            site_name: Site name
            project_name: Project name
            client: Client name
            survey_year: Year of survey
            first_visit: First visit date (ISO string)
            last_visit: Last visit date (ISO string)
            visit_count: Number of visits
            species_data: List of (tvk, species_name, short_status, tier, sqs)
            metrics: Dict with sqi, key_species_count, key_species_pct,
                     rare_count, scarce_count, priority_count,
                     scoring_species, sqi_reliable
            analysis_mode: "codex_full" or "pantheon_only"
            codex_version: Codex build version string
            pantheon_version: Pantheon version string
            notes: Optional notes

        Returns:
            snapshot_id
        """
        conn = self._get_conn()
        c = conn.cursor()
        now = datetime.now().isoformat()

        # Insert or replace snapshot
        c.execute("""INSERT OR REPLACE INTO site_snapshots
            (site_name, project_name, client, survey_year,
             first_visit, last_visit, visit_count,
             species_count, key_species_count, key_species_pct,
             rare_count, scarce_count, priority_count,
             sqi, sqi_reliable, scoring_species,
             analysis_mode, codex_version, pantheon_version,
             frozen_date, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (site_name, project_name, client, survey_year,
             first_visit, last_visit, visit_count,
             len(species_data),
             metrics.get("key_species_count", 0),
             metrics.get("key_species_pct", 0.0),
             metrics.get("rare_count", 0),
             metrics.get("scarce_count", 0),
             metrics.get("priority_count", 0),
             metrics.get("sqi", 0.0),
             1 if metrics.get("sqi_reliable", True) else 0,
             metrics.get("scoring_species", 0),
             analysis_mode, codex_version, pantheon_version,
             now, notes))

        snapshot_id = c.lastrowid

        # Clear any existing species for this snapshot (from REPLACE)
        c.execute("DELETE FROM snapshot_species WHERE snapshot_id = ?",
                  (snapshot_id,))

        # Insert species
        c.executemany("""INSERT INTO snapshot_species
            (snapshot_id, tvk, species_name, short_status, tier, sqs)
            VALUES (?,?,?,?,?,?)""",
            [(snapshot_id, tvk, name, status, tier, sqs)
             for tvk, name, status, tier, sqs in species_data])

        # Log
        c.execute("""INSERT INTO snapshot_log (snapshot_id, action, timestamp, notes)
                     VALUES (?, 'frozen', ?, ?)""",
                  (snapshot_id, now, f"Mode: {analysis_mode}, Species: {len(species_data)}"))

        conn.commit()
        return snapshot_id

    def get_snapshots(self, site_name: str = None,
                      project_name: str = None) -> list:
        """Get all snapshots, optionally filtered by site/project."""
        conn = self._get_conn()
        c = conn.cursor()

        where_parts = []
        params = []
        if site_name:
            where_parts.append("site_name = ?")
            params.append(site_name)
        if project_name:
            where_parts.append("project_name = ?")
            params.append(project_name)

        where = " WHERE " + " AND ".join(where_parts) if where_parts else ""
        c.execute(f"""SELECT * FROM site_snapshots{where}
                      ORDER BY site_name, survey_year DESC, analysis_mode""",
                  params)

        return [self._row_to_snapshot(row) for row in c.fetchall()]

    def get_snapshot(self, snapshot_id: int) -> Snapshot:
        """Get a single snapshot with its species list."""
        conn = self._get_conn()
        c = conn.cursor()

        c.execute("SELECT * FROM site_snapshots WHERE id = ?", (snapshot_id,))
        row = c.fetchone()
        if not row:
            return None

        snap = self._row_to_snapshot(row)

        c.execute("""SELECT tvk, species_name, short_status, tier, sqs
                     FROM snapshot_species WHERE snapshot_id = ?
                     ORDER BY sqs DESC, species_name""", (snapshot_id,))
        snap.species = [(r["tvk"], r["species_name"], r["short_status"],
                         r["tier"], r["sqs"]) for r in c.fetchall()]

        return snap

    def delete_snapshot(self, snapshot_id: int):
        """Delete a snapshot and its species list."""
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("DELETE FROM snapshot_species WHERE snapshot_id = ?",
                  (snapshot_id,))
        c.execute("DELETE FROM site_snapshots WHERE id = ?", (snapshot_id,))
        conn.commit()

    def get_snapshot_count(self) -> int:
        c = self._get_conn().cursor()
        c.execute("SELECT COUNT(*) FROM site_snapshots")
        return c.fetchone()[0]

    def _row_to_snapshot(self, row) -> Snapshot:
        return Snapshot(
            id=row["id"],
            site_name=row["site_name"],
            project_name=row["project_name"] or "",
            client=row["client"] or "",
            survey_year=row["survey_year"],
            first_visit=row["first_visit"] or "",
            last_visit=row["last_visit"] or "",
            visit_count=row["visit_count"] or 0,
            species_count=row["species_count"] or 0,
            key_species_count=row["key_species_count"] or 0,
            key_species_pct=row["key_species_pct"] or 0.0,
            rare_count=row["rare_count"] or 0,
            scarce_count=row["scarce_count"] or 0,
            priority_count=row["priority_count"] or 0,
            sqi=row["sqi"] or 0.0,
            sqi_reliable=bool(row["sqi_reliable"]),
            scoring_species=row["scoring_species"] or 0,
            analysis_mode=row["analysis_mode"] or "codex_full",
            codex_version=row["codex_version"] or "",
            pantheon_version=row["pantheon_version"] or "",
            frozen_date=row["frozen_date"] or "",
            notes=row["notes"] or "",
        )
