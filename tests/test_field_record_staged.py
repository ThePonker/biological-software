"""Edit Specimen's Field record box: a specimen already on a Data Entry row cannot be
linked from the dialog (F86, 16 Oct 2026); its check box carries the suite's green tick.
A small purpose-made database; no live figures are pinned."""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from DataEntry import staging_repo  # noqa: E402
from Observatum.src.views.dialogs.field_record_box import FieldRecordBox  # noqa: E402
from shared import specimen_staging, tick_style  # noqa: E402

JOB = "Dartford visit"


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "observatum.db"
    c = sqlite3.connect(p)
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, species_name, date, "
              "grid_ref, recorder, site_name, quantity, sex)")
    c.execute("CREATE TABLE specimens (id INTEGER PRIMARY KEY, observation_id, "
              "no_field_record_checked)")
    c.executemany("INSERT INTO specimens (id) VALUES (?)", [(1,), (2,)])
    staging_repo.ensure_schema(c)
    job = staging_repo.create_job(c, JOB, "Personal")
    row = staging_repo.insert_row(c, job, {"species_name": "Lamia textor"})
    specimen_staging.add(c, row, [1])
    c.commit()
    c.close()
    return p


def _box(path, sid):
    QApplication.instance() or QApplication([])
    return FieldRecordBox(sid, str(path), lambda: {})


def test_staged_specimen_cannot_be_picked_and_says_why(db):
    box = _box(db, 1)
    assert not box.pick_btn.isEnabled()
    assert box.staged_note.text() == (f"On a Data Entry row (job '{JOB}'): "
                                      "it will be linked when that row is committed.")
    assert not box.staged_note.isHidden()
    box.set_link(5)                                   # refused too
    assert box.changes() == {}
    assert not box.check.isEnabled()                  # nor "no field record exists"


def test_link_script_leaves_staged_specimens_alone(db):
    from scripts import link_specimens_to_observations as lk
    c = sqlite3.connect(db)
    try:
        assert lk.staged_on_rows(c) == {1}
        assert lk.apply(c, [(1, 7), (2, 8)]) == [(2, 8)]
        assert c.execute("SELECT id, observation_id FROM specimens ORDER BY id").fetchall() == [
            (1, None), (2, 8)]
    finally:
        c.close()


def test_staged_specimen_has_nothing_to_clear(db):
    box = _box(db, 1)
    assert not box.clear_btn.isEnabled()              # nothing linked, nothing to clear


def test_unstaged_specimen_is_normal(db):
    box = _box(db, 2)
    assert box.pick_btn.isEnabled()
    assert box.check.isEnabled()
    assert box.staged_note.text() == ""
    assert box.staged_note.isHidden()


def test_database_without_the_staging_table_is_normal(tmp_path):
    p = tmp_path / "old.db"
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY)")
    c.execute("CREATE TABLE specimens (id INTEGER PRIMARY KEY, observation_id, "
              "no_field_record_checked)")
    c.execute("INSERT INTO specimens (id) VALUES (1)")
    c.commit()
    c.close()
    box = _box(p, 1)
    assert box.pick_btn.isEnabled()
    assert box.staged_note.text() == ""


def test_field_record_check_box_gets_the_suite_tick(db):
    app = QApplication.instance() or QApplication([])
    tick_style.install(app, lambda: dict(fill="#4a7c59", mark="#ffffff", border="#9ca3af",
                                         background="#ffffff"))
    box = _box(db, 2)
    box.show()
    app.processEvents()
    qss = box.check.styleSheet()
    assert "QCheckBox::indicator:checked" in qss and "image: url(" in qss
    assert "tick_4a7c59_ffffff" in qss                # the suite's tick PNG, in the green
    box.close()


def test_a_box_with_its_own_indicator_style_is_left_alone(db):
    app = QApplication.instance() or QApplication([])
    tick_style.install(app, lambda: dict(fill="#4a7c59", mark="#ffffff", border="#9ca3af",
                                         background="#ffffff"))
    from PySide6.QtWidgets import QCheckBox
    own = "QCheckBox::indicator:checked { background-color: #123456; }"
    cb = QCheckBox("x")
    cb.setStyleSheet(own)
    cb.show()
    app.processEvents()
    assert cb.styleSheet() == own
    cb.close()


GREEN = dict(fill="#4a7c59", mark="#ffffff", border="#9ca3af", background="#ffffff")


def test_radio_buttons_get_the_suite_dot():
    """17 Oct: radio buttons too (Export for checking's 'Rows marked to check')."""
    app = QApplication.instance() or QApplication([])
    tick_style.install(app, lambda: GREEN)
    from PySide6.QtWidgets import QRadioButton, QWidget
    panel = QWidget()
    panel.setStyleSheet("QCheckBox::indicator { width: 20px; }")   # a check-box rule only
    rb = QRadioButton("Rows marked to check", panel)
    panel.show()
    app.processEvents()
    qss = rb.styleSheet()
    assert "QRadioButton::indicator:checked" in qss and "#4a7c59" in qss
    panel.close()


def test_a_radio_with_its_own_indicator_style_is_left_alone():
    app = QApplication.instance() or QApplication([])
    tick_style.install(app, lambda: GREEN)
    from PySide6.QtWidgets import QRadioButton
    own = "QRadioButton::indicator:checked { background-color: #123456; }"
    rb = QRadioButton("x")
    rb.setStyleSheet(own)
    rb.show()
    app.processEvents()
    assert rb.styleSheet() == own
    rb.close()


def test_checkable_list_items_get_the_tick():
    QApplication.instance() or QApplication([])
    from PySide6.QtWidgets import QListWidget, QTreeWidget
    for view in (QListWidget(), QTreeWidget()):
        tick_style.style_item_view(view, GREEN)
        sheet = view.styleSheet()
        name = type(view).__name__
        assert f"{name}::indicator:checked" in sheet and "tick_4a7c59_ffffff" in sheet
        assert f"{name}::indicator:indeterminate" in sheet
