"""Small purpose-made databases for the Round A tests (Data Entry preview, status marks).

uksi / codex / pantheon / observatum / examen in a temp folder, with the module paths pointed at
them. Species (all invertebrates unless noted):
    T_RARE   Nationally Rare (NR)         -> Rare Key Species
    T_VU     Vulnerable (threat 2001)     -> Rare Key Species
    T_SCARCE Nationally Scarce (NS)       -> Scarce Key Species
    T_COMMON no status
    T_PLANT  Bee Orchid, kingdom Plantae  -> never Key, no status
"""
import sqlite3
from pathlib import Path

import paths

T_RARE, T_VU, T_SCARCE, T_COMMON, T_PLANT = "T_RARE", "T_VU", "T_SCARCE", "T_COMMON", "T_PLANT"
NAMES = {T_RARE: "Rarus beetle", T_VU: "Vulnus bug", T_SCARCE: "Scarcus beetle",
         T_COMMON: "Communis beetle", T_PLANT: "Ophrys apifera"}
# (species_name, tvk, date, site, vc)
RECORDS = [
    (NAMES[T_RARE], T_RARE, "2026-05-10", "North", 74),
    (NAMES[T_RARE], T_RARE, "2026-06-11", "North", 74),
    (NAMES[T_VU], T_VU, "2026-05-10", "South", 74),
    (NAMES[T_SCARCE], T_SCARCE, "2026-06-11", "South", 74),
    (NAMES[T_COMMON], T_COMMON, "2026-06-11", "South", 74),
    (NAMES[T_PLANT], T_PLANT, "2026-06-11", "South", 74),
]

OBS_DDL = """
CREATE TABLE observations (id INTEGER PRIMARY KEY, record_type TEXT);   -- load_all_projects checks it
CREATE TABLE assessment_records (origin TEXT DEFAULT 'own', contributor TEXT, id INTEGER PRIMARY KEY,
    record_type TEXT, project_name TEXT, client TEXT, site_name TEXT, sub_location TEXT,
    date TEXT, species_name TEXT, species_tvk TEXT, quantity INTEGER, vc_number INTEGER,
    visit_number TEXT, method TEXT, determiner TEXT, grid_ref TEXT);
CREATE TABLE entry_jobs (id INTEGER PRIMARY KEY, name TEXT, mode TEXT, client TEXT, project TEXT,
    embargo_until TEXT, status TEXT, notes TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE entry_staging (id INTEGER PRIMARY KEY, job_id INTEGER, row_order INTEGER,
    species_name TEXT, species_tvk TEXT, date TEXT, site_name TEXT, sub_location TEXT,
    quantity INTEGER, vc_number INTEGER,
    grid_ref TEXT, method TEXT, determiner TEXT, visit_number TEXT, check_flag INTEGER DEFAULT 0);
"""


def _run(path, ddl, rows=()):
    c = sqlite3.connect(str(path))
    c.executescript(ddl)
    for sql, data in rows:
        c.executemany(sql, data)
    c.commit()
    c.close()
    return Path(path)


def build(tmp_path, monkeypatch, with_mark_tables=True, old_marks_schema=False):
    """Create the databases and point paths / examen_data at them. Returns the folder."""
    taxa = [(t, NAMES[t], "Species", "G", "Plantae" if t == T_PLANT else "Animalia",
             "Tracheophyta" if t == T_PLANT else "Arthropoda") for t in NAMES]
    uksi = _run(tmp_path / "uksi.db",
                "CREATE TABLE taxa (tvk TEXT PRIMARY KEY, scientific_name TEXT, rank TEXT, "
                "parent_tvk TEXT, kingdom TEXT, phylum TEXT, family TEXT, \"order\" TEXT, "
                "sort_code INTEGER);"
                "CREATE TABLE common_names (tvk TEXT, common_name TEXT, preferred INTEGER);",
                [("INSERT INTO taxa VALUES (?,?,?,?,?,?,'Fam','Coleoptera',1)", taxa)])
    codex = _run(tmp_path / "codex.db", """
        CREATE TABLE designations (tvk TEXT, category TEXT);
        CREATE TABLE status_summary (tvk TEXT, status_track TEXT, status_value TEXT,
            status_detail TEXT, source TEXT, iucn_version TEXT);
        CREATE TABLE sqs_scores (tvk TEXT PRIMARY KEY, sqs INTEGER, source TEXT DEFAULT 'pantheon');
        CREATE TABLE species_profiles (tvk TEXT, profile_text TEXT, source TEXT);
        CREATE TABLE tvk_bridge (pantheon_tvk TEXT PRIMARY KEY, uksi_tvk TEXT,
            species_name TEXT, match_method TEXT);""", [
        ("INSERT INTO status_summary VALUES (?,?,?,NULL,'test','')",
         [(T_RARE, "rarity_modern", "NR"), (T_VU, "threat_iucn_2001", "VU"),
          (T_SCARCE, "rarity_modern", "NS")]),
        ("INSERT INTO sqs_scores (tvk, sqs) VALUES (?,?)", [(T_RARE, 8), (T_SCARCE, 4)])])
    pantheon = _run(tmp_path / "pantheon.db", """
        CREATE TABLE species (tvk TEXT PRIMARY KEY, species_name TEXT, family TEXT);
        CREATE TABLE sqs_scores (tvk TEXT, sqs INTEGER);
        CREATE TABLE conservation_status (tvk TEXT, reporting_category TEXT, abbreviation TEXT);
        CREATE TABLE broad_biotope (tvk TEXT, biotope TEXT);
        CREATE TABLE habitats (tvk TEXT, habitat TEXT);
        CREATE TABLE specific_assemblage_types (tvk TEXT, sat_name TEXT);
        CREATE TABLE feeding_guilds (tvk TEXT, life_stage TEXT, guild TEXT);
        CREATE TABLE fidelity_scores (tvk TEXT, index_name TEXT, score TEXT);
        CREATE TABLE associations (tvk TEXT, associated_taxa_type TEXT, associated_taxa TEXT);""")
    obs = _run(tmp_path / "observatum.db", OBS_DDL)
    examen = _run(tmp_path / "examen.db", """
        CREATE TABLE status_downgrades (tvk TEXT PRIMARY KEY, species_name TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT '',
            status_marked TEXT NOT NULL DEFAULT '', created_at TEXT, updated_at TEXT);
        CREATE TABLE status_downgrade_overrides (project_name TEXT NOT NULL,
            client TEXT NOT NULL DEFAULT '', survey_year TEXT NOT NULL DEFAULT '',
            tvk TEXT NOT NULL, species_name TEXT NOT NULL DEFAULT '', bracket INTEGER NOT NULL,
            status_marked TEXT NOT NULL DEFAULT '', updated_at TEXT, PRIMARY KEY(project_name, client, survey_year, tvk));"""
                 if with_mark_tables else "CREATE TABLE unrelated (x INTEGER);")
    if old_marks_schema:        # as scripts/add_report_tables.py made them before status_marked
        c = sqlite3.connect(str(examen))
        for t in ("status_downgrades", "status_downgrade_overrides"):
            c.execute(f"ALTER TABLE {t} DROP COLUMN status_marked")
        c.commit()
        c.close()
    for attr, p in (("UKSI_DB", uksi), ("CODEX_DB", codex), ("PANTHEON_DB", pantheon),
                    ("OBSERVATUM_DB", obs), ("EXAMEN_DB", examen)):
        monkeypatch.setattr(paths, attr, p)
    from Examen import examen_data
    monkeypatch.setattr(examen_data, "DB_PATH", obs)
    monkeypatch.setattr(examen_data, "load_taxonomy", lambda tvks: {
        t: {"common": "", "family": "Fam", "order": "Coleoptera"} for t in tvks})

    from shared.repositories.codex_repository import CodexRepository
    from shared.repositories.pantheon_repository import PantheonRepository
    from shared.services.pantheon_analysis_service import PantheonAnalysisService
    repos = []

    def service():
        pan = PantheonRepository(str(pantheon), codex_path=str(codex), uksi_path=str(uksi))
        cx = CodexRepository(str(codex), str(pantheon), uksi_path=str(uksi))
        repos.extend([pan, cx])
        return PantheonAnalysisService(pan, cx)
    monkeypatch.setattr(examen_data, "analysis_service", service)
    from Examen import workbook_export as we
    monkeypatch.setattr(we, "_reference_counts", lambda: {"biotope": {}, "habitat": {}, "sat": {}})
    monkeypatch.setattr(we, "_sat_thresholds", lambda: {})
    return tmp_path


def add_committed(tmp_path, project="Notts Park", client="Acme", records=RECORDS):
    c = sqlite3.connect(str(tmp_path / "observatum.db"))
    c.executemany(
        "INSERT INTO assessment_records (record_type, project_name, client, site_name, date, "
        "species_name, species_tvk, quantity, vc_number) VALUES ('Commercial',?,?,?,?,?,?,1,?)",
        [(project, client, site, d, n, t, vc) for n, t, d, site, vc in records])
    c.commit()
    c.close()


def add_job(tmp_path, name="Notts", project="Notts Park", client="Acme", status="active",
            records=RECORDS, extra_rows=()):
    c = sqlite3.connect(str(tmp_path / "observatum.db"))
    cur = c.execute("INSERT INTO entry_jobs (name, mode, client, project, status) "
                    "VALUES (?, 'Commercial', ?, ?, ?)", (name, client, project, status))
    jid = cur.lastrowid
    rows = list(records) + list(extra_rows)
    c.executemany(
        "INSERT INTO entry_staging (job_id, row_order, species_name, species_tvk, date, "
        "site_name, quantity, vc_number) VALUES (?,?,?,?,?,?,1,?)",
        [(jid, i, n, t, d, site, vc) for i, (n, t, d, site, vc) in enumerate(rows)])
    c.commit()
    c.close()
    return jid


def add_staged(tmp_path, job_id, **cols):
    """One more staged row with exactly these columns (for held-back and odd rows)."""
    c = sqlite3.connect(str(tmp_path / "observatum.db"))
    cols = {"row_order": 99, **cols, "job_id": job_id}
    c.execute(f"INSERT INTO entry_staging ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
              list(cols.values()))
    c.commit()
    c.close()
