"""One UKSI lookup (24 Nov 2026): UKSIRepository is a thin wrapper over UKSIModel, so both
entry points give the same answers.  A small made-up uksi.db whose tables copy the real file's
column shapes (PRAGMA table_info on data/uksi.db, opened read-only); no real figures pinned."""
import dataclasses
import os
import sqlite3
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "Observatum")]

import paths  # noqa: E402
from src.models.database import DatabaseManager  # noqa: E402
from src.models.uksi import UKSIModel  # noqa: E402
from src.repositories.uksi_repository import UKSIRepository  # noqa: E402

pytestmark = pytest.mark.skipif(not os.path.exists(paths.UKSI_DB), reason="needs data/uksi.db for table shapes")
RANKS = ["Species", "Species aggregate", "Microspecies"]


def _shape(table):
    """CREATE TABLE text from the real file's PRAGMA table_info (columns, types, NOT NULL, defaults, PK)."""
    real = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
    try:
        info = real.execute(f"PRAGMA table_info({table})").fetchall()
    finally:
        real.close()
    cols = []
    for _cid, name, typ, notnull, dflt, pk in info:
        c = f'"{name}" {typ}' + (" NOT NULL" if notnull else "") + (f" DEFAULT {dflt}" if dflt is not None else "")
        cols.append(c + (" PRIMARY KEY" if pk == 1 and len(
            [i for i in info if i[5]]) == 1 else ""))
    return f"CREATE TABLE {table} ({', '.join(cols)})"


@pytest.fixture
def uksi_path(tmp_path):
    p = tmp_path / "uksi.db"
    c = sqlite3.connect(p)
    for t in ("taxa", "common_names", "synonyms"):
        c.execute(_shape(t))
    tx = "INSERT INTO taxa (tvk, scientific_name, rank, parent_tvk, \"order\", family, genus) VALUES (?,?,?,?,?,?,?)"
    c.executemany(tx, [
        ("F1", "Cerambycidae", "Family", None, "Coleoptera", None, None),
        ("T1", "Rutpela maculata", "Species", "F1", "Coleoptera", "Cerambycidae", "Rutpela"),
        ("T2", "Rutpela agg", "Species aggregate", "F1", "Coleoptera", "Cerambycidae", "Rutpela"),
        ("T3", "Rutpela micro", "Microspecies", "F1", "Coleoptera", "Cerambycidae", "Rutpela"),
        ("T4", "Bombus lucorum", "Species", None, "Hymenoptera", "Apidae", "Bombus"),   # no parent: no walk
        ("T5", "Rutpela nofamily", "Species", "F1", None, None, "Rutpela"),             # family via hierarchy
    ])
    # T1: two names, the preferred one is not the shortest, so the pick rule is visible
    c.executemany("INSERT INTO common_names (common_name, tvk, preferred) VALUES (?,?,?)", [
        ("Black-and-yellow Longhorn", "T1", 1), ("Long", "T1", 0), ("Bumblebee", "T4", 0), ("Buff Bee", "T4", 0)])
    # 150 synonyms of one species: the old model read only 100 of them
    c.executemany("INSERT INTO synonyms (synonym, tvk) VALUES (?,?)",
                  [(f"Oldgenus oldname{i:03d}", "T4") for i in range(150)])
    c.commit()
    c.close()
    return str(p)


@pytest.fixture
def both(uksi_path, tmp_path):
    main = tmp_path / "observatum.db"
    sqlite3.connect(main).close()                       # set_paths wants the file to exist
    db = DatabaseManager()
    db.set_paths(str(main), uksi_path)
    return UKSIModel(db), UKSIRepository(uksi_path)


QUERIES = ["rutpela", "Rut mac", "longhorn", "bee", "oldname", "Bombus lucorum", "zzzz", "r"]


@pytest.mark.parametrize("q", QUERIES)
def test_search_same_from_both(both, q):
    model, repo = both
    want = [dataclasses.asdict(r) for r in model.search_species(q, limit=500)]
    assert repo.search_species(q, limit=500) == want
    assert [dataclasses.asdict(r) for r in model.search_species(q, limit=2)] == repo.search_species(q, limit=2)


def test_filters_and_recorded_boost_same(both):
    model, repo = both
    kw = dict(order_filter="Coleoptera", recorded_tvks=["T3"])
    got = repo.search_species("rutpela", limit=50, **kw)
    assert got == [dataclasses.asdict(r) for r in model.search_species("rutpela", limit=50, **kw)]
    assert got[0]["tvk"] == "T3"                         # recorded species ranked first


def test_aggregates_and_microspecies_found(both):
    _model, repo = both
    assert {"T1", "T2", "T3"} <= {r["tvk"] for r in repo.search_species("rutpela", limit=50)}


def test_synonym_search_reads_up_to_300(both):
    model, repo = both
    assert len(model.search_species("oldname", limit=500)) == 1          # one species, found via synonyms
    q = "oldname14"                                                       # a synonym past the old 100 cut
    assert [r.tvk for r in model.search_species(q)] == ["T4"] == [r["tvk"] for r in repo.search_species(q)]


def test_common_name_pick_rule_in_search(both):
    _model, repo = both
    by = {r["tvk"]: r for r in repo.search_species("rutpela", limit=50)}
    assert by["T1"]["common_name"] == "Black-and-yellow Longhorn"        # preferred, not the shortest
    assert by["T2"]["common_name"] is None
    bees = {r["tvk"]: r for r in repo.search_species("Bombus", limit=5)}
    assert bees["T4"]["common_name"] == "Buff Bee"                        # none preferred: capital, then shorter


def test_species_lookups_same_shape_and_values(both):
    model, repo = both
    for tvk in ("T1", "T5", "T4", "NOPE"):
        sp = model.get_species_by_tvk(tvk)
        want = None if sp is None else {**dataclasses.asdict(sp), "taxon_name": sp.scientific_name}
        assert repo.get_species_by_tvk(tvk) == want
        assert repo.get_taxonomy(tvk) == model.get_taxonomy(tvk)
    assert repo.get_species_by_tvk("T5")["family"] == "Cerambycidae"       # walked up the hierarchy
    assert repo.get_species_by_name("Rutpela maculata")["tvk"] == "T1"
    assert repo.get_species_by_name("Nothing here") is None
    assert repo.get_species_by_tvk("T1")["common_name"] == "Black-and-yellow Longhorn"


def test_batch_same_from_both(both):
    model, repo = both
    names = ["rutpela maculata", "Bombus lucorum", "missing name"]
    got = repo.get_species_batch(names)
    assert set(got) == set(names) and got["missing name"] is None
    for n in names[:2]:
        sp = model.get_species_batch(names)[n]
        assert got[n] == {**dataclasses.asdict(sp), "taxon_name": sp.scientific_name}
    assert got["rutpela maculata"]["tvk"] == "T1"


def test_lists_and_hierarchy_same(both):
    model, repo = both
    assert repo.get_common_names("T1") == model.get_common_names("T1")
    assert repo.get_synonyms("T4") == model.get_synonyms("T4") and len(repo.get_synonyms("T4")) == 150
    assert repo.get_orders() == model.get_orders()
    assert repo.get_families() == model.get_families() == ["Cerambycidae"]
    assert repo.get_parent("T1") == model.get_parent("T1") == "F1"
    assert repo.get_children("F1") == model.get_children("F1")


def test_repository_is_read_only_and_keeps_its_extras(both):
    _model, repo = both
    assert repo.count_species() == 3                                      # T1, T4, T5 (ranks Species/Subspecies)
    assert repo.count_by_family() == {"Cerambycidae": 1, "Apidae": 1}
    with pytest.raises(sqlite3.OperationalError):
        repo._execute("INSERT INTO synonyms (synonym, tvk) VALUES ('x', 'T1')")
