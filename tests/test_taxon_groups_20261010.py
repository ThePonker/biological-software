"""One taxon grouping across the suite (backlog item 3; review SRCH14 / MAP10 / OBS-11 / IMP-10 /
OBS-16, 10 Oct 2026): shared/taxon_groups.py, its users, and scripts/backfill_taxon_groups.py.
Small temp databases, or the data copies read-only; no display needed."""
import importlib.util
import os
import sqlite3
from types import SimpleNamespace

import pytest

from shared import taxon_groups as tg
from shared.taxon_groups import (BUTTERFLY, MOTH, display_labels, fill_blank_groups, group_filter_sql,
                                 group_for_record, group_label, group_sql, group_values,
                                 merge_curve_groups, taxon_group)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


# ---------------------------------------------------------------- the rule
@pytest.mark.parametrize("order, family, cls, kingdom, phylum, group", [
    ("Lepidoptera", "Nymphalidae", "Insecta", "Animalia", "Arthropoda", BUTTERFLY),
    ("Lepidoptera", "Noctuidae", "Insecta", "Animalia", "Arthropoda", MOTH),
    ("Carnivora", "Phocidae", "Mammalia", "Animalia", "Chordata", "marine mammal"),
    ("Carnivora", "Mustelidae", "Mammalia", "Animalia", "Chordata", "terrestrial mammal"),
    ("Raphidioptera", "Raphidiidae", "Insecta", "Animalia", "Arthropoda", "insect - snakefly (Raphidioptera)"),
    ("Zygentoma", "Lepismatidae", "Insecta", "Animalia", "Arthropoda", "insect - silverfish (Thysanura)"),
    ("Trombidiformes", None, "Arachnida", "Animalia", "Arthropoda", "acarine (Acari)"),
    ("", None, "Arachnida", "Animalia", "Arthropoda", None),          # not guessed as a spider
    ("Equisetales", None, "Polypodiopsida", "Plantae", None, "horsetail"),
    ("Polypodiales", None, "Polypodiopsida", "Plantae", None, "fern"),
    ("Actiniaria", None, "Anthozoa", "Animalia", "Cnidaria", "coelenterate (=cnidarian)"),   # phylum
    ("Teloschistales", None, "Lecanoromycetes", "Fungi", "Ascomycota", "lichen"),
    ("Pezizales", None, "Pezizomycetes", "Fungi", "Ascomycota", "fungus"),                  # kingdom
])
def test_rule(order, family, cls, kingdom, phylum, group):
    assert taxon_group(order, family, cls, kingdom, phylum) == group


def test_irecord_labels_on_record_agree_with_ours():
    """Every label the rule gives for an order seen on iRecord records is iRecord's own
    spelling (10 Oct 2026: no iRecord record with an order disagrees)."""
    db = os.path.join(DATA, "observatum.db")
    uksi = os.path.join(DATA, "uksi.db")
    if not (os.path.exists(db) and os.path.exists(uksi)):
        pytest.skip("data copies not present")
    o = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = o.execute("SELECT species_tvk, taxon_group FROM observations "
                     "WHERE source LIKE 'iRecord%' AND COALESCE(taxon_group,'') <> ''").fetchall()
    o.close()
    info = tg.taxonomy_for_tvks({t for t, _ in rows}, uksi)
    differ = {(g, info[t]["taxon_group"]) for t, g in rows
              if t in info and info[t]["taxon_group"] and info[t]["taxon_group"] != g}
    assert differ == set()


# ---------------------------------------------------------------- display labels
OLD_LABEL_MAP = {     # the dashboards' copy, 9 Oct 2026 (three identical copies)
    'insect - beetle (Coleoptera)': 'Beetles (Coleoptera)', 'insect - moth': 'Moths (Lepidoptera)',
    'insect - butterfly': 'Butterflies (Lepidoptera)', 'insect - true fly (Diptera)': 'True Flies (Diptera)',
    'bird': 'Birds (Aves)', 'insect - hymenopteran': 'Bees, Wasps & Ants (Hymenoptera)',
    'spider (Araneae)': 'Spiders (Araneae)', 'insect - true bug (Hemiptera)': 'True Bugs (Hemiptera)',
    'mollusc': 'Molluscs (Mollusca)', 'insect - dragonfly (Odonata)': 'Dragonflies (Odonata)',
    'harvestman (Opiliones)': 'Harvestmen (Opiliones)', 'crustacean': 'Crustaceans (Crustacea)',
    'annelid': 'Annelids (Annelida)', 'insect - orthopteran': 'Grasshoppers & Crickets (Orthoptera)',
    'millipede': 'Millipedes (Diplopoda)', 'amphibian': 'Amphibians (Amphibia)',
    'false scorpion (Pseudoscorpiones)': 'False Scorpions (Pseudoscorpiones)',
    'centipede': 'Centipedes (Chilopoda)', 'reptile': 'Reptiles (Reptilia)',
    'bony fish (Actinopterygii)': 'Fish (Actinopterygii)',
    'insect - scorpion fly (Mecoptera)': 'Scorpion Flies (Mecoptera)', 'moss': 'Mosses (Bryophyta)',
    'springtail (Collembola)': 'Springtails (Collembola)', 'acarine (Acari)': 'Mites (Acari)',
    'chromist': 'Chromists (Chromista)', 'coelenterate (=cnidarian)': 'Cnidarians (Cnidaria)',
    'insect - caddis fly (Trichoptera)': 'Caddisflies (Trichoptera)',
    'insect - earwig (Dermaptera)': 'Earwigs (Dermaptera)',
    'insect - snakefly (Raphidioptera)': 'Snakeflies (Raphidioptera)',
    'insect - thrips (Thysanoptera)': 'Thrips (Thysanoptera)', 'insect - flea (Siphonaptera)': 'Fleas (Siphonaptera)',
    'insect - lacewing (Neuroptera)': 'Lacewings (Neuroptera)', 'alga': 'Algae', 'lichen': 'Lichens',
    'flatworm (Turbellaria)': 'Flatworms (Turbellaria)', 'scorpion': 'Scorpions (Scorpiones)',
}
OLD_MERGES = {'Plants (Plantae)': ['flowering plant', 'fern', 'conifer', 'horsetail'],
              'Fungi': ['fungus', 'slime mould'],
              'Mammals (Mammalia)': ['terrestrial mammal', 'marine mammal']}


def test_curve_labels_unchanged_for_every_old_label():
    for value, label in OLD_LABEL_MAP.items():
        assert group_label(value) == label
    for label, members in OLD_MERGES.items():
        for m in members:
            assert group_label(m) == label
        assert group_values(label) == members
    assert group_label("undetermined") == "Undetermined"        # unknown: title case, as before


def test_merge_curve_groups():
    raw = {"insect - beetle (Coleoptera)": {"species_count": 3, "yearly_new": {2020: 2, 2021: 1}},
           "fern": {"species_count": 1, "yearly_new": {2020: 1}},
           "flowering plant": {"species_count": 2, "yearly_new": {2021: 2}}}
    data, groups = merge_curve_groups(raw)
    assert data["Plants (Plantae)"] == {"species_count": 3, "yearly_new": {2020: 1, 2021: 2}}
    assert sorted(groups["Plants (Plantae)"]) == ["fern", "flowering plant"]
    assert groups["Beetles (Coleoptera)"] == ["insect - beetle (Coleoptera)"]


def test_display_labels_order_and_inverse():
    labels = display_labels()
    assert labels[:2] == ["Beetles (Coleoptera)", "True Flies (Diptera)"]
    assert len(labels) == len(set(labels))
    present = display_labels(["spider (Araneae)", "insect - beetle (Coleoptera)", "fern", "", None,
                              "undetermined"])
    assert present == ["Beetles (Coleoptera)", "Spiders (Araneae)", "Plants (Plantae)", "Undetermined"]
    for lab in labels:
        assert all(group_label(v) == lab for v in group_values(lab))
    assert group_values("Undetermined", known=["undetermined"]) == ["undetermined"]


# ---------------------------------------------------------------- SQL helper
@pytest.fixture
def recs():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE r (id INTEGER PRIMARY KEY, taxon_group TEXT, order_name TEXT, "
              "family TEXT, kingdom TEXT)")
    c.executemany("INSERT INTO r VALUES (?,?,?,?,?)", [
        (1, "insect - beetle (Coleoptera)", "Coleoptera", "Carabidae", "Animalia"),
        (2, None, "Coleoptera", "Cerambycidae", "Animalia"),          # Data Entry commit, blank
        (3, "  ", "Lepidoptera", "Pieridae", "Animalia"),             # blank -> butterfly
        (4, "insect - moth", "Lepidoptera", "Pieridae", "Animalia"),  # stored label wins
        (5, "", "Polypodiales", None, "Plantae"),                     # class fallback not in SQL
        (6, None, "Pezizales", None, "Fungi"),                        # kingdom fallback
        (7, "fern", "Polypodiales", None, "Plantae"),
    ])
    return c


def test_group_sql_stored_label_then_order_family(recs):
    got = dict(recs.execute(f"SELECT id, {group_sql(kingdom_col='kingdom')} FROM r"))
    assert got == {1: "insect - beetle (Coleoptera)", 2: "insect - beetle (Coleoptera)",
                   3: BUTTERFLY, 4: MOTH, 5: None, 6: "fungus", 7: "fern"}
    # Python twin agrees
    for rid, stored, order, fam, kingdom in recs.execute("SELECT * FROM r"):
        assert group_for_record(stored, order, fam, kingdom) == got[rid] or rid == 5


def test_group_filter_sql(recs):
    def ids(labels, **kw):
        sql, params = group_filter_sql(labels, **kw)
        return sorted(r[0] for r in recs.execute(f"SELECT id FROM r WHERE {sql}", params))
    assert ids(["Beetles (Coleoptera)"]) == [1, 2]
    assert ids(["Butterflies (Lepidoptera)", "Moths (Lepidoptera)"]) == [3, 4]
    assert ids(["Plants (Plantae)"]) == [7]
    assert ids(["Fungi"], kingdom_col="kingdom") == [6]
    assert ids(["insect - beetle (Coleoptera)"]) == [1, 2]          # raw value works too
    assert ids([]) == [] and ids(["No such group"]) == []
    sql, _ = group_filter_sql(["Beetles (Coleoptera)"], group_col="o.taxon_group",
                              order_col="o.order_name", family_col="o.family")
    assert "o.taxon_group" in sql and "o.order_name" in sql


# ---------------------------------------------------------------- import rows (IMP-10)
def test_fill_blank_groups_keeps_labels_fills_blanks():
    rows = [SimpleNamespace(species_tvk="B1", taxon_group="", kingdom="", order_name="", family=""),
            SimpleNamespace(species_tvk="B1", taxon_group="insect - beetle (Coleoptera)", kingdom=""),
            SimpleNamespace(species_tvk="", taxon_group=None, order_name="Lepidoptera",
                            family="Pieridae"),
            SimpleNamespace(species_tvk="X", taxon_group="", order_name="", family="")]
    tax = {"B1": {"taxon_group": "insect - beetle (Coleoptera)", "kingdom": "Animalia"}}
    assert fill_blank_groups(rows, taxonomy=tax) == 2
    assert rows[0].taxon_group == "insect - beetle (Coleoptera)" and rows[0].kingdom == "Animalia"
    assert rows[1].kingdom == "Animalia"
    assert rows[2].taxon_group == BUTTERFLY
    assert rows[3].taxon_group == ""                 # nothing known: left blank


def test_apply_confirmed_sets_the_new_species_group():
    import enum

    from shared.species_lookup_entries import apply_confirmed

    class Status(enum.Enum):
        ERROR, WARNING, VALID = "e", "w", "v"
    row = SimpleNamespace(species_name="Pieris rapae x", species_tvk="", common_name="", order_name="",
                          family="", kingdom="", taxon_group="insect - beetle (Coleoptera)",
                          import_notes="", status=Status.ERROR, error_message="Species not found",
                          warnings=[])
    apply_confirmed(row, {"scientific_name": "Pieris rapae", "tvk": "P2", "order_name": "Lepidoptera",
                          "family": "Pieridae", "kingdom": "Animalia"}, "Pieris rapae x")
    assert row.taxon_group == BUTTERFLY and row.species_tvk == "P2"


# ---------------------------------------------------------------- UKSI lookup + backfill
@pytest.fixture
def dbs(tmp_path):
    u = sqlite3.connect(tmp_path / "uksi.db")
    u.execute('CREATE TABLE taxa (tvk TEXT, scientific_name TEXT, rank TEXT, parent_tvk TEXT, '
              'kingdom TEXT, phylum TEXT, class TEXT, "order" TEXT, family TEXT, sort_code INTEGER, '
              'superfamily TEXT)')
    u.executemany("INSERT INTO taxa VALUES (?,?,?,?,?,?,?,?,?,?,?)", [
        ("B1", "Carabus nemoralis", "Species", None, "Animalia", "Arthropoda", "Insecta", "Coleoptera",
         "Carabidae", 18000, "Caraboidea"),
        ("P1", "Anthocharis cardamines", "Species", None, "Animalia", "Arthropoda", "Insecta",
         "Lepidoptera", "Pieridae", 45000, "Papilionoidea"),
        ("R1", "Xanthostigma xanthostigma", "Species", None, "Animalia", "Arthropoda", "Insecta",
         "Raphidioptera", "Raphidiidae", 100, None),
        ("A1", "Actinia equina", "Species", None, "Animalia", "Cnidaria", "Anthozoa", "Actiniaria",
         "Actiniidae", 10, None),
    ])
    u.commit()
    u.close()
    o = sqlite3.connect(tmp_path / "observatum.db")
    o.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, species_tvk TEXT, source TEXT, "
              "order_name TEXT, taxon_group TEXT, kingdom TEXT, taxon_rank TEXT, superfamily TEXT, "
              "taxonomic_sort_key)")
    o.execute("CREATE TABLE recording_scheme (id INTEGER PRIMARY KEY, species_tvk TEXT, source TEXT, "
              "order_name TEXT, taxon_group TEXT, kingdom TEXT)")
    o.execute("CREATE TABLE specimens (id INTEGER PRIMARY KEY, species_tvk TEXT, order_name TEXT, "
              "taxon_group TEXT, superfamily TEXT, taxonomic_sort_key)")
    o.executemany("INSERT INTO observations (id, species_tvk, source, order_name, taxon_group, kingdom, "
                  "taxonomic_sort_key) VALUES (?,?,?,?,?,?,?)", [
                      (1, "B1", None, "Coleoptera", None, None, None),           # DE commit: fill
                      (2, "P1", None, "Lepidoptera", "insect - moth", "Animalia", 5),  # ours, wrong
                      (3, "P1", "iRecord | iRecord App", "Lepidoptera", "insect - moth", "Animalia", 5),
                      (4, "ZZ", None, None, None, None, None),                   # not in UKSI
                      (5, "A1", None, "Actiniaria", "", None, 7),                # phylum fallback
                  ])
    o.executemany("INSERT INTO recording_scheme VALUES (?,?,?,?,?,?)", [
        (1, "B1", "Cerambycidae Dataset", "Coleoptera", None, "Animalia"),
        (2, "R1", "Some NBN dataset", "Raphidioptera", "insect", "Animalia"),     # theirs: kept
    ])
    o.executemany("INSERT INTO specimens VALUES (?,?,?,?,?,?)", [
        (1, "R1", "Raphidioptera", "insect", None, 1),
        (2, "B1", "Coleoptera", None, "Caraboidea", 2),
        (3, None, None, None, None, None),
    ])
    o.commit()
    return o, str(tmp_path / "uksi.db"), tmp_path


def _script():
    path = os.path.join(ROOT, "scripts", "backfill_taxon_groups.py")
    spec = importlib.util.spec_from_file_location("backfill_taxon_groups", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_taxonomy_for_tvks_uses_phylum(dbs):
    _, uksi, _ = dbs
    info = tg.taxonomy_for_tvks(["B1", "A1", "nope"], uksi)
    assert set(info) == {"B1", "A1"}
    assert info["A1"]["taxon_group"] == "coelenterate (=cnidarian)"
    assert info["B1"]["taxonomic_sort_key"] == 19018000 and info["B1"]["superfamily"] == "Caraboidea"


def test_backfill_plan_fills_blanks_and_lists(dbs):
    conn, uksi, _ = dbs
    m = _script()
    found = m.plan(conn, uksi)
    obs = found["observations"]
    fill = {c: {rid: new for rid, new, _ in items} for c, items in obs["fill"].items()}
    assert fill["taxon_group"] == {1: "insect - beetle (Coleoptera)", 5: "coelenterate (=cnidarian)"}
    assert fill["kingdom"] == {1: "Animalia", 5: "Animalia"}
    assert fill["taxonomic_sort_key"] == {1: 19018000}                 # only the NULL key
    assert obs["relabel"] == [(2, "insect - moth", BUTTERFLY)]          # ours only, not id 3
    assert obs["differ"] == {("Lepidoptera", "insect - moth", BUTTERFLY): 1}
    assert obs["not_in_uksi"] == 1
    sch = found["recording_scheme"]
    assert [rid for rid, _, _ in sch["fill"]["taxon_group"]] == [1]
    assert sch["relabel"] == [] and sum(sch["differ"].values()) == 1    # scheme: never relabelled
    spe = found["specimens"]
    assert [rid for rid, _, _ in spe["fill"]["taxon_group"]] == [2]
    assert spe["relabel"] == [(1, "insect", "insect - snakefly (Raphidioptera)")]
    assert spe["no_tvk"] == 1


def test_backfill_apply_and_main(dbs, capsys):
    conn, uksi, tmp = dbs
    m = _script()
    db = str(tmp / "observatum.db")
    conn.close()
    assert m.main(["--db", db, "--uksi", uksi]) == 0                     # dry run
    out = capsys.readouterr().out
    assert "Nothing has been changed" in out and "1  insect - beetle (Coleoptera)" in out
    c = sqlite3.connect(db)
    assert c.execute("SELECT taxon_group FROM observations WHERE id=1").fetchone()[0] is None
    c.close()

    assert m.main(["--db", db, "--uksi", uksi, "--apply", "--backup-dir", str(tmp / "bk")]) == 0
    assert len(os.listdir(tmp / "bk")) == 1
    c = sqlite3.connect(db)
    g = dict(c.execute("SELECT id, taxon_group FROM observations"))
    assert g[1] == "insect - beetle (Coleoptera)" and g[5] == "coelenterate (=cnidarian)"
    assert g[2] == "insect - moth" and g[3] == "insect - moth"          # no --relabel: unchanged
    assert c.execute("SELECT taxon_group FROM recording_scheme WHERE id=2").fetchone()[0] == "insect"
    c.close()

    assert m.main(["--db", db, "--uksi", uksi, "--apply", "--relabel",
                   "--backup-dir", str(tmp / "bk")]) == 0
    c = sqlite3.connect(db)
    g = dict(c.execute("SELECT id, taxon_group FROM observations"))
    assert g[2] == BUTTERFLY and g[3] == "insect - moth"                # iRecord's label kept
    assert c.execute("SELECT taxon_group FROM specimens WHERE id=1").fetchone()[0] == \
        "insect - snakefly (Raphidioptera)"
    assert c.execute("SELECT taxon_group FROM recording_scheme WHERE id=2").fetchone()[0] == "insect"
    c.close()
    after = m.plan(sqlite3.connect(db), uksi)
    assert not any(v for t in after.values() for v in t["fill"].values())
    assert not any(t["relabel"] for t in after.values())


# ---------------------------------------------------------------- Stats curves (MAP10 / OBS-11)
def test_stats_curves_count_blank_groups_like_the_order_table():
    """Commercial Beetles read 552 against Coleoptera 651 while Data Entry commits had no group.
    With the group from order/family for a blank label they agree -- checked on the data copy
    with every Data Entry-style record's label blanked again (in a TEMP shadow table)."""
    db = os.path.join(DATA, "observatum.db")
    if not os.path.exists(db):
        pytest.skip("data copy not present")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from src.services.observation_stats_service import ObservationStatsService

    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TEMP TABLE observations AS SELECT * FROM main.observations")
    conn.execute("UPDATE temp.observations SET taxon_group = NULL WHERE source IS NULL")

    class DB:
        def execute_main(self, q, params=()):
            return conn.execute(q, params).fetchall()

    svc = ObservationStatsService()
    saved = (svc._db, svc._cache)
    try:
        svc._db, svc._cache = DB(), {}
        svc._refresh()
        c = svc._cache
        orders = {o["label"]: o["species"] for o in c["commercial_species_by_order"]}
        curve = c["commercial_order_curve_raw"]
        assert curve["insect - beetle (Coleoptera)"]["species_count"] == orders["Coleoptera"]
        assert curve["insect - true fly (Diptera)"]["species_count"] == orders["Diptera"]
        assert curve["spider (Araneae)"]["species_count"] == orders["Araneae"]
    finally:
        svc._db, svc._cache = saved
        conn.close()
