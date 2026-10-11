"""Batch maps (R9-7, 11 Oct 2026): taxon selection, file naming, the spread-over-time maths,
and -- on the data copies, read-only, offscreen -- the batch's figures equal the Mapping tab's
for the same settings.
"""
import os

import pytest

import paths

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HAVE_DATA = paths.OBSERVATUM_DB.exists() and paths.UKSI_DB.exists()
needs_data = pytest.mark.skipif(not HAVE_DATA, reason="needs data/observatum.db and uksi.db")

RUTPELA = "NHMSYS0020109270"
TETROPS = "NHMSYS0020153614"         # Tetrops praeustus: few records, VC23
STENOCORUS = "NBNSYS0000011005"


# ---------------------------------------------------------------- pure parts

def test_settings_areas_and_filters():
    from src.services.batch_maps import AreaFilters, BatchSettings, area_label
    s = BatchSettings(vcs=(23, 24))
    assert s.areas() == [(23, 24)] and area_label((23, 24)) == "VC23-24"
    assert BatchSettings(vcs=(23, 24), per_vc=True).areas() == [(23,), (24,)]
    assert BatchSettings().areas() == [()] and area_label(()) == "GB"
    assert BatchSettings(grid="1km").grid_name == "monad"
    keys = AreaFilters(vcs=(23, 24), date_from="2000-01-01").builder_keys()
    assert keys["vice_county"] == ["23", "24"] and keys["date_from"] == "2000-01-01"
    assert "vice_county" not in AreaFilters().builder_keys()
    assert s.filters((23,)).vcs == (23,)


def test_file_names_are_consistent_and_safe():
    from src.services.batch_maps import BatchSettings, file_name
    s = BatchSettings(grid="tetrad")
    chip = {"scientific_name": "Leptura aurulenta"}
    assert file_name(chip, s, (23,)) == "Leptura_aurulenta_tetrad_VC23.png"
    assert file_name(chip, s, (), "f03_1980s") == "Leptura_aurulenta_tetrad_GB_f03_1980s.png"
    odd = {"scientific_name": 'Anoplodera sexguttata/ "agg."'}
    assert not set('/\\:*?"<>|') & set(file_name(odd, s))


def test_date_classes_and_colours():
    from src.services import batch_spread as sp
    cl = sp.date_classes((1970, 2000, 2020))
    assert [c["label"] for c in cl] == ["Pre-1970", "1970–1999", "2000–2019", "2020+"]
    assert sp.class_of(1969, cl) == "c0" and sp.class_of(1970, cl) == "c1"
    assert sp.class_of(2026, cl) == "c3" and sp.class_of(None, cl) == sp.UNDATED
    assert sp.parse_breaks("2000, 1970;2020") == (1970, 2000, 2020)
    with pytest.raises(ValueError):
        sp.parse_breaks("70")
    assert len(sp.ramp(6)) == 6 and sp.ramp(4) == sp.DATE_RAMP
    squares = {"A": {"first_year": 1950, "last_year": 2021},
               "B": {"first_year": 2005, "last_year": 2005},
               "C": {"first_year": None, "last_year": None}}
    legend = sp.colour_by_date_class(squares, (1970, 2000, 2020), "first", "#999999")
    assert [lab for _c, lab in legend] == ["First record Pre-1970", "First record 2000–2019",
                                          "Undated only"]
    assert squares["C"]["fill"] == "#999999"
    sp.colour_by_date_class(squares, (1970, 2000, 2020), "last")
    assert squares["A"]["date_class"] == "c3"


def test_frames_are_cumulative():
    from src.services import batch_spread as sp
    squares = {"A": {"first_year": 1955}, "B": {"first_year": 1987}, "C": {"first_year": 1989},
               "D": {"first_year": 2003}, "E": {"first_year": None}}
    fr, undated = sp.frames(squares, "decade")
    assert undated == 1
    assert [f["label"] for f in fr] == ["1950s", "1960s", "1970s", "1980s", "1990s", "2000s"]
    assert [f["total"] for f in fr] == [1, 1, 1, 3, 3, 4]
    assert [f["new"] for f in fr] == [1, 0, 0, 2, 0, 1]
    fr2, _u = sp.frames(squares, "decade", start=1980)
    assert fr2[0]["label"] == "to 1979" and fr2[0]["total"] == 1
    assert sp.periods(1998, 2001, "year")[-1] == (2001, 2001, "2001")
    sq, legend = sp.frame_squares({k: dict(v) for k, v in squares.items()}, fr[3])
    assert sq["A"]["fill"] == sp.FRAME_OLD and sq["B"]["fill"] == sp.FRAME_NEW
    assert "D" not in sq and [lab for _c, lab in legend] == ["Recorded before 1980", "New 1980s"]


# ---------------------------------------------------------------- on the data copies

@needs_data
def test_resolve_group_and_tvks():
    from src.services import batch_maps as bm
    s = bm.BatchSettings(sources=("all",), vcs=(23,))
    chips, problems = bm.resolve(group="Cerambycidae", rank="family", settings=s)
    assert not problems and len(chips) > 20
    tvks = [c["tvk"] for c in chips]
    assert RUTPELA in tvks and len(set(tvks)) == len(tvks)
    assert all(c["kind"] == "taxon" for c in chips)
    # every species has a record in VC23 for these settings
    tm = bm.map_taxon(chips[-1], s, (23,))
    assert tm.records > 0
    chips2, problems2 = bm.resolve([RUTPELA, "NOTATVK000"], settings=s)
    assert [c["tvk"] for c in chips2] == [RUTPELA] and problems2
    assert bm.resolve(group="Nosuchfamilyidae", settings=s)[1]


@pytest.fixture(scope="module")
def tab():
    if not HAVE_DATA:
        pytest.skip("needs data copies")
    from PySide6.QtCore import QCoreApplication, QSettings
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    org = QCoreApplication.organizationName()
    QCoreApplication.setOrganizationName("ObservatumTests_batch_maps_r3")
    QSettings().clear()
    from src.views.mapping.mapping_tab import MappingTab
    t = MappingTab()
    t.resize(1600, 1000)
    yield t
    t.close()
    QSettings().clear()
    QCoreApplication.setOrganizationName(org)


@needs_data
@pytest.mark.parametrize("tvk,sources,vc,grid", [
    (RUTPELA, ["all"], None, "hectad"),
    (TETROPS, ["personal", "scheme"], 23, "tetrad"),
    (STENOCORUS, ["scheme"], 23, "hectad"),
])
def test_counts_equal_mapping_tab(tab, tvk, sources, vc, grid):
    """The same chip, sources, VC and grid in the Mapping tab and in a batch: same records,
    same squares, same held-back figures, same page footer."""
    from src.services import batch_maps as bm
    from src.views.mapping.batch_render import BatchRenderer
    fp = tab.filter_panel
    fp.selection_box.clear(emit=False)
    fp.source_picker.set_sources(sources, emit=False)
    fp.vc_combo.blockSignals(True)
    fp.vc_combo.setCurrentIndex(fp.vc_combo.findData(vc) if vc else 0)
    fp.vc_combo.blockSignals(False)
    s = bm.BatchSettings(sources=tuple(sources), vcs=(vc,) if vc else (), grid=grid,
                         include_tetrads=fp.include_tetrads())
    tab.toolbar.grid_combo.setCurrentIndex(tab.toolbar.grid_combo.findData(s.size))
    chip = bm.taxon_chip(tvk)
    fp.selection_box.add(dict(chip))            # adding a chip maps it
    tab._generate_map()
    tm = bm.map_taxon(chip, s, s.vcs)
    assert tm.records == len(tab._records) > 0
    assert set(tm.squares) == set(tab._squares)
    assert {k: v["count"] for k, v in tm.squares.items()} == \
        {k: v["count"] for k, v in tab._squares.items()}
    assert (tm.result.embargoed, tm.result.merged) == (tab._result.embargoed, tab._result.merged)
    assert tm.tetrads_held == tab._tetrads_held
    r = BatchRenderer(s)
    # atlas_export.render_atlas's footer, from the tab's own state
    n_sp = len({x["species"] for x in tab._records if x.get("species") and x.get("square")})
    grid_word = {"hectad": "hectads", "tetrad": "tetrads"}[grid]
    tab_footer = (f"{len(tab._squares):,} {grid_word}, "
                  f"{sum(q['count'] for q in tab._squares.values()):,} records, {n_sp:,} species.")
    assert r.footer(tm) == tab_footer


@needs_data
def test_batch_writes_pages_and_index(tmp_path):
    from src.services import batch_maps as bm
    from src.views.mapping.batch_render import BatchRenderer
    s = bm.BatchSettings(sources=("scheme",), vcs=(23,), dpi=60)
    chips = [bm.taxon_chip(RUTPELA), bm.taxon_chip(STENOCORUS)]
    r = BatchRenderer(s)
    done = []
    for tm in bm.run(chips, s):
        r.save_map(tm, str(tmp_path))
        done.append(tm)
    files = r.save_frames(done[0], str(tmp_path), "decade", 1990, gif=False)
    dc = r.save_date_classes(done[0], str(tmp_path))
    assert bm.write_index(str(tmp_path / "index.csv"), done) == 2
    names = sorted(os.listdir(tmp_path))
    assert "Rutpela_maculata_hectad_VC23.png" in names
    assert "Stenocorus_meridianus_hectad_VC23.png" in names
    assert os.path.basename(dc) == "Rutpela_maculata_hectad_VC23_dateclass-first.png"
    assert files and os.path.basename(files[0]).startswith("Rutpela_maculata_hectad_VC23_f01_")
    rows = (tmp_path / "index.csv").read_text(encoding="utf-8-sig").splitlines()
    assert rows[0].startswith("taxon,common_name,tvk") and len(rows) == 3
    assert f",{done[0].records}," in rows[1]
