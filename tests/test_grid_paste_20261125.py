"""25 Nov 2026: copy and paste in the Data Entry grid.

A block copied in the grid that spans Check / Check note / Keep pasted with the values after
them shifted; Windows line endings broke the in-app match; a comment with a line break split
into two rows; a copied species landing in another column pasted a dict."""
import sqlite3

import pytest

from DataEntry import grid_clipboard as gc
from DataEntry.grid_columns import COLUMNS, COLIDX


def test_text_round_trip_keeps_line_breaks_and_quotes():
    rows = [["Amara aenea", "2", 'a "big" one\nsecond line'], ["Bb", "", "x\ty"]]
    assert gc.from_text(gc.to_text(rows)) == rows
    assert gc.from_text("a\tb\r\nc\td\r\n") == [["a", "b"], ["c", "d"]]
    assert gc.same_text("a\tb\nc", "a\tb\r\nc\r\n")


def test_old_sheet_steps_over_check_columns_grid_shaped_does_not():
    n = len(COLUMNS)
    old = [c for c in range(n) if COLUMNS[c][0] not in gc.CHECK_KEYS]
    # old sheet: VC No. 56 sits where Check now is
    row_old = [""] * len(old)
    row_old[old.index(COLIDX["vc_number"])] = "56"
    row_old[old.index(COLIDX["recorder"])] = "Heeney, W.J."
    assert gc.target_columns([row_old], 0, n) == old
    # grid-shaped: Check "1", VC No. 56 where the grid has it
    row_new = [""] * n
    row_new[COLIDX["check_flag"]] = "1"
    row_new[COLIDX["vc_number"]] = "56"
    assert gc.target_columns([row_new], 0, n) == list(range(n))
    # a full-width grid row with nothing in Check or VC No. is still too wide for an old sheet
    assert gc.target_columns([[""] * n], 0, n) == list(range(n))
    # copied in the grid: same spacing, whatever is in it
    assert gc.target_columns([["a", "b"]], 3, n, [10, 12]) == [3, 5]


class _FakeClipboard:
    """Stands in for the system clipboard, so the test never touches Wil's own (on Windows a
    real clipboard can be briefly locked and fail the next test that uses it)."""
    def __init__(self):
        self._t = ""

    def setText(self, t):
        self._t = t

    def text(self):
        return self._t


@pytest.fixture
def grid(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    fake = _FakeClipboard()
    monkeypatch.setattr(QApplication, "clipboard", staticmethod(lambda: fake))
    from DataEntry import entry_grid as eg
    conn = sqlite3.connect(tmp_path / "g.db")
    conn.row_factory = sqlite3.Row
    cols = ", ".join(f"{c[0]} TEXT" for c in COLUMNS if c[0] != "species_name")
    conn.execute("CREATE TABLE entry_jobs (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute(f"CREATE TABLE entry_staging (id INTEGER PRIMARY KEY, job_id INTEGER, "
                 f"row_order INTEGER, species_name TEXT, tvk TEXT, {cols}, updated_at TEXT)")
    conn.execute("INSERT INTO entry_jobs (id, name) VALUES (1, 'T')")
    conn.execute("INSERT INTO entry_staging (job_id, row_order, species_name, comment, check_note, "
                 "recorder, determiner) VALUES (1, 0, 'Amara aenea', 'c1', 'note', 'Rec A', 'Det A')")
    conn.commit()
    m = eg.StagingTableModel(conn, 1)
    v = eg.EntryTableView()
    v.setModel(m)
    return conn, m, v


def test_in_grid_copy_across_check_columns_pastes_in_place(grid):
    conn, m, v = grid
    from PySide6.QtCore import QItemSelectionModel
    sel = v.selectionModel()
    for c in range(COLIDX["comment"], COLIDX["determiner"] + 1):
        sel.select(m.index(0, c), QItemSelectionModel.SelectionFlag.Select)
    v._copy()
    v.clearSelection()
    v.setCurrentIndex(m.index(1, COLIDX["comment"]))
    v._paste()
    got = {c: m.cell_value(1, COLIDX[c]) for c in ("comment", "check_note", "recorder", "determiner")}
    assert got == {"comment": "c1", "check_note": "note", "recorder": "Rec A", "determiner": "Det A"}


def test_copied_species_into_another_column_pastes_its_name(grid):
    conn, m, v = grid
    v.setCurrentIndex(m.index(0, COLIDX["species_name"]))
    v._copy()
    v.setCurrentIndex(m.index(0, COLIDX["comment"]))
    v._paste()
    assert m.cell_value(0, COLIDX["comment"]) == "Amara aenea"
