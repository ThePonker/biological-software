"""Read back checking (17 Oct 2026): the export's row list, reading a filled-in reply (xlsx and
CSV), what each answer does, and applying it through the grid. Purpose-made databases only."""
import csv
import json
import sqlite3

import pytest

import paths
from shared import photo_files as pf
from shared import photo_links as pl


@pytest.fixture
def lib(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "MEDIA_ROOT", tmp_path / "Media")
    monkeypatch.setattr(paths, "PHOTO_MOVES_DIR", tmp_path / "logs")
    (tmp_path / "Media" / "Photos" / "_Bench").mkdir(parents=True)
    pf.refresh()
    from DataEntry import staging_repo as repo
    conn = sqlite3.connect(tmp_path / "observatum.db")
    conn.row_factory = sqlite3.Row
    repo.ensure_schema(conn)
    pl.ensure_schema(conn)
    yield tmp_path, conn, repo
    pf.refresh()


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _job_with_rows(conn, repo):
    jid = repo.create_job(conn, "Coedely test", "Personal", None, None)
    base = {"species_tvk": "T0", "date": "2026-06-05", "quantity": "1", "recorder": "Heeney, W.J.",
            "determiner": "Heeney, W.J.", "check_flag": 1}
    names = ["Amara aenea", "Amara familiaris", "Bembidion lampros", "Stenus clavicornis",
             "Philonthus cognatus"]
    ids = [repo.insert_row(conn, jid, {**base, "species_name": n}) for n in names]
    conn.commit()
    return jid, ids


def _export(tmp, conn, repo, jid, ids):
    from DataEntry import check_export as ce
    return ce.export_for_checking(conn, repo.get_job(conn, jid), ids, ["Species", "Date"],
                                  tmp / "out")


def _fill(xlsx, answers):
    """answers: {ref: (agree, their_id, notes)} written into the reply columns."""
    from openpyxl import load_workbook
    wb = load_workbook(xlsx)
    ws = wb["For checking"]
    head = [c.value for c in ws[1]]
    col = {h: i + 1 for i, h in enumerate(head)}
    for r in range(2, ws.max_row + 1):
        ref = ws.cell(r, col["Ref"]).value
        if ref in answers:
            a, t, n = answers[ref]
            ws.cell(r, col["Agree?"]).value = a
            ws.cell(r, col["Their ID"]).value = t
            ws.cell(r, col["Notes"]).value = n
    wb.save(xlsx)


KNOWN = {"amara lunicollis": "NBNSYS0000009999", "amara aenea": "NBNSYS0000001111",
         "philonthus cognatus": "NBNSYS0000002222"}


def _resolve(text):
    """Stands in for the grid's species cell: one certain match, or None."""
    k = " ".join(text.split()).casefold()
    for name, tvk in KNOWN.items():
        if k == name or k.startswith(name + " ("):           # an author added
            return {"scientific_name": name.capitalize(), "tvk": tvk, "common_name": None,
                    "order": "Coleoptera", "family": "Carabidae", "rank": "Species"}
    return None


ANSWERS = {"R001": ("Yes", None, None),
           "R002": ("No", "Amara lunicollis", "pronotum hind angles"),
           "R003": ("?", None, "need the aedeagus"),
           "R004": (None, None, "nice specimen"),
           "R005": ("y", "Philonthus cognatus", None)}        # same name: agreement


def test_export_writes_the_row_list(lib):
    tmp, conn, repo = lib
    jid, ids = _job_with_rows(conn, repo)
    res = _export(tmp, conn, repo, jid, ids)
    from openpyxl import load_workbook
    wb = load_workbook(res["xlsx"])
    assert wb.sheetnames == ["For checking", "_rows"] and wb["_rows"].sheet_state == "hidden"
    refs = json.loads((tmp / "out" / res["folder"].split("\\")[-1].split("/")[-1]
                       / "refs.json").read_text())
    assert refs["job_id"] == jid and [r["row_id"] for r in refs["rows"]] == ids


def test_plan_and_changes(lib):
    tmp, conn, repo = lib
    jid, ids = _job_with_rows(conn, repo)
    res = _export(tmp, conn, repo, jid, ids)
    _fill(res["xlsx"], ANSWERS)
    from DataEntry import check_readback as cr
    items = cr.plan(conn, jid, cr.read_reply(res["xlsx"]), _resolve)
    assert [i["action"] for i in items] == ["agree", "new_id", "no", "note", "agree"]
    assert all(i["tick"] for i in items)
    ch = [cr.changes_for(i, "Smith, J.") for i in items]
    assert ch[0] == {"check_flag": None, "comment": "conf. Smith, J."}
    assert ch[1]["species"]["tvk"] == "NBNSYS0000009999"
    assert {k: v for k, v in ch[1].items() if k != "species"} == {"check_flag": None,
                     "determiner": "Smith, J.",
                     "comment": "det. Smith, J. (was Amara familiaris); pronotum hind angles"}
    assert ch[2] == {"check_note": "Smith, J.: ?, need the aedeagus"}
    assert ch[3] == {"check_note": "Smith, J.: nice specimen"}


def test_csv_reply_uses_refs_json_and_flags_changes(lib):
    tmp, conn, repo = lib
    jid, ids = _job_with_rows(conn, repo)
    res = _export(tmp, conn, repo, jid, ids)
    from pathlib import Path
    reply = Path(res["folder"]) / "reply.csv"
    with open(reply, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Ref", "Species", "Agree", "Their ID", "Notes"])
        w.writerow(["R001", "Amara aenea", "yes", "", ""])
        w.writerow(["R002", "Amara familiaris", "yes", "", ""])
        w.writerow(["R009", "?", "yes", "", ""])                    # not in the export
    repo.update_row(conn, ids[1], {"species_name": "Amara communis"})   # edited since
    repo.delete_row(conn, ids[0])
    conn.commit()
    from DataEntry import check_readback as cr
    items = cr.plan(conn, jid, cr.read_reply(reply))
    assert [i["action"] for i in items] == ["missing", "agree", "mismatch"]
    assert items[1]["changed"] and not items[1]["tick"]          # ask before applying


def test_reply_from_another_job_and_without_a_row_list(lib, tmp_path):
    tmp, conn, repo = lib
    jid, ids = _job_with_rows(conn, repo)
    res = _export(tmp, conn, repo, jid, ids)
    from DataEntry import check_readback as cr
    other = repo.create_job(conn, "Other", "Personal", None, None)
    items = cr.plan(conn, other, cr.read_reply(res["xlsx"]))
    assert {i["action"] for i in items} == {"other_job"} and not any(i["tick"] for i in items)
    lone = tmp_path / "elsewhere" / "reply.csv"
    lone.parent.mkdir()
    lone.write_text("Ref,Agree?\nR001,yes\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no list of which row"):
        cr.read_reply(lone)


def test_apply_through_the_grid(lib, qapp):
    tmp, conn, repo = lib
    jid, ids = _job_with_rows(conn, repo)
    res = _export(tmp, conn, repo, jid, ids)
    _fill(res["xlsx"], {**ANSWERS, "R005": ("No", "Philonthus nonexistens", None)})
    from DataEntry import check_readback as cr
    from DataEntry import entry_grid as eg
    from DataEntry.check_readback_dialog import apply_through_grid
    items = cr.plan(conn, jid, cr.read_reply(res["xlsx"]), _resolve)
    assert items[4]["action"] == "no" and items[4]["suggested"] == "Philonthus nonexistens"
    m = eg.StagingTableModel(conn, jid)
    out = apply_through_grid(m, items, "Smith, J.")
    assert out["applied"] == 5
    rows = {r["id"]: r for r in repo.fetch_rows(conn, jid)}
    a, b, c, d, e = (rows[i] for i in ids)
    assert not a["check_flag"] and a["comment"] == "conf. Smith, J."
    assert (b["species_name"], b["species_tvk"], b["determiner"], b["check_flag"]) == (
        "Amara lunicollis", "NBNSYS0000009999", "Smith, J.", None)
    assert c["check_flag"] == 1 and c["check_note"] == "Smith, J.: ?, need the aedeagus"
    assert d["check_flag"] == 1 and d["check_note"] == "Smith, J.: nice specimen"
    # an unmatched name never replaces the species: the row stays marked, the name noted
    assert (e["species_name"], e["species_tvk"], e["check_flag"]) == ("Philonthus cognatus", "T0", 1)
    assert e["check_note"] == "Smith, J.: No, Philonthus nonexistens"


@pytest.mark.parametrize("agree,their,action", [
    ("No", "?", "no"),                         # a question mark is not a name
    ("Yes", "Yes", "agree"),
    ("unsure", "Amara lunicollis", "no"),      # unsure with a name: suggested, not applied
    ("Yes - but cf.", "cf. Amara lunicollis", "no"),
    ("", "Amara lunicollis agg.", "no"),
    ("", "Amara sp.", "no"),                   # no single match
    ("Yes", "Amara familiaris", "agree"),      # their name is the row's
    ("", "-", "none"),
    ("No", "Amara lunicollis", "new_id"),
    ("", "Amara lunicollis", "new_id"),
    ("Yes", "Amara aenea (De Geer)", "new_id"),  # an author: still one species, another one
])
def test_their_id_only_changes_the_species_when_certain(lib, agree, their, action):
    tmp, conn, repo = lib
    jid, ids = _job_with_rows(conn, repo)
    res = _export(tmp, conn, repo, jid, ids)
    _fill(res["xlsx"], {"R002": (agree or None, their, None)})
    from DataEntry import check_readback as cr
    items = cr.plan(conn, jid, cr.read_reply(res["xlsx"]), _resolve)
    assert items[1]["action"] == action
    # without a resolver nothing is ever a new ID
    assert cr.plan(conn, jid, cr.read_reply(res["xlsx"]))[1]["action"] != "new_id"


def test_a_ref_twice_and_a_reply_from_another_export_are_not_applied(lib):
    tmp, conn, repo = lib
    jid, ids = _job_with_rows(conn, repo)
    res = _export(tmp, conn, repo, jid, ids)
    from openpyxl import load_workbook
    wb = load_workbook(res["xlsx"])
    ws = wb["For checking"]
    ws.append(["R001", ids[0], "Amara aenea", None, None, None, "No", "Amara lunicollis", None])
    ws.cell(3, 2).value = 999999                       # R002's row id altered
    ws.cell(4, 3).value = "Something else"             # R003's species is not the export's
    wb.save(res["xlsx"])
    _fill(res["xlsx"], {"R001": ("Yes", None, None)})
    from DataEntry import check_readback as cr
    items = cr.plan(conn, jid, cr.read_reply(res["xlsx"]), _resolve)
    acts = [i["action"] for i in items]
    assert acts[0] == "repeat" and acts[-1] == "repeat"
    assert acts[1] == "mismatch" and acts[2] == "mismatch"
    assert not any(i["tick"] for i in items if i["action"] in ("repeat", "mismatch"))


def test_a_failure_part_way_says_what_was_applied(lib, qapp):
    tmp, conn, repo = lib
    jid, ids = _job_with_rows(conn, repo)
    res = _export(tmp, conn, repo, jid, ids)
    _fill(res["xlsx"], ANSWERS)
    from DataEntry import check_readback as cr
    from DataEntry import entry_grid as eg
    from DataEntry.check_readback_dialog import apply_through_grid
    items = cr.plan(conn, jid, cr.read_reply(res["xlsx"]), _resolve)
    m = eg.StagingTableModel(conn, jid)
    real = m.setData
    calls = []

    def flaky(index, value, role=None):
        calls.append(1)
        if len(calls) > 3:
            raise sqlite3.OperationalError("disk I/O error")
        return real(index, value, role)
    m.setData = flaky
    with pytest.raises(RuntimeError, match="Already applied: R001"):
        apply_through_grid(m, items, "Smith, J.")


def test_dialog_lists_answers_and_applies_only_ticked(lib, qapp):
    tmp, conn, repo = lib
    jid, ids = _job_with_rows(conn, repo)
    res = _export(tmp, conn, repo, jid, ids)
    _fill(res["xlsx"], ANSWERS)
    from PySide6.QtCore import Qt
    from DataEntry.check_readback_dialog import CheckReadbackDialog
    got = []
    d = CheckReadbackDialog(conn, {"id": jid, "name": "Coedely test"},
                            lambda items, who: got.append((items, who)) or {"applied": len(items)})
    assert d.load(res["xlsx"]) and d.table.rowCount() == 5
    d.table.item(1, 0).setCheckState(Qt.CheckState.Unchecked)
    assert [i["ref"] for i in d.ticked()] == ["R001", "R003", "R004", "R005"]
    assert repo.fetch_rows(conn, jid)[0]["check_flag"] == 1      # nothing written by loading


# ---------------------------------------------------------------- the test-job copy script

def _live(tmp_path):
    from DataEntry import staging_repo as repo
    p = tmp_path / "observatum.db"
    c = sqlite3.connect(p)
    c.row_factory = sqlite3.Row
    repo.ensure_schema(c)
    pl.ensure_schema(c)
    jid = repo.create_job(c, "RWE Wales Coedely", "Commercial", "RWE", "Coedely")
    a = repo.insert_row(c, jid, {"species_name": "Amara aenea", "check_flag": 1, "check_note": "?"})
    repo.insert_row(c, jid, {"species_name": "Bembidion lampros"})
    pl.add_staging_link(c, "Photos/_Bench/a.jpg", a)
    c.commit()
    c.close()
    return p, jid


def test_copy_script_dry_run_then_apply(tmp_path, capsys):
    from scripts import copy_job_for_test as cj
    db, jid = _live(tmp_path)
    before = db.read_bytes()
    assert cj.main(["--job", "coedely", "--db", str(db), "--backup-dir", str(tmp_path / "b")]) == 0
    assert "DRY RUN" in capsys.readouterr().out and db.read_bytes() == before
    assert cj.main(["--job", "coedely", "--apply", "--db", str(db),
                    "--backup-dir", str(tmp_path / "b")]) == 0
    assert "done." in capsys.readouterr().out and len(list((tmp_path / "b").iterdir())) == 1
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    from DataEntry import staging_repo as repo
    test = [j for j in repo.list_jobs(c) if repo.is_test_copy(j)]
    assert [j["name"] for j in test] == ["TEST copy of RWE Wales Coedely"]
    repo.update_job(c, test[0]["id"], name="Renamed")          # the note keeps the guard
    assert repo.is_test_copy(repo.get_job(c, test[0]["id"]))
    rows = repo.fetch_rows(c, test[0]["id"])
    assert [(r["species_name"], r["check_flag"], r["check_note"]) for r in rows] == [
        ("Amara aenea", 1, "?")]
    assert pl.photos_for_staging(c, rows[0]["id"]) == []          # photos stay with the original
    assert len(repo.fetch_rows(c, jid)) == 2                      # original untouched
    c.close()
    # a second copy of the same job is a new job; the test copies are not offered as sources
    assert cj.main(["--job", "TEST copy", "--db", str(db)]) == 1


def test_test_copy_cannot_be_committed_or_exported(lib):
    tmp, conn, repo = lib
    jid = repo.create_job(conn, "TEST copy of Coedely", "Personal")
    job = repo.get_job(conn, jid)
    from DataEntry import commit_service, irecord_export
    with pytest.raises(ValueError, match="test copy"):
        commit_service.commit_job(None, None, conn, job)
    with pytest.raises(ValueError, match="test copy"):
        irecord_export.export_job(conn, job, str(tmp / "x.csv"))


def test_the_grid_refuses_to_commit_a_test_copy_before_asking(lib, qapp, monkeypatch):
    """Wil's test, 17 Oct: Commit asked "Write this job's records?" first; now the button is
    off and the page refuses before any question."""
    tmp, conn, repo = lib
    jid = repo.create_job(conn, "TEST copy of Coedely", "Personal")
    repo.insert_row(conn, jid, {"species_name": "Amara aenea", "date": "2026-06-05"})
    from DataEntry import entry_grid as eg
    from PySide6.QtWidgets import QMessageBox
    asked = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: asked.append(a) or None)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: asked.append(("info",) + a))
    page = eg.EntryGridPage.__new__(eg.EntryGridPage)        # only what _do_commit reads
    page._job = repo.get_job(conn, jid)
    page._commit_cb = lambda *a: None
    eg.EntryGridPage._do_commit(page)
    assert len(asked) == 1 and asked[0][0] == "info" and "test copy" in asked[0][-1]
