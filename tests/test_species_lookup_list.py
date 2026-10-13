"""Stats > Species Lookup: the drop-down rows are drawn by the shared species list painter
(13 Oct 2026). The search (shared.species_search, every UK species) and what a pick opens are
unchanged: each row's text is still _display(r), which _on_completer_activated matches on."""
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _r(sci, common="", family="", **kw):
    base = dict(scientific_name=sci, common_name=common, family=family, tvk="T" + sci[:3],
                rank="Species", order_name="Coleoptera", old_name=None, match_type="exact")
    base.update(kw)
    return SimpleNamespace(**base)


def test_rows_keep_their_text_and_carry_the_painters_data(qapp):
    from shared.species_list_delegate import HIT_ROLE, SpeciesListDelegate
    from src.views.stats.species_dashboard import SpeciesDashboard
    d = SpeciesDashboard()
    rows = [_r("Rutpela maculata", "Black-and-yellow Longhorn", "Cerambycidae"),
            _r("Clytus arietis", "", "Cerambycidae", old_name="Clytus arietus"),
            _r("Rhagium mordax", "", "Cerambycidae", match_type="fuzzy")]
    d._set_results(rows)
    m = d._completer_model
    assert [m.item(i).text() for i in range(m.rowCount())] == [d._display(r) for r in rows]
    first = m.item(0).data(HIT_ROLE)
    assert (first["scientific"], first["common"], first["family"]) == (
        "Rutpela maculata", "Black-and-yellow Longhorn", "Cerambycidae")
    assert m.item(1).data(HIT_ROLE)["note"] == "old name: Clytus arietus"
    assert m.item(2).data(HIT_ROLE)["note"] == "close spelling"
    assert isinstance(d._completer.popup().itemDelegate(), SpeciesListDelegate)
    d._set_results([])
    assert m.rowCount() == 0


def test_popup_paints(qapp):
    """The pop-up draws its rows with the painter without error."""
    from src.views.stats.species_dashboard import SpeciesDashboard
    d = SpeciesDashboard()
    d.resize(800, 600)
    d.show()
    d._set_results([_r("Rutpela maculata", "Black-and-yellow Longhorn", "Cerambycidae")])
    d._completer.complete()
    qapp.processEvents()
    img = d._completer.popup().grab()
    assert not img.isNull()
    d.close()
