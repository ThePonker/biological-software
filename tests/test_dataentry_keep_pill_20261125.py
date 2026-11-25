"""25 Nov 2026: the specimens pill counts rows ticked Keep (any open job, one per row, not made
yet) as "+k to keep", and shortens itself to fit the card."""
import sqlite3
from types import SimpleNamespace

from PySide6.QtWidgets import QLabel

from tests.test_dataentry_r3 import qapp  # noqa: F401


def test_kept_to_make_counts_ticked_rows_in_open_jobs(tmp_path):
    from DataEntry.info_panel import InfoService
    c = sqlite3.connect(tmp_path / "o.db")
    c.execute("CREATE TABLE entry_jobs (id INTEGER PRIMARY KEY, status TEXT)")
    c.execute("CREATE TABLE entry_staging (id INTEGER PRIMARY KEY, job_id INTEGER, species_tvk TEXT, "
              "sex TEXT, quantity INTEGER, keep_flag INTEGER)")
    c.executemany("INSERT INTO entry_jobs VALUES (?, ?)", [(1, "active"), (2, "active"), (3, "committed")])
    c.executemany("INSERT INTO entry_staging (job_id, species_tvk, sex, quantity, keep_flag) "
                  "VALUES (?, ?, ?, ?, ?)", [
                      (1, "T", "male", 93, 1),      # a row of 93 counts one
                      (2, "T", "female", 1, 1),     # another open job counts
                      (1, "T", "", 2, 1),
                      (1, "T", "male", 1, 0),       # not ticked (or made: tick cleared)
                      (3, "T", "male", 1, 1),       # closed job
                      (1, "U", "male", 1, 1)])      # another species
    assert InfoService(c).kept_to_make("T") == (3, 1, 1, 1)
    assert InfoService(c).kept_to_make("") == (0, 0, 0, 0)
    bare = sqlite3.connect(":memory:")                 # no tables: fails soft
    assert InfoService(bare).kept_to_make("T") == (0, 0, 0, 0)


def _pills(kept):
    from DataEntry.info_panel import InfoPanel, _FlowRow
    svc = SimpleNamespace(counts=lambda tvk: (27, 6, 6), specimen_sexes=lambda tvk: (4, 2, 0),
                          kept_to_make=lambda tvk: kept)
    fake = SimpleNamespace(_svc=svc, _pending_for=lambda tvk: {"personal": 0, "commercial": 0},
                           _pill=lambda t: QLabel(t), _pills_row=_FlowRow(), _spec_row=_FlowRow())
    InfoPanel._set_count_pills(fake, "T")
    return fake._spec_row


def test_pill_shows_to_keep_and_shortens_to_fit(qapp):  # noqa: F811
    row = _pills((2, 1, 1, 0))
    pill = row._items[0]
    assert pill.text() == "Spec. 6 (♂4 ♀2) · +2 to keep (♂1 ♀1)"
    assert "+2 to keep" in pill.toolTip() and "1 male, 1 female" in pill.toolTip()
    full = pill.sizeHint().width()
    row.resize(full + 10, 22)
    row._fit()
    assert pill.text().endswith("to keep (♂1 ♀1)") and not pill.isHidden()
    row.resize(pill.fontMetrics().horizontalAdvance("Spec. 6 (+2)") + 30, 22)
    row._fit()
    assert pill.text() == "Spec. 6 (+2)" and not pill.isHidden()      # never folded into "+1"
    # nothing ticked: as before
    plain = _pills((0, 0, 0, 0))
    assert plain._items[0].text() == "Spec. 6 (♂4 ♀2)"
