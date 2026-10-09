"""shared/import_core and the scheme duplicate check (I7b, 9 Oct 2026).

In-memory / temp-file databases only; nothing real is touched."""
import contextlib
import sqlite3

import pytest

from shared import import_core as ic


class FakeDB:
    """The three calls the wizards make on Observatum's database manager."""

    def __init__(self, path):
        self.path = str(path)

    @contextlib.contextmanager
    def _c(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        try:
            yield c
        finally:
            c.close()

    def execute_main(self, q, p=()):
        with self._c() as c:
            return c.execute(q, p).fetchall()

    def execute_main_write(self, q, p=()):
        with self._c() as c:
            cur = c.execute(q, p)
            c.commit()
            return cur.lastrowid or cur.rowcount

    def execute_main_many(self, q, ps):
        with self._c() as c:
            cur = c.executemany(q, ps)
            c.commit()
            return cur.rowcount


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "obs.db"
    c = sqlite3.connect(p)
    c.execute("""CREATE TABLE recording_scheme (id INTEGER PRIMARY KEY, irecord_id INTEGER UNIQUE,
                 record_key TEXT, nbn_atlas_id TEXT, species_name TEXT NOT NULL, date TEXT,
                 comment TEXT, verifier TEXT, quantity INTEGER DEFAULT 1)""")
    c.commit()
    c.close()
    return FakeDB(p)


def test_read_table_file_keeps_the_id_column_behind_a_bom(tmp_path):
    f = tmp_path / "irecord.csv"
    f.write_bytes("﻿ID,Taxon,Comment\r\n17,Carabus nemoralis,\"two\r\nlines\"\r\n".encode("utf-8"))
    cols, rows, enc = ic.read_table_file(str(f))
    assert cols[0] == "ID" and rows[0]["ID"] == "17"          # the 35,104-ID fault
    assert rows[0]["Comment"] == "two\r\nlines"                 # quoted newline kept whole
    f.write_bytes("ID\tTaxon\n1\tNebria caf\xe9\n".encode("cp1252"))
    cols, rows, enc = ic.read_table_file(str(f))
    assert cols == ["ID", "Taxon"] and rows[0]["Taxon"].endswith("é") and enc == "cp1252"


@pytest.mark.parametrize("text, out", [
    ("12", (12, None)), ("3.0", (3, None)), ("c.20", (20, "c.20")), ("5+", (5, "5+")),
    ("ca 7", (7, "ca 7")), ("2 (Exact)", (2, "2 (Exact)")), ("1 Adult (Exact)", (1, "1 Adult (Exact)")), ("many", (None, "many")), ("10-20", (None, "10-20")),
    ("", (None, None)), (None, (None, None))])
def test_parse_quantity(text, out):
    assert ic.parse_quantity(text) == out


def test_insert_rows_fixed_columns_and_row_by_row_fallback(db):
    recs = [{"species_name": "A", "irecord_id": 1},                     # no comment in row 0 ...
            {"species_name": "B", "irecord_id": 2, "comment": "kept"},  # ... used to drop it for all
            {"species_name": "C", "irecord_id": 1},                     # clashes: batch fails
            {"species_name": "D", "verifier": "V", "unknown_col": "x"}]
    ok, fails = ic.insert_rows(db, "recording_scheme", recs)
    assert ok == 3 and len(fails) == 1 and fails[0][0] == "C" and "UNIQUE" in fails[0][1]
    got = {r["species_name"]: (r["comment"], r["verifier"])
           for r in db.execute_main("SELECT * FROM recording_scheme")}
    assert got == {"A": (None, None), "B": ("kept", None), "D": (None, "V")}


def test_chunked_select_chunks_and_raises(db):
    db.execute_main_many("INSERT INTO recording_scheme (species_name, irecord_id) VALUES ('x', ?)",
                         [(i,) for i in range(2000)])
    rows = ic.chunked_select(db, "SELECT irecord_id FROM recording_scheme WHERE irecord_id IN ({ph})",
                             list(range(0, 4000, 2)))
    assert len(rows) == 1000
    with pytest.raises(sqlite3.Error):
        ic.chunked_select(db, "SELECT nope FROM recording_scheme WHERE id IN ({ph})", [1])


def test_taxonomy_for_tvks_gives_sort_key_and_subfamily(tmp_path):
    u = tmp_path / "uksi.db"
    c = sqlite3.connect(u)
    c.execute('CREATE TABLE taxa (tvk, scientific_name, rank, parent_tvk, "order", family, superfamily, sort_code)')
    c.executemany("INSERT INTO taxa VALUES (?,?,?,?,?,?,?,?)", [
        ("SF", "Carabinae", "Subfamily", "F", "Coleoptera", "Carabidae", "Caraboidea", 15000),
        ("G", "Carabus", "Genus", "SF", "Coleoptera", "Carabidae", "Caraboidea", 15010),
        ("S", "Carabus nemoralis", "Species", "G", "Coleoptera", "Carabidae", "Caraboidea", 15012)])
    c.commit()
    c.close()
    t = ic.taxonomy_for_tvks(["S", "S", "missing", ""], uksi_path=u)
    assert set(t) == {"S"}
    assert t["S"]["subfamily"] == "Carabinae" and t["S"]["superfamily"] == "Caraboidea"
    assert t["S"]["sort_key"] > 15012 and t["S"]["order_name"] == "Coleoptera"


def test_scheme_duplicate_check_matches_record_key_and_repeats(db):
    pd = pytest.importorskip("pandas")
    pytest.importorskip("PySide6")
    import importlib.util
    import sys
    import types
    if importlib.util.find_spec("PySide6.QtWebEngineWidgets") is None:     # headless test machine
        from PySide6.QtWidgets import QWidget
        for m in ("PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineCore", "PySide6.QtWebChannel"):
            mod = types.ModuleType(m)
            for n in ("QWebEngineView", "QWebEnginePage", "QWebEngineSettings", "QWebEngineProfile", "QWebChannel"):
                setattr(mod, n, type(n, (QWidget,), {}))
            sys.modules.setdefault(m, mod)
    from src.views.dialogs.scheme_import_wizard import validation_worker as vw
    db.execute_main_write("INSERT INTO recording_scheme (species_name, record_key) VALUES ('held, ID lost', 'iBRC500')")
    db.execute_main_write("INSERT INTO recording_scheme (species_name, nbn_atlas_id) VALUES ('nbn', 'N1')")
    w = vw.SchemeValidationWorker.__new__(vw.SchemeValidationWorker)
    w.db_manager = db
    df = pd.DataFrame([
        {"row_number": 2, "irecord_id": 500, "record_key": "iBRC500", "nbn_atlas_id": ""},  # held via key
        {"row_number": 3, "irecord_id": 501, "record_key": "iBRC501", "nbn_atlas_id": ""},  # new
        {"row_number": 4, "irecord_id": 501, "record_key": "iBRC501", "nbn_atlas_id": ""},  # repeat of row 3
        {"row_number": 5, "irecord_id": None, "record_key": "", "nbn_atlas_id": "N1"}])     # held NBN
    out = w._batch_duplicate_check(df)
    assert out["is_duplicate"].tolist() == [True, False, False, True]
    assert out.loc[2, "dup_error"].startswith("Same record as row 3")
    w.db_manager = FakeDB("/nonexistent/dir/x.db")                   # a lookup that fails ...
    out = w._batch_duplicate_check(df.drop(columns=["is_duplicate", "existing_record_id", "dup_error"]))
    assert all(e.startswith("Duplicate check failed") for e in out["dup_error"])   # ... stops all
