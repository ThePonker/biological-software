"""Build pantheon.db from the Pantheon v3.7.4 CSV download (backlog D5, fault F26).

Reconstructed 9 Oct 2026: the original script was lost in the March restructure.
It reproduces the existing pantheon.db table for table (checked row by row against
the March 2026 build -- see check_pantheon_rebuild.py), with one deliberate change:

    Species that Pantheon published WITHOUT a TVK (1,114 of them -- 797 of those
    give only a preferred name) used to be stored under one blank key '', so all
    but one lost their ecology and SQS (fault F26). Each is now keyed on its own
    name, as  NOTVK:<species name>  (the preferred name where that is all there
    is), and its species_name is filled from the preferred name when blank. The
    Codex bridge resolves these through Pantheon's preferred TVK, then by name
    and synonym (e.g. Ochlerotatus communis -> Aedes communis).

Inputs (Pantheon 3.7.4, NERC EIDC, doi 10.5285/2a353d2d-c1b9-4bf7-8702-9e78910844bc):
    PantheonHabitatTraits_v3.7.4.csv, PantheonConservationStatus_v3.7.4.csv,
    PantheonAssociations_v3.7.4.csv
    default folder: Observatum\\test data\\Pantheon Data Download\\data

Usage:
    py -3.14 scripts\\build_pantheon_db.py --out PATH      build into a new file (safe)
    py -3.14 scripts\\build_pantheon_db.py --replace       build, back up the live
                                                         pantheon.db, then swap it in
    options: --csv-dir FOLDER   --uksi PATH (for the uksi_match table; default uksi.db)

Order of rebuilds: UKSI -> Pantheon -> Codex. After replacing pantheon.db,
rebuild Codex (build_codex_db.py) so the bridge and SQS pick up the change.
"""
import csv
import os
import shutil
import sqlite3
import sys
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths  # noqa: E402

DEFAULT_CSV_DIR = os.path.join(str(paths.OBSERVATUM_DIR), "test data", "Pantheon Data Download", "data")
VERSION = "3.7.4"
HT = f"PantheonHabitatTraits_v{VERSION}.csv"
CS = f"PantheonConservationStatus_v{VERSION}.csv"
AS = f"PantheonAssociations_v{VERSION}.csv"
NO_TVK_PREFIX = "NOTVK:"

SCHEMA = """
CREATE TABLE species (
        tvk TEXT PRIMARY KEY,
        species_name TEXT NOT NULL,
        preferred_name TEXT,
        preferred_tvk TEXT,
        family TEXT
    );
CREATE TABLE conservation_status (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tvk TEXT NOT NULL,
        reporting_category TEXT NOT NULL,
        designation TEXT NOT NULL,
        abbreviation TEXT NOT NULL,
        FOREIGN KEY (tvk) REFERENCES species(tvk)
    );
CREATE TABLE habitat_traits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tvk TEXT NOT NULL,
        trait_type TEXT NOT NULL,
        trait_name TEXT NOT NULL,
        trait_value TEXT,
        trait_id INTEGER,
        parent_trait_id INTEGER,
        resource_heading TEXT,
        FOREIGN KEY (tvk) REFERENCES species(tvk)
    );
CREATE TABLE associations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tvk TEXT NOT NULL,
        associated_tree_type TEXT,
        associated_taxa_type TEXT,
        associated_taxa TEXT,
        FOREIGN KEY (tvk) REFERENCES species(tvk)
    );
CREATE TABLE sqs_scores (
        tvk TEXT PRIMARY KEY,
        sqs INTEGER NOT NULL,
        FOREIGN KEY (tvk) REFERENCES species(tvk)
    );
CREATE TABLE broad_biotope (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tvk TEXT NOT NULL,
        biotope TEXT NOT NULL,
        FOREIGN KEY (tvk) REFERENCES species(tvk)
    );
CREATE TABLE habitats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tvk TEXT NOT NULL,
        habitat TEXT NOT NULL,
        FOREIGN KEY (tvk) REFERENCES species(tvk)
    );
CREATE TABLE feeding_guilds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tvk TEXT NOT NULL,
        life_stage TEXT NOT NULL,
        guild TEXT,
        FOREIGN KEY (tvk) REFERENCES species(tvk)
    );
CREATE TABLE specific_assemblage_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tvk TEXT NOT NULL,
        sat_name TEXT NOT NULL,
        FOREIGN KEY (tvk) REFERENCES species(tvk)
    );
CREATE TABLE fidelity_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tvk TEXT NOT NULL,
        index_name TEXT NOT NULL,
        score TEXT,
        FOREIGN KEY (tvk) REFERENCES species(tvk)
    );
CREATE TABLE uksi_match (
        pantheon_tvk TEXT PRIMARY KEY,
        uksi_tvk TEXT,
        match_method TEXT,
        FOREIGN KEY (uksi_tvk) REFERENCES species(tvk)
    );
CREATE TABLE metadata (
        key TEXT PRIMARY KEY,
        value TEXT
    );
CREATE INDEX idx_cs_tvk ON conservation_status(tvk);
CREATE INDEX idx_ht_tvk ON habitat_traits(tvk);
CREATE INDEX idx_ht_type ON habitat_traits(trait_type);
CREATE INDEX idx_bb_tvk ON broad_biotope(tvk);
CREATE INDEX idx_hab_tvk ON habitats(tvk);
CREATE INDEX idx_fg_tvk ON feeding_guilds(tvk);
CREATE INDEX idx_sat_tvk ON specific_assemblage_types(tvk);
CREATE INDEX idx_fid_tvk ON fidelity_scores(tvk);
CREATE INDEX idx_assoc_tvk ON associations(tvk);
CREATE INDEX idx_match_uksi ON uksi_match(uksi_tvk);
"""


def species_key(row, legacy_blank_key=False):
    """The key a CSV row is stored under: its TVK, or NOTVK:<name> when it has none."""
    tvk = (row.get("SpeciesTVK") or "").strip()
    if tvk or legacy_blank_key:
        return tvk
    name = (row.get("SpeciesName") or "").strip() or (row.get("PreferredName") or "").strip()
    return NO_TVK_PREFIX + name


def _int_or_blank(v):
    v = (v or "").strip()
    return int(v) if v.lstrip("-").isdigit() else v


def read_csv(path):
    # Text mode on purpose: a few association cells hold line breaks, and the
    # original build stored them as \n (the CSV has \r\n).
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def build(out_path, csv_dir=DEFAULT_CSV_DIR, uksi_path=None, legacy_blank_key=False, log=print):
    """Build a complete pantheon.db at out_path (which must not exist)."""
    if os.path.exists(out_path):
        raise FileExistsError(out_path)
    ht = read_csv(os.path.join(csv_dir, HT))
    cs = read_csv(os.path.join(csv_dir, CS))
    asr = read_csv(os.path.join(csv_dir, AS))
    log(f"Read {len(ht):,} trait rows, {len(cs):,} status rows, {len(asr):,} association rows")

    def key(r):
        return species_key(r, legacy_blank_key)

    conn = sqlite3.connect(out_path)
    c = conn.cursor()
    c.executescript(SCHEMA)

    # Species: every key met in any file; the first sighting wins, family included
    # (the original build did not fill a blank family from a later file).
    species = {}
    # Order matters: the original read traits, then statuses, then associations.
    for rows in (ht, cs, asr):
        for r in rows:
            k = key(r)
            if k not in species:
                name = r["SpeciesName"]
                if not name.strip() and not legacy_blank_key:
                    name = r.get("PreferredName") or ""     # 797 rows give only the preferred name
                species[k] = [k, name, r.get("PreferredName") or None,
                              r.get("PreferredTVK") or None, r.get("Family") or ""]
    c.executemany("INSERT INTO species VALUES (?,?,?,?,?)", species.values())

    c.executemany("""INSERT INTO conservation_status (tvk, reporting_category, designation, abbreviation)
                     VALUES (?,?,?,?)""",
                  [(key(r), r["ReportingCategory"], r["Designation"], r["DesignationAbbreviation"]) for r in cs])

    c.executemany("""INSERT INTO habitat_traits (tvk, trait_type, trait_name, trait_value,
                     trait_id, parent_trait_id, resource_heading) VALUES (?,?,?,?,?,?,?)""",
                  [(key(r), r["TraitType"], r["TraitName"], r["TraitValue"], _int_or_blank(r["TraitID"]),
                    _int_or_blank(r["ParentTraitID"]), r["ResourceHeading"]) for r in ht])

    c.executemany("""INSERT INTO associations (tvk, associated_tree_type, associated_taxa_type, associated_taxa)
                     VALUES (?,?,?,?)""",
                  [(key(r), r["AssociatedTreeType"], r["AssociatedTaxaType"], r["AssociatedTaxa"]) for r in asr])

    by_type = {}
    for r in ht:
        by_type.setdefault(r["TraitType"], []).append(r)
    sqs = {}
    for r in by_type.get("rarity score", []):
        if r["TraitName"] == "SQS" and r["TraitValue"].strip().isdigit():
            sqs.setdefault(key(r), int(r["TraitValue"]))   # first row wins, as the original build did
    c.executemany("INSERT INTO sqs_scores VALUES (?,?)", sqs.items())
    c.executemany("INSERT INTO broad_biotope (tvk, biotope) VALUES (?,?)",
                  [(key(r), r["TraitName"]) for r in by_type.get("broad biotope", [])])
    c.executemany("INSERT INTO habitats (tvk, habitat) VALUES (?,?)",
                  [(key(r), r["TraitName"]) for r in by_type.get("habitat", [])])
    c.executemany("INSERT INTO feeding_guilds (tvk, life_stage, guild) VALUES (?,?,?)",
                  [(key(r), r["TraitName"], r["TraitValue"]) for r in by_type.get("feeding guild", [])])
    c.executemany("INSERT INTO specific_assemblage_types (tvk, sat_name) VALUES (?,?)",
                  [(key(r), r["TraitName"]) for r in by_type.get("specific assemblage type", [])])
    c.executemany("INSERT INTO fidelity_scores (tvk, index_name, score) VALUES (?,?,?)",
                  [(key(r), r["TraitName"], r["TraitValue"]) for r in by_type.get("fidelity score", [])])

    # uksi_match: informational only (nothing reads it; Codex builds its own bridge).
    methods = {}
    if uksi_path and os.path.exists(uksi_path):
        u = sqlite3.connect(f"file:{os.path.abspath(uksi_path)}?mode=ro", uri=True)
        uksi_tvks = {t for (t,) in u.execute("SELECT tvk FROM taxa")}
        uksi_names = {}
        for n, t in u.execute("SELECT scientific_name, tvk FROM taxa ORDER BY rowid"):
            uksi_names.setdefault((n or "").lower(), t)
        u.close()
        rows = []
        for k, _name, pname, ptvk, _fam in species.values():
            if k in uksi_tvks:
                rows.append((k, k, "tvk_direct"))
            elif ptvk and ptvk in uksi_tvks:
                rows.append((k, ptvk, "preferred_tvk"))
            elif (pname or "").lower() in uksi_names:          # Pantheon's preferred name
                rows.append((k, uksi_names[pname.lower()], "name_match"))
            else:
                rows.append((k, None, "unmatched"))
        c.executemany("INSERT INTO uksi_match VALUES (?,?,?)", rows)
        for _, _, m in rows:
            methods[m] = methods.get(m, 0) + 1

    c.executemany("INSERT INTO metadata VALUES (?,?)", [
        ("version", VERSION),
        ("source", "NERC EIDC - Webb et al. 2017"),
        ("licence", "Open Government Licence"),
        ("doi", "10.5285/2a353d2d-c1b9-4bf7-8702-9e78910844bc"),
        ("species_count", str(len(species))),
        ("import_date", date.today().isoformat()),
        ("builder", "scripts/build_pantheon_db.py (reconstructed Oct 2026)"),
        ("no_tvk_keying", "legacy blank key" if legacy_blank_key else f"{NO_TVK_PREFIX}<species name>"),
    ])
    conn.commit()
    conn.close()
    no_tvk = sum(1 for k in species if k.startswith(NO_TVK_PREFIX))
    log(f"Built {out_path}")
    log(f"  species {len(species):,} ({no_tvk} keyed on name)   SQS {len(sqs):,}   uksi_match {methods or 'skipped'}")
    return out_path


def main():
    args = sys.argv[1:]

    def opt(name, default=None):
        return args[args.index(name) + 1] if name in args else default

    csv_dir = opt("--csv-dir", DEFAULT_CSV_DIR)
    uksi = opt("--uksi", str(paths.UKSI_DB))
    for f in (HT, CS, AS):
        if not os.path.exists(os.path.join(csv_dir, f)):
            sys.exit(f"Missing {f} in {csv_dir}")

    if "--out" in args:
        build(opt("--out"), csv_dir, uksi)
        return
    if "--replace" not in args:
        print(__doc__)
        return

    live = str(paths.PANTHEON_DB)
    new = live + ".new"
    if os.path.exists(new):
        sys.exit(f"{new} already exists from an earlier run -- move it to _archive first.")
    build(new, csv_dir, uksi)
    if input(f"\n  Replace {live} with the new build? Apps closed? Type YES: ").strip() != "YES":
        print(f"  Stopped. The new build is left at {new} -- live pantheon.db unchanged.")
        return
    bdir = os.path.join(r"C:\BiologicalSoftware_Backups", "reference") if os.name == "nt" \
        else os.path.join(ROOT, "_backups", "reference")
    os.makedirs(bdir, exist_ok=True)
    backup = os.path.join(bdir, f"pantheon_pre_rebuild_{datetime.now():%Y%m%d_%H%M%S}.db")
    src = sqlite3.connect(f"file:{live}?mode=ro", uri=True)
    dst = sqlite3.connect(backup)
    src.backup(dst)
    dst.close()
    src.close()
    print(f"  Backup: {backup}")
    retired = os.path.join(ROOT, "_archive", f"pantheon_replaced_{datetime.now():%Y%m%d_%H%M%S}")
    os.makedirs(retired)
    shutil.move(live, os.path.join(retired, "pantheon.db"))      # retired, never deleted
    shutil.move(new, live)
    print(f"  Old pantheon.db moved to {retired}")
    print(f"  pantheon.db replaced. Next: rebuild Codex (py -3.14 scripts\\build_codex_db.py).")


if __name__ == "__main__":
    main()
