"""Round 16 (B11 / Q54): the Data Entry banner folds to one line, remembered in settings.
Offscreen at 1280x720 on a small temp database."""
from PySide6.QtWidgets import QPushButton
from tests.test_dataentry_r3 import (_make_widget, _open_grid, _pump,  # noqa: F401,F811
                                     _tidy_widgets, qapp, settings_isolated)


def _rows_shown(g):
    view = g._view
    h = view.verticalHeader().defaultSectionSize()
    return view.viewport().height() // h


def _setup(app, tmp_path, monkeypatch):
    tmp_path.mkdir(exist_ok=True)
    w = _make_widget(tmp_path, monkeypatch)
    g = _open_grid(w)
    w.resize(1280, 720)
    w.show()
    _pump(app, 8)
    return w, g


def test_compact_default_off_and_shows_more_rows(qapp, settings_isolated,  # noqa: F811
  tmp_path, monkeypatch):
    w, g = _setup(qapp, tmp_path, monkeypatch)
    ip = g._info
    assert not ip.is_compact()
    assert all(c.isVisible() for c in ip._banner_cards if c not in ip._collapsible)
    full_rows, full_banner = _rows_shown(g), g._banner_scroll.height()
    btn = w._fold_top_btn                              # R17: right-hand end of the job's top line
    assert btn.text() == "\u25B4 Fold banner"
    assert not hasattr(ip, "_fold_btn")                # the old small link in the species card is gone
    top = btn.parentWidget()
    assert btn.geometry().right() > top.width() - 60   # at the right-hand end
    w._fold_top_btn.click()
    _pump(qapp, 8)
    assert ip.is_compact()
    assert btn.text() == "\u25BE Unfold banner"
    w._fold_top_btn.click()                            # the same button unfolds
    _pump(qapp, 8)
    assert not ip.is_compact() and btn.text() == "\u25B4 Fold banner"
    w._fold_top_btn.click()
    _pump(qapp, 8)
    assert not any(c.isVisible() for c in ip._banner_cards)
    assert ip._compact_strip.isVisible()
    assert g._banner_scroll.height() < full_banner - 100
    assert _rows_shown(g) >= full_rows + 5, (full_rows, _rows_shown(g))
    assert not hasattr(ip._compact_strip, "unfold_btn")   # R18: the strip has no button of its own
    assert not ip._compact_strip.findChildren(QPushButton)
    w._fold_top_btn.click()                            # the top line's button unfolds
    _pump(qapp, 8)
    assert not ip.is_compact() and not ip._compact_strip.isVisible()
    assert btn.text() == "\u25B4 Fold banner"
    assert ip._controls_widget.isVisible()
    assert _rows_shown(g) == full_rows
    w.close()


def test_compact_is_remembered_and_strip_names_the_species(qapp, settings_isolated,  # noqa: F811
  tmp_path,
                                                           monkeypatch):
    w, g = _setup(qapp, tmp_path, monkeypatch)
    ip = g._info
    ip.update_for_row({"species_name": "Abax parallelus", "common_name": ""})
    ip.set_compact(True)
    _pump(qapp, 4)
    assert "Abax parallelus" in ip._compact_strip.label.text()
    ip.update_for_row({"species_name": "Carabus violaceus"})
    assert "Carabus violaceus" in ip._compact_strip.label.text()
    w.close()
    w2, g2 = _setup(qapp, tmp_path / "again", monkeypatch)
    assert g2._info.is_compact()                      # a new panel starts the way it was left
    assert w2._fold_top_btn.text() == "\u25BE Unfold banner"
    _pump(qapp, 6)
    assert not any(c.isVisible() for c in g2._info._banner_cards)
    g2._info.set_compact(False)
    w2.close()
