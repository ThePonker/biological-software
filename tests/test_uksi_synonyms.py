"""UKSI synonyms fix (backlog F14, fault F25)."""
import sqlite3

from scripts.fix_uksi_synonyms import plan


def _uksi(tmp_path):
    c = sqlite3.connect(tmp_path / "uksi.db")
    c.executescript("""
        CREATE TABLE taxa (tvk TEXT, scientific_name TEXT);
        CREATE TABLE synonyms (synonym TEXT, tvk TEXT);
        CREATE TABLE name_map (tvk TEXT PRIMARY KEY, recommended_tvk TEXT, name TEXT,
                               recommended_name TEXT, name_status TEXT, deprecated TEXT, source TEXT);
        CREATE TABLE tvk_remap (old_tvk TEXT PRIMARY KEY, new_tvk TEXT, method TEXT, old_name TEXT, new_name TEXT);
        INSERT INTO taxa VALUES ('LT', 'Lamia textor'), ('MS', 'Monochamus sartor'), ('HA', 'Hypnogyra angularis');
        -- NAMES: Lamia sartor is Monochamus sartor; Xantholinus angularis is Hypnogyra angularis (via an old key)
        INSERT INTO name_map VALUES ('n1', 'MS', 'Lamia sartor', 'Monochamus sartor', 'S', '', '');
        INSERT INTO name_map VALUES ('n2', 'OLD', 'Xantholinus angularis', '', 'S', '', '');
        INSERT INTO tvk_remap VALUES ('OLD', 'HA', 'name_map', '', '');
        INSERT INTO name_map VALUES ('n3', 'LT', 'Lamia sutor', 'Lamia textor', 'S', '', '');
        INSERT INTO synonyms VALUES ('Lamia sartor', 'MS'), ('Lamia sartor', 'LT'),
                                    ('Xantholinus angularis', 'HA'), ('Lamia sutor', 'LT'),
                                    ('Only carried', 'LT');
    """)
    return c


def test_carried_rows_yield_to_names_and_corrections_apply(tmp_path):
    c = _uksi(tmp_path)
    corr = {"exclude": {("Lamia sutor", "LT")}, "add": {("Cerambyx textor", "LT"), ("Nope", "XX")}}
    removals, additions = plan(c, corr)
    assert sorted((s, t) for s, t, _ in removals) == [("Lamia sartor", "LT"), ("Lamia sutor", "LT")]
    assert [(s, t) for s, t, _ in additions] == [("Cerambyx textor", "LT")]   # unknown TVK skipped


def test_the_real_corrections_file_loads():
    from scripts.fix_uksi_synonyms import load_corrections
    corr = load_corrections()
    assert ("Lamia sartor", "NBNSYS0000011050") in corr["exclude"]
    assert ("Cerambyx textor", "NBNSYS0000011050") in corr["add"]
