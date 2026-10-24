"""The two 9 Oct 2026 one-off scripts, on throwaway databases: the taxonomy backfill
(OBS-11) and the s.l. -> species merge. Skipped once the scripts are archived."""
import importlib.util
import os
import sqlite3

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name):
    path = os.path.join(ROOT, "scripts", "_oneoff", name)
    if not os.path.exists(path):
        pytest.skip(f"{name} archived")
    spec = importlib.util.spec_from_file_location(name[:-3], path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture
def dbs(tmp_path):
    u = sqlite3.connect(tmp_path / "uksi.db")
    u.execute('CREATE TABLE taxa (tvk TEXT, scientific_name TEXT, rank TEXT, parent_tvk TEXT, '
              'kingdom TEXT, class TEXT, "order" TEXT, family TEXT, sort_code INTEGER, superfamily TEXT)')
    u.executemany("INSERT INTO taxa VALUES (?,?,?,?,?,?,?,?,?,?)", [
        ("B1", "Carabus nemoralis", "Species", None, "Animalia", "Insecta", "Coleoptera",
         "Carabidae", 18000, "Caraboidea"),
        ("P1", "Anthocharis cardamines", "Species", None, "Animalia", "Insecta", "Lepidoptera",
         "Pieridae", 45000, "Papilionoidea"),
        ("XS", "Xanthogramma pedissequum", "Species", None, "Animalia", "Insecta", "Diptera",
         "Syrphidae", 50, None),
        ("XL", "Xanthogramma pedissequum", "Species sensu lato", None, "Animalia", "Insecta",
         "Diptera", "Syrphidae", 49, None),
        ("XA", "Xanthogramma pedissequum/stackelbergi", "Species aggregate", None, "Animalia",
         "Insecta", "Diptera", "Syrphidae", 48, None),
    ])
    u.commit()
    u.close()
    o = sqlite3.connect(tmp_path / "observatum.db")
    o.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, species_tvk TEXT, species_name TEXT, "
              "family TEXT, taxon_group TEXT, kingdom TEXT, taxon_rank TEXT, superfamily TEXT, "
              "taxonomic_sort_key, recorder TEXT, import_notes TEXT)")
    o.execute("CREATE TABLE specimens (id INTEGER PRIMARY KEY, species_tvk TEXT, species_name TEXT, "
              "family TEXT, taxon_group TEXT, superfamily TEXT, taxonomic_sort_key, collector TEXT, "
              "import_notes TEXT)")
    o.executemany("INSERT INTO observations (id, species_tvk, species_name, family, taxon_group, "
                  "kingdom, recorder, import_notes) VALUES (?,?,?,?,?,?,?,?)", [
                      (1, "B1", "Carabus nemoralis", "Carabidae", None, None, "W", None),
                      (2, "P1", "Anthocharis cardamines", "Pieridae", "insect - moth", "Animalia", "W", None),
                      (3, "B1", "Carabus nemoralis", "Carabidae", "my own group", "Animalia", "W", None),
                      (4, "ZZ", "Not in UKSI", None, None, None, "W", None),
                      (5, "XL", "Xanthogramma pedissequum", "Syrphidae", None, None, "W", "old note"),
                      (6, "XA", "Xanthogramma pedissequum/stackelbergi", "Syrphidae", None, None, "W", None),
                  ])
    o.execute("INSERT INTO specimens (id, species_tvk, species_name, collector) "
              "VALUES (1, 'XL', 'Xanthogramma pedissequum', 'W')")
    o.commit()
    return o, tmp_path / "uksi.db"


