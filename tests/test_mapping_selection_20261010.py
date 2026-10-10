"""Mapping selection (backlog item 4; review SRCH18, MAP1-8, MAP13, MAP14), 10 Oct 2026.

Service figures are checked against hand SQL on the data copies (read-only); the pure parts
on small made-up records; the tab is built offscreen and driven.
"""
import datetime as dt
import os
import sqlite3
import time

import pytest

import paths
from shared.import_core import date_bounds

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HAVE_DATA = paths.OBSERVATUM_DB.exists() and paths.UKSI_DB.exists()
needs_data = pytest.mark.skipif(not HAVE_DATA, reason="needs data/observatum.db and uksi.db")
TODAY = dt.date.today().isoformat()
EMB = f"(COALESCE(embargo_status,'')='Active' AND COALESCE(embargo_until,'') > '{TODAY}')"
GRID = "COALESCE(grid_ref,'') <> ''"
PERSONAL = "LOWER(COALESCE(record_type,'')) NOT LIKE 'comm%'"
SPEC_OBS = ("(o.id = s.observation_id OR (s.observation_id IS NULL AND o.species_tvk = s.species_tvk"
            " AND o.date = s.date_collected AND REPLACE(UPPER(o.grid_ref),' ','') = "
            "REPLACE(UPPER(s.grid_ref),' ','')))")


def sql1(q):
    conn = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
    try:
        return conn.execute(q).fetchone()[0]
    finally:
        conn.close()


@pytest.fixture(scope="module")
def ms():
    from src.services import map_selection
    return map_selection


@pytest.fixture(scope="module")
def taxa():
    from src.services import map_taxa
    return map_taxa


def fetch(ms, sel, src, **kw):
    return ms.fetch(sel, src, ms.MapFilters(**kw))


def chip(taxa, text, rank="species"):
    return taxa.search_taxa(text, rank)[0]


# ---------------------------------------------------------------- sources and embargo (MAP1)

@needs_data
def test_source_split_matches_sql(ms):
    assert len(fetch(ms, [], "personal").records) == sql1(
        f"SELECT COUNT(*) FROM observations WHERE {GRID} AND {PERSONAL} AND NOT {EMB}")
    com = fetch(ms, [], "commercial")
    assert len(com.records) == sql1(
        f"SELECT COUNT(*) FROM observations WHERE {GRID} AND NOT {PERSONAL} AND NOT {EMB}")
    assert com.embargoed == sql1(f"SELECT COUNT(*) FROM observations WHERE {GRID} AND {EMB}")
    assert len(fetch(ms, [], "scheme").records) == sql1(f"SELECT COUNT(*) FROM recording_scheme WHERE {GRID}")
    assert len(fetch(ms, [], "contributed").records) == sql1(
        f"SELECT COUNT(*) FROM contributed_observations WHERE {GRID}")
    inc = fetch(ms, [], "commercial", include_embargoed=True)
    assert len(inc.records) == len(com.records) + com.embargoed


@needs_data
def test_embargoed_never_on_personal_or_all(ms):
    emb_ids = set()
    conn = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
    emb_ids = {r[0] for r in conn.execute(f"SELECT id FROM observations WHERE {EMB}")}
    conn.close()
    assert emb_ids, "the data copy has embargoed records (4,586 on 9 Oct)"
    for src in ("personal", "commercial", "all"):
        ids = {r["id"] for r in fetch(ms, [], src).records if r["table"] == "observations"}
        assert not ids & emb_ids, src
    # a specimen whose observation is embargoed is held back with it
    held = sql1(f"SELECT COUNT(*) FROM specimens s WHERE {GRID.replace('grid_ref', 's.grid_ref')} AND EXISTS "
                f"(SELECT 1 FROM observations o WHERE {SPEC_OBS} AND "
                f"{EMB.replace('embargo_', 'o.embargo_')})")
    col = fetch(ms, [], "collection")
    assert col.embargoed == held
    assert len(col.records) == sql1(f"SELECT COUNT(*) FROM specimens WHERE {GRID}") - held


@needs_data
def test_all_shows_each_record_once(ms):
    """MAP2: a specimen with its own observation is the observation; scheme rows that are
    your observations (same iRecord id) likewise."""
    res = fetch(ms, [], "all")
    by_table = {}
    for r in res.records:
        by_table[r["table"]] = by_table.get(r["table"], 0) + 1
    dup_spec = sql1(f"SELECT COUNT(*) FROM specimens s WHERE EXISTS (SELECT 1 FROM observations o "
                    f"WHERE {SPEC_OBS})")
    assert dup_spec > 1000                     # 1,339 on the 9 Oct copy (review: 1,337)
    assert by_table["specimens"] == sql1("SELECT COUNT(*) FROM specimens WHERE COALESCE(grid_ref,'')<>''") - dup_spec
    dup_rs = sql1("SELECT COUNT(*) FROM recording_scheme WHERE COALESCE(irecord_id,'')<>'' AND "
                  "COALESCE(grid_ref,'')<>'' AND irecord_id IN (SELECT irecord_id FROM observations "
                  f"WHERE COALESCE(irecord_id,'')<>'' AND NOT {EMB})")
    assert by_table["recording_scheme"] == sql1(f"SELECT COUNT(*) FROM recording_scheme WHERE {GRID}") - dup_rs
    assert by_table["observations"] == sql1(f"SELECT COUNT(*) FROM observations WHERE {GRID} AND NOT {EMB}")
    keys = [(r["table"], r["id"]) for r in res.records]
    assert len(keys) == len(set(keys))


# ---------------------------------------------------------------- selection

@needs_data
def test_species_genus_family_order_against_sql(ms, taxa):
    rut = chip(taxa, "Rutpela maculata")
    assert len(fetch(ms, [rut], "personal").records) == sql1(
        f"SELECT COUNT(*) FROM observations WHERE {GRID} AND {PERSONAL} AND NOT {EMB} "
        f"AND species_tvk = '{rut['tvk']}'")
    rh = chip(taxa, "Rhagium", "genus")
    assert rh["rank"] == "Genus"
    assert len(fetch(ms, [rh], "personal").records) == sql1(
        f"SELECT COUNT(*) FROM observations WHERE {GRID} AND {PERSONAL} AND NOT {EMB} "
        f"AND species_name LIKE 'Rhagium %'")
    col = chip(taxa, "Coleoptera", "order")
    assert len(fetch(ms, [col], "personal").records) == sql1(
        f"SELECT COUNT(*) FROM observations WHERE {GRID} AND {PERSONAL} AND NOT {EMB} "
        f"AND order_name = 'Coleoptera'")
    cer = chip(taxa, "Cerambycidae", "family")
    assert len(fetch(ms, [cer], "scheme").records) == sql1(
        f"SELECT COUNT(*) FROM recording_scheme WHERE {GRID} AND family = 'Cerambycidae'")


@needs_data
def test_old_name_maps_current_taxon(ms, taxa):
    hit = taxa.search_taxa("Strangalia maculata")[0]
    assert hit["scientific_name"] == "Rutpela maculata" and hit["old_name"] == "Strangalia maculata"
    assert taxa.search_taxa("Rhagium mordx")[0]["scientific_name"] == "Rhagium mordax"


@needs_data
def test_several_taxa_union_and_chip_counts(ms, taxa):
    rut, rh = chip(taxa, "Rutpela maculata"), chip(taxa, "Rhagium", "genus")
    a, b = fetch(ms, [rut], "all"), fetch(ms, [rh], "all")
    both = fetch(ms, [rut, rh], "all")
    assert len(both.records) == len(a.records) + len(b.records)       # disjoint taxa
    assert both.chip_counts == [len(a.records), len(b.records)]
    # overlapping chips: each record once, counted under both chips
    cer = chip(taxa, "Cerambycidae", "family")
    c = fetch(ms, [cer, rut], "personal")
    assert len(c.records) == len(fetch(ms, [cer], "personal").records)
    assert c.chip_counts[1] == len(fetch(ms, [rut], "personal").records)


@needs_data
def test_taxon_group_chip(ms, taxa):
    from shared.taxon_groups import group_filter_sql
    g = taxa.search_taxa("beetles", "group")[0]
    assert g["kind"] == "group" and g["label"] == "Beetles (Coleoptera)"
    sql, params = group_filter_sql([g["label"]], known=[g["label"]])
    conn = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
    want = conn.execute(f"SELECT COUNT(*) FROM observations WHERE {GRID} AND {PERSONAL} AND NOT {EMB} "
                        f"AND {sql}", params).fetchone()[0]
    conn.close()
    res = fetch(ms, [g], "personal")
    assert len(res.records) == want and res.chip_counts == [want]


# ---------------------------------------------------------------- filters (MAP3, MAP8)

@needs_data
def test_vc_recorder_site_and_dates(ms):
    assert len(fetch(ms, [], "personal", vc=23).records) == sql1(
        f"SELECT COUNT(*) FROM observations WHERE {GRID} AND {PERSONAL} AND NOT {EMB} AND vc_number = 23")
    assert len(fetch(ms, [], "scheme", recorder="heeney").records) == sql1(
        f"SELECT COUNT(*) FROM recording_scheme WHERE {GRID} AND recorder LIKE '%heeney%'")
    assert len(fetch(ms, [], "collection", recorder="heeney").records) <= sql1(
        f"SELECT COUNT(*) FROM specimens WHERE {GRID} AND collector LIKE '%heeney%'")
    assert len(fetch(ms, [], "personal", site="Bicester").records) == sql1(
        f"SELECT COUNT(*) FROM observations WHERE {GRID} AND {PERSONAL} AND NOT {EMB} "
        f"AND site_name LIKE '%Bicester%'")
    f, t = date_bounds("01/01/2020")[0], date_bounds("31/12/2020")[1]
    y2020 = fetch(ms, [], "personal", date_from=f, date_to=t)
    assert len(y2020.records) == sql1(
        f"SELECT COUNT(*) FROM observations WHERE {GRID} AND {PERSONAL} AND NOT {EMB} "
        f"AND date BETWEEN '2020-01-01' AND '2020-12-31'")
    assert {r["year"] for r in y2020.records} == {2020}


def test_date_bounds_forms():
    assert date_bounds("2021") == ("2021-01-01", "2021-12-31")
    assert date_bounds("06/2021") == ("2021-06-01", "2021-06-30")
    assert date_bounds("01/06/2021") == ("2021-06-01", "2021-06-01")
    assert date_bounds("2021-06-01") == ("2021-06-01", "2021-06-01")
    assert date_bounds("31/02/2021") is None and date_bounds("soon") is None


@needs_data
def test_vc_choices_one_per_number(ms):
    ch = ms.vc_choices()
    nums = [n for n, _t in ch]
    assert len(nums) == len(set(nums)) and 23 in nums
    assert dict(ch)[23].startswith("VC23 - ")


# ---------------------------------------------------------------- squares, styles (MAP5)

def _recs():
    return [{"grid_ref": "SP580207", "year": 2021, "species": "A"},
            {"grid_ref": "SP581208", "year": 1990, "species": "B"},
            {"grid_ref": "SP590200", "year": None, "species": "A"},
            {"grid_ref": "TQ1234", "year": None, "species": None},
            {"grid_ref": "SP58", "year": 2000, "species": "C"}]


def test_squares_richness_and_undated():
    from src.services import map_square_service as s
    bands = s.BAND_PRESETS["default"]
    sq, coarse, unparsed = s.squares_for(_recs(), 1000, lambda y: s.year_to_band(y, bands))
    assert coarse == 1 and unparsed == 0
    assert sq["SP5820"]["count"] == 2 and sq["SP5820"]["species"] == 2
    assert sq["SP5920"]["band"] == "undated" and sq["SP5920"]["undated"] == 1
    assert sq["TQ1234"]["species"] == 0
    assert "2 species" in sq["SP5820"]["tip"]
    hect, _c, _u = s.squares_for(_recs(), 10000, lambda y: s.year_to_band(y, bands))
    assert hect["SP52"]["count"] == 3 and hect["SP52"]["species"] == 2
    assert hect["SP58"]["count"] == 1
    assert hect["SP52"]["band"] == "current"         # newest dated record, not the undated one
    assert s.year_to_band(None, bands) == "undated"
    assert list(s.band_labels(bands).values())[-1] == "Undated"
    r = _recs()
    s.squares_for(r, 1000, lambda y: s.year_to_band(y, bands))
    assert s.records_in_square(r, "SP5820", 1000) == r[:2]


def test_richness_and_date_legends():
    from src.views.mapping.square_style import band_colours, colour_squares, style_key
    assert style_key("Species richness") == "richness"
    squares = {"A": {"count": 3, "species": 1, "band": "recent"},
               "B": {"count": 9, "species": 25, "band": "undated"},
               "C": {"count": 1, "species": 0, "band": "current"}}
    legend = colour_squares(squares, "richness", {}, {}, "#ffffff", "#000000")
    labels = [lab for _c, lab in legend]
    assert labels == ["No species-level record", "1 species", "20–49"]
    assert squares["A"]["fill"] != squares["B"]["fill"]
    cols = band_colours(["historical", "recent", "current", "undated"], "#999999")
    legend = colour_squares(squares, "date", cols, {"recent": "2000–2019", "current": "2020+",
                                                    "undated": "Undated"}, "#fff", "#000")
    assert [lab for _c, lab in legend] == ["2000–2019", "2020+", "Undated"]
    assert squares["B"]["fill"] == "#999999"


def test_quick_presets_run_to_this_year_and_safe_names():
    from src.views.mapping.filter_panel import quick_presets
    from src.views.mapping.mapping_tab import safe_filename
    p = quick_presets(dt.date(2026, 10, 10))
    assert [x[0] for x in p] == ["2026", "2025", "2024", "2021–26", "All"]
    assert p[3][1:] == ("2021", "2026")
    name = safe_filename("Bombus lucorum/terrestris agg. + Rhagium")
    assert "/" not in name and "\\" not in name and name.startswith("Bombus_lucorum-terrestris")


# ---------------------------------------------------------------- the tab, offscreen

@pytest.fixture(scope="module")
def tab():
    if not HAVE_DATA:
        pytest.skip("needs data copies")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from src.views.mapping.mapping_tab import MappingTab
    return MappingTab()


@needs_data
def test_tab_coleoptera_all_sources(tab, ms, taxa):
    sb = tab.filter_panel.selection_box
    sb.clear()
    tab.toolbar.data_combo.setCurrentIndex(tab.toolbar.data_combo.findData("all"))
    sb.rank_combo.setCurrentIndex(sb.rank_combo.findData("order"))
    sb.search.setText("Coleoptera")
    sb.run_search()
    hit = [r for r in sb.results() if r["scientific_name"] == "Coleoptera"][0]
    t = time.perf_counter()
    sb.add(hit)                                     # adding a chip maps it
    elapsed = time.perf_counter() - t
    want = len(fetch(ms, [hit], "all").records)
    assert len(tab._records) == want
    assert "records mapped" in sb.chip_texts()[0] and f"{want:,}" in sb.chip_texts()[0]
    assert f"{want:,} records" in tab.map_header.grid_count.text()
    assert "embargoed not shown" in tab.map_header.subtitle.text()
    assert elapsed < 6.0, f"all Coleoptera, all sources took {elapsed:.1f}s"
    tab.display_bar.style_combo.setCurrentIndex(tab.display_bar.style_combo.findData("richness"))
    assert tab.display_bar.legend_labels()[0] in ("1 species", "No species-level record")
    tab.display_bar.style_combo.setCurrentIndex(tab.display_bar.style_combo.findData("date"))
    assert tab.display_bar.legend_labels()[-1] == "Undated"
    assert tab.display_bar.period_combo.isEnabled()
    n = len(tab._records)
    tab.display_bar.period_combo.setCurrentIndex(1)         # recolours only
    assert len(tab._records) == n and tab.display_bar.legend_labels()[0] == "Pre-1970"
    img = tab.render_atlas()
    assert img.width() == 2480


@needs_data
def test_tab_filters_and_bad_date(tab):
    fp = tab.filter_panel
    fp.selection_box.clear()
    tab.toolbar.data_combo.setCurrentIndex(tab.toolbar.data_combo.findData("personal"))
    fp.vc_combo.setCurrentIndex(fp.vc_combo.findData(23))
    tab._generate_map()
    assert {r["vc"] for r in tab._records} == {23}
    assert tab.map_widget._vc_highlight == {23}                  # MAP4: by number, same records
    fp.vc_combo.setCurrentIndex(0)
    fp.date_from.setText("31/02/2020")
    tab._generate_map()
    assert "not understood" in tab.map_widget._message and fp.date_error.isVisibleTo(fp)
    fp.date_from.setText("01/01/2020")
    fp.date_to.setText("31/12/2020")
    tab._generate_map()
    assert tab._records and {r["year"] for r in tab._records} == {2020}
    fp.date_from.setText("")
    fp.date_to.setText("")


@needs_data
def test_tab_square_dialog_count_column(tab, taxa):
    from src.services import map_square_service as s
    from src.views.mapping.square_records_dialog import SquareRecordsDialog
    sb = tab.filter_panel.selection_box
    sb.clear()
    tab.toolbar.data_combo.setCurrentIndex(tab.toolbar.data_combo.findData("personal"))
    sb.add(chip(taxa, "Rutpela maculata"))
    lab = max(tab._squares, key=lambda k: tab._squares[k]["count"])
    recs = s.records_in_square(tab._records, lab, tab._grid_size())
    assert len(recs) == tab._squares[lab]["count"]
    d = SquareRecordsDialog(lab, "Hectad", recs, "Rutpela maculata")
    assert all(d.table.item(i, 6).text() for i in range(d.table.rowCount()))   # MAP6
