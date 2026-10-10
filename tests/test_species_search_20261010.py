"""The shared species search (backlog item 1, review SRCH15-19, OBS-09, CDX-2; 10 Oct 2026).

shared/species_search.py against the real data/uksi.db (read-only), shared/species_filter.py
against a small temporary record table, the ranking rules in shared/species_rank.py, timing,
and the boxes that use it, built offscreen.
"""
import os
import sqlite3
import time

import pytest

import paths

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytestmark = pytest.mark.skipif(not paths.UKSI_DB.exists(), reason="needs data/uksi.db")


@pytest.fixture(scope="module")
def idx():
    from shared.species_search import get_index
    return get_index()


def first(idx, text, **kw):
    r = idx.search(text, **kw)
    return r[0] if r else None


# ---------------------------------------------------------------- matching

def test_typing_slip(idx):
    r = first(idx, "Rhagium mordx")
    assert r["scientific_name"] == "Rhagium mordax" and r["match_type"] == "fuzzy"
    assert first(idx, "Rutpela maculta")["scientific_name"] == "Rutpela maculata"
    assert first(idx, "Lucanus cervis")["scientific_name"] == "Lucanus cervus"
    # a swap of two neighbouring letters is one slip
    assert first(idx, "Rhagium modrax")["scientific_name"] == "Rhagium mordax"


def test_every_word_any_order(idx):
    for text in ("rhag mor", "mor rhag", "agium mord", "RHAGIUM   MORDAX"):
        assert first(idx, text)["scientific_name"] == "Rhagium mordax", text


def test_old_name_gives_current_taxon(idx):
    r = first(idx, "Strangalia maculata")
    assert r["scientific_name"] == "Rutpela maculata"
    assert r["old_name"] == "Strangalia maculata" and r["matched_kind"] == "synonym"


def test_common_names_from_uksi(idx):
    assert first(idx, "spotted longhorn")["scientific_name"] == "Anoplodera sexguttata"
    assert first(idx, "Stag Beetle")["scientific_name"] == "Lucanus cervus"
    assert first(idx, "common burying")["scientific_name"] == "Nicrophorus vespillo"


def test_exact_name_first(idx):
    names = [r["scientific_name"] for r in idx.search("Nicrophorus vespillo")]
    assert names[:2] == ["Nicrophorus vespillo", "Nicrophorus vespilloides"]
    assert first(idx, "N. vespillo")["scientific_name"] == "Nicrophorus vespillo"
    assert first(idx, "Rhagium")["rank"] == "Genus"


def test_species_before_higher_ranks(idx):
    r = idx.search("rhagium", limit=10)
    groups = [x["rank"] for x in r[1:4]]
    assert all(g == "Species" for g in groups)


def test_qualifiers(idx):
    agg = first(idx, "Bombus lucorum agg.")
    assert agg["rank"] in ("Species sensu lato", "Species aggregate")
    assert first(idx, "Bombus lucorum")["rank"] == "Species"
    assert first(idx, "cf. Rhagium mordax")["scientific_name"] == "Rhagium mordax"
    assert first(idx, "Rhagium cf mordax")["scientific_name"] == "Rhagium mordax"
    assert first(idx, "Rhagium sp.")["rank"] == "Genus"


def test_every_agg_taxon_findable(idx):
    """SRCH16: one of the two old searches could find none of UKSI's 155 'agg.' taxa."""
    conn = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
    rows = conn.execute("SELECT t.tvk, t.scientific_name, q.label FROM taxa t JOIN "
                        "taxon_qualifiers q ON q.tvk = t.tvk WHERE q.qualifier = 'agg.'").fetchall()
    conn.close()
    assert len(rows) >= 150
    missing = [n for tvk, n, label in rows
               if tvk not in {r["tvk"] for r in idx.search(label or n, limit=10)}]
    assert missing == []


def test_punctuation_accents_apostrophes(idx):
    a = [r["tvk"] for r in idx.search("Altenhofer’s elm")]
    b = [r["tvk"] for r in idx.search("Altenhofer's elm")]
    c = [r["tvk"] for r in idx.search("altenhofers elm")]
    assert a == b == c and a
    r = first(idx, "Meyenia mulleri")
    assert "llleri" not in r["scientific_name"] and r["match_type"] != "fuzzy"
    assert "ü" in r["scientific_name"]                        # mülleri
    assert first(idx, "6 spotted longhorn")["scientific_name"] == "Anoplodera sexguttata"


def test_ranks_filter(idx):
    from shared.species_search import SPECIES_LEVEL
    assert all(r["rank"] in SPECIES_LEVEL for r in idx.search("rhagium", ranks=SPECIES_LEVEL))
    assert idx.search("x") == []


def test_tvk_for_name(idx):
    assert idx.tvk_for_name("Rutpela maculata") == "NHMSYS0020109270"
    assert idx.tvk_for_name("Strangalia maculata") == "NHMSYS0020109270"
    assert idx.tvk_for_name("No such beast") is None


def test_speed(idx):
    """Under 100 ms a keystroke on the full UKSI (measured here 1-60 ms; build ~1.4 s)."""
    worst = 0.0
    for text in ("ra", "ab", "rhag mor", "Rhagium mordx", "Spotted Longhorn", "N. vespillo",
                 "Strangalia maculata", "ina", "a b", "pterostichs madidu", "beetle"):
        t = time.perf_counter()
        idx.search(text, limit=50)
        worst = max(worst, time.perf_counter() - t)
    assert worst < 0.25        # generous for a slow PC; report the real figure, not this


# ---------------------------------------------------------------- ranking rules

def test_rank_and_resolve(idx):
    from shared.species_rank import rank_matches, resolve_name
    res = idx.search("Rhagium mordx")
    assert resolve_name("Rhagium mordx", res, interactive=True)[0] == "pick"
    assert resolve_name("Rhagium mordx", res, interactive=False)[0] == "unresolved"
    res = idx.search("Strangalia maculata")
    action, hit = resolve_name("Strangalia maculata", res, interactive=False)
    assert action == "fill" and hit["scientific_name"] == "Rutpela maculata"
    # the matcher's order is kept; an alias without a key goes last
    mixed = res + [{"scientific_name": "Aaa", "tvk": "X"}]
    assert rank_matches("x", mixed)[-1]["tvk"] == "X"


def test_import_lookup_still_exact():
    """Imports never take a close spelling: species_lookup is unchanged."""
    from shared.species_lookup import LookupFailure, lookup_names
    conn = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
    r = lookup_names(["Rhagium mordx"], conn)["Rhagium mordx"]
    conn.close()
    assert isinstance(r, LookupFailure)


# ---------------------------------------------------------------- record filters

@pytest.fixture()
def records():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE recs (id INTEGER, species_name TEXT, species_tvk TEXT, "
                 "common_name TEXT)")
    rows = [
        (1, "Anoplodera sexguttata", "NHMSYS0020151259", None),           # no common name
        (2, "Anoplodera sexguttata", "NHMSYS0020151259", "6-spotted Longhorn"),
        (3, "Rhagium mordax", "NBNSYS0000011004", None),
        (4, "Nicrophorus vespillo", "NBNSYS0000023039", None),
        (5, "Nicrophorus vespilloides", "NBNSYS0000023040", None),
        (6, "Rhagium mordax", None, None),                                 # no TVK
        (7, "Rhagium bifasciatum", "NBNSYS0000011002", None),
        (8, "Strangalia maculata", "NHMSYS0020109270", None),               # an old name
        (9, "Mystery beetle", "ZZZ0000000001", None),                       # TVK not in UKSI
    ]
    conn.executemany("INSERT INTO recs VALUES (?,?,?,?)", rows)
    return conn


def ids(conn, text):
    from shared.species_filter import sql_for_table
    clause, params = sql_for_table(text, lambda q, p=(): conn.execute(q, p).fetchall(), "recs")
    return sorted(r[0] for r in conn.execute(f"SELECT id FROM recs WHERE {clause}", params))


def test_filter_by_tvk(records):
    assert ids(records, "Spotted Longhorn") == [1, 2]       # SRCH17: not only the named row
    assert ids(records, "rhag mor") == [3, 6]                # the no-TVK row by name
    assert ids(records, "Rhagium mordx") == [3]              # a slip; the no-TVK row has no 'mordx'
    assert ids(records, "Nicrophorus vespillo") == [4]       # OBS-09: exact, not vespilloides
    assert ids(records, "N. vespillo") == [4]
    assert ids(records, "Nicrophorus vesp") == [4, 5]
    assert ids(records, "Rhagium") == [3, 6, 7]              # a genus takes its species
    assert ids(records, "Cerambycidae") == [1, 2, 3, 7, 8]
    assert ids(records, "Rutpela maculata") == [8]           # stored under its old name
    assert ids(records, "Mystery") == [9]                    # unknown TVK: by name
    assert ids(records, "y") == [9]                          # 1 letter: by name, as before


def test_filter_in_memory_and_names(records):
    from shared.species_filter import filter_names, species_filter
    rows = records.execute("SELECT id, species_tvk, species_name, common_name FROM recs").fetchall()
    sf = species_filter("Spotted Longhorn", {r[1] for r in rows if r[1]})
    assert [r[0] for r in rows if sf.matches(r[1], r[2], r[3])] == [1, 2]
    names = ["Rhagium mordax", "Strangalia maculata", "Nicrophorus vespillo",
             "Nicrophorus vespilloides"]
    assert filter_names("Rutpela maculata", names) == {"Strangalia maculata"}
    assert filter_names("N. vespillo", names) == {"Nicrophorus vespillo"}
    assert filter_names("rhag mor", names) == {"Rhagium mordax"}


# ---------------------------------------------------------------- the boxes

@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_species_search_widget(app):
    from src.views.components.species_search import SpeciesSearch
    w = SpeciesSearch()
    w.search_input.setText("Strangalia maculata")
    w._do_search()
    assert w._popup.count() >= 1
    assert "old name: Strangalia maculata" in w._popup.item(0).text()
    w._select_item(w._popup.item(0))
    assert w.get_selected_tvk() == "NHMSYS0020109270"


def test_wizard_species_completer(app):
    from PySide6.QtWidgets import QLineEdit
    from src.views.components.filter_wizard.fuzzy import SpeciesCompleter
    items = ["Common Burying Beetle (Nicrophorus vespillo)", "Nicrophorus vespilloides",
             "Rhagium mordax"]
    edit = QLineEdit()
    sc = SpeciesCompleter(items, edit,
                          names={items[0]: "Nicrophorus vespillo", items[1]: items[1],
                                 items[2]: items[2]})
    pm = sc._proxy_model

    def shown(text):
        sc.splitPath(text)
        return [pm.data(pm.index(i, 0)) for i in range(pm.rowCount())]
    assert shown("Rhagium mordx") == ["Rhagium mordax"]
    assert shown("rhag mor") == ["Rhagium mordax"]
    assert shown("burying") == [items[0]]


def test_codex_species_tab(app):
    from PySide6.QtWidgets import QLabel
    from Codex.species_tab import SpeciesTab
    tab = SpeciesTab()
    tab.search_input.setText("Strangalia maculata")
    tab._do_search()
    texts = [lbl.text() for lbl in tab.results_frame.findChildren(QLabel)]
    assert any("Rutpela maculata" in t for t in texts)
    tab.search_input.setText("Cerambycidae")      # CDX-2: ranks above species are found
    tab._do_search()
    texts = [lbl.text() for lbl in tab.results_frame.findChildren(QLabel)]
    assert any("Cerambycidae" in t for t in texts)


def test_examen_species_database_search():
    from Examen.species_database_view import SpeciesDatabaseView
    view = SpeciesDatabaseView.__new__(SpeciesDatabaseView)
    hits = SpeciesDatabaseView._search_uksi(view, "Rhagium mordx")
    assert hits[0][0] == "Rhagium mordax" and hits[0][5] == "close spelling"
    assert SpeciesDatabaseView._search_uksi(view, "stag beetle")[0][0] == "Lucanus cervus"
