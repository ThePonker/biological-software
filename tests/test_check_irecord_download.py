"""scripts/check_irecord_download.py (A1, 13 Oct 2026): the sync's own matching, read-only,
on a purpose-made database and download."""
import csv
import sqlite3

from scripts import check_irecord_download as chk

HEAD = ["ID", "RecordKey", "External key", "Taxon", "Date from", "Output map ref",
        "Site name", "Input on date"]


def _db(path):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, irecord_id INTEGER, "
              "irecord_key TEXT, observatum_key TEXT, species_name TEXT, date TEXT)")
    c.executemany("INSERT INTO observations VALUES (?,?,?,?,?,?)", [
        (1, 100, None, "uuid-a", "Abax parallelepipedus", "2026-06-01"),   # held by ID
        (2, None, None, "OBS-WJH-20260601-000001", "Carabus nemoralis", "2026-06-01"),
        (3, None, None, "OBS-SHARED", "Pterostichus niger", "2026-06-02"),
        (4, None, None, "OBS-SHARED", "Pterostichus niger", "2026-06-02"),
    ])
    c.commit()
    c.close()


def _download(path, extra):
    rows = [
        ["100", "", "uuid-a", "Abax parallelepipedus", "01/06/2026", "SP5240", "X", "02/06/2026"],
        ["201", "", "OBS-WJH-20260601-000001", "Carabus nemoralis", "01/06/2026", "SP5240",
         "X", "02/06/2026"],
        ["202", "", "OBS-SHARED", "Pterostichus niger", "02/06/2026", "SP5240", "X", "03/06/2026"],
    ] + extra
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEAD)
        w.writerows(rows)


def _test_rows(n):
    return [[str(57539740 + i), "", f"OBS-WJH-IRTEST-20261013-{i:04d}", "Eudemis profundana",
             "26/06/2026", "SP521403", "Farthinghoe Nature Reserve", "13/10/2026"]
            for i in range(1, n + 1)]


def _run(tmp_path, extra, expect=3):
    db, dl, out = tmp_path / "o.db", tmp_path / "d.csv", tmp_path / "out.csv"
    _db(db)
    _download(dl, extra)
    before = (tmp_path / "o.db").read_bytes()
    assert chk.main([str(dl), "--db", str(db), "--expect", str(expect), "--csv", str(out)]) == 0
    assert (tmp_path / "o.db").read_bytes() == before            # read only
    with open(out, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def test_test_set_found_and_added_once(tmp_path, capsys):
    rows = _run(tmp_path, _test_rows(3))
    text = capsys.readouterr().out
    assert "update (iRecord ID)" in text
    assert "update (External key)" in text
    assert "add as new (key names several records)" in text
    assert "3 found, 3 expected" in text and "missing numbers: none" in text
    assert "RESULT: all keys came back once" in text
    assert {r["outcome"] for r in rows} == {"add as new"} and len(rows) == 3


def test_missing_and_twice_reported(tmp_path, capsys):
    extra = _test_rows(2)
    extra.append(list(extra[0]))
    extra[-1][0] = "57539999"                                      # same key, second ID
    _run(tmp_path, extra)
    text = capsys.readouterr().out
    assert "missing numbers: 3" in text
    assert "OBS-WJH-IRTEST-20261013-0001" in text.split("keys appearing twice:")[1].splitlines()[0]
    assert "not the expected clean result" in text
