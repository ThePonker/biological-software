"""Invertebrates only: the one rule behind every species count (shared/invertebrate_filter.py)."""
import sqlite3

import pytest

from shared.invertebrate_filter import is_vertebrate_group, non_invertebrate_tvks


def _db(path, ddl, rows, table):
    c = sqlite3.connect(str(path))
    c.executescript(ddl)
    for r in rows:
        c.execute(f"INSERT INTO {table} VALUES ({','.join('?' * len(r))})", r)
    c.commit()
    c.close()
    return path


@pytest.fixture
def dbs(tmp_path):
    obs = _db(tmp_path / "obs.db",
              "CREATE TABLE observations (id INTEGER PRIMARY KEY, species_tvk TEXT, kingdom TEXT, "
              "taxon_group TEXT)",
              [(1, "T_BEE", "Animalia", "insect - hymenopteran"),
               (2, "T_ORCHID", "Plantae", "flowering plant"),
               (3, "T_WREN", "Animalia", "bird"),
               (4, "T_NEWT", "Animalia", "amphibian"),
               (5, "T_EARWIG_AGG", "Animalia", "insect - earwig (Dermaptera)"),
               (6, "T_FUNGUS", "Fungi", ""),
               (7, "T_NOGROUP", "Animalia", ""),          # kingdom only: UKSI decides
               (8, "T_BLANK", "", "")],                    # nothing: UKSI decides
              "observations")
    uksi = _db(tmp_path / "uksi.db",
               "CREATE TABLE taxa (tvk TEXT PRIMARY KEY, kingdom TEXT, phylum TEXT)",
               [("T_BEE", "Animalia", "Arthropoda"), ("T_ORCHID", "Plantae", "Tracheophyta"),
                ("T_EARWIG_AGG", "", ""),                  # UKSI's invertebrate list misses it
                ("T_NOGROUP", "Animalia", "Chordata"),
                ("T_BLANK", "Plantae", "Bryophyta"),
                ("T_STAGED_PLANT", "Plantae", "Tracheophyta"),
                ("T_STAGED_FROG", "Animalia", "Chordata"),
                ("T_STAGED_BEETLE", "Animalia", "Arthropoda"),
                ("T_STAGED_UNKNOWN_KINGDOM", "", "")],
               "taxa")
    return obs, uksi


def test_rule(dbs):
    obs, uksi = dbs
    tvks = ["T_BEE", "T_ORCHID", "T_WREN", "T_NEWT", "T_EARWIG_AGG", "T_FUNGUS", "T_NOGROUP",
            "T_BLANK", "T_STAGED_PLANT", "T_STAGED_FROG", "T_STAGED_BEETLE",
            "T_STAGED_UNKNOWN_KINGDOM", "T_NOT_ANYWHERE", ""]
    got = non_invertebrate_tvks(tvks, obs, uksi)
    assert got == {"T_ORCHID", "T_WREN", "T_NEWT", "T_FUNGUS", "T_NOGROUP", "T_BLANK",
                   "T_STAGED_PLANT", "T_STAGED_FROG"}
    assert {"T_BEE", "T_EARWIG_AGG", "T_STAGED_BEETLE", "T_STAGED_UNKNOWN_KINGDOM",
            "T_NOT_ANYWHERE"}.isdisjoint(got)


def test_observations_without_the_columns_fall_back_to_uksi(tmp_path, dbs):
    _, uksi = dbs
    bare = _db(tmp_path / "bare.db", "CREATE TABLE observations (id INTEGER, record_type TEXT)",
               [], "observations")
    assert non_invertebrate_tvks(["T_ORCHID", "T_BEE"], bare, uksi) == {"T_ORCHID"}


def test_nothing_readable_leaves_everything_counted(tmp_path):
    assert non_invertebrate_tvks(["A", "B"], tmp_path / "no.db", tmp_path / "no2.db") == set()
    assert non_invertebrate_tvks([], tmp_path / "no.db") == set()


def test_vertebrate_groups():
    for g in ("bird", "Terrestrial mammal", "marine mammal", "amphibian", "reptile",
              "bony fish (Actinopterygii)", "cartilaginous fish (Chondrichthyes)"):
        assert is_vertebrate_group(g), g
    for g in ("insect - earwig (Dermaptera)", "insect - silverfish (Thysanura)", "spider (Araneae)",
              "mollusc", "", None):
        assert not is_vertebrate_group(g), g


def test_workbook_basis_line():
    from types import SimpleNamespace
    from Examen.workbook_export import _not_counted_line
    assert _not_counted_line(SimpleNamespace(non_invertebrates={})) == []
    assert _not_counted_line(SimpleNamespace(non_invertebrates={"a": "Pica pica", "b": "Ballota nigra"})) \
        == [("Not counted", "2 non-invertebrate taxa recorded incidentally are not counted: "
                            "Ballota nigra, Pica pica.")]
    assert _not_counted_line(SimpleNamespace(non_invertebrates={"a": "Pica pica"}))[0][1] \
        == "1 non-invertebrate taxon recorded incidentally is not counted: Pica pica."
