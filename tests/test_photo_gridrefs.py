"""Grid refs on photos (14 Oct 2026): taken from the linked record, or the specimen's field
record, else the specimen; display only."""
import sqlite3

from shared import photo_links as pl


def _db():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, grid_ref TEXT)")
    conn.execute("CREATE TABLE specimens (id INTEGER PRIMARY KEY, grid_ref TEXT, observation_id INTEGER)")
    pl.ensure_schema(conn)
    conn.execute("INSERT INTO observations VALUES (1, 'SP512345'), (2, 'TQ100200'), (3, NULL)")
    conn.execute("INSERT INTO specimens VALUES (10, 'SP5123', 2), (11, 'NZ1010', NULL)")
    return conn


def test_grid_refs_from_record_field_record_and_specimen():
    conn = _db()
    pl.add_link(conn, "a.jpg", observation_id=1)
    pl.add_link(conn, "b.jpg", specimen_id=10)          # field record wins
    pl.add_link(conn, "c.jpg", specimen_id=11)          # no field record: the specimen's own
    pl.add_link(conn, "d.jpg", observation_id=3)        # no grid ref: left out
    pl.add_link(conn, "e.jpg", observation_id=1)
    pl.add_link(conn, "e.jpg", observation_id=2)
    got = pl.grid_refs(conn, ["a.jpg", "b.jpg", "c.jpg", "d.jpg", "e.jpg", "f.jpg"])
    assert got == {"a.jpg": ["SP512345"], "b.jpg": ["TQ100200"], "c.jpg": ["NZ1010"],
                   "e.jpg": ["SP512345", "TQ100200"]}


def test_viewer_title_shows_the_grid_ref(tmp_path):
    from PySide6.QtWidgets import QApplication
    from src.views.dialogs.photo_viewer import PhotoViewer
    _app = QApplication.instance() or QApplication([])
    a, b = tmp_path / "a.jpg", tmp_path / "b.jpg"
    a.write_bytes(b"x")
    b.write_bytes(b"x")
    v = PhotoViewer([a, b], 0, places={str(a): "SP512345"})
    assert "Grid ref SP512345" in v.title.text()
    v.step(1)
    assert "Grid ref" not in v.title.text()
    v.close()
