"""R18 B2: an exception in the specimen wizard's species lookup marks that row unmatched with the
error text, is logged by crash_log.note, and validation still finishes."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, "Observatum")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from shared.species_lookup import LookupFailure  # noqa: E402
from src.views.dialogs.specimen_import_wizard import validation_worker as vw  # noqa: E402


class _Model:                                    # truthy stand-in for the UKSI model
    pass


def _run(names, monkeypatch, fake_lookup, notes):
    monkeypatch.setattr(vw, "lookup_names", fake_lookup)
    monkeypatch.setattr(vw.crash_log, "note", lambda text, exc=None: notes.append(text))
    rows = [vw.ImportRow(row_number=i + 2, raw_data={"Species": n, "Date": "01/06/2024"})
            for i, n in enumerate(names)]
    w = vw.ValidationWorker(rows, {"species_name": "Species", "date_collected": "Date"}, _Model(),
                            vc_db_path=None)
    got = []
    w.finished.connect(lambda r: got.extend(r))
    w.run()
    return got


def _not_found(names, *_a, **_k):
    return {n: LookupFailure(n, "not_found") for n in names}


def test_batch_exception_marks_only_the_failing_name(monkeypatch):
    notes = []

    def fake(names, uksi, **kw):
        if len(names) > 1 or names == ["Boom boom"]:
            raise RuntimeError("fuzzy blew up")
        return _not_found(names)

    got = _run(["Fine fine", "Boom boom"], monkeypatch, fake, notes)
    assert len(got) == 2                                       # validation finished
    by = {r.raw_data["Species"]: r for r in got}
    assert "fuzzy blew up" in by["Boom boom"].error_message
    assert by["Boom boom"].status == vw.RowStatus.ERROR and not by["Boom boom"].species_tvk
    assert "fuzzy blew up" not in by["Fine fine"].error_message     # the other name was looked up
    assert any("Boom boom" in n and "fuzzy blew up" in n for n in notes)


def test_row_exception_marks_the_row_and_the_rest_carry_on(monkeypatch):
    notes = []
    orig = vw.ValidationWorker._apply_species_row

    def flaky(self, df, idx, row, lookup):
        if row["species_name"] == "Row bad":
            raise ValueError("row broke")
        return orig(self, df, idx, row, lookup)

    monkeypatch.setattr(vw.ValidationWorker, "_apply_species_row", flaky)
    got = _run(["Row bad", "Row ok"], monkeypatch, lambda names, uksi, **kw: _not_found(names), notes)
    by = {r.raw_data["Species"]: r for r in got}
    assert len(got) == 2 and "row broke" in by["Row bad"].error_message
    assert by["Row bad"].status == vw.RowStatus.ERROR
    assert "Row ok" in by["Row ok"].error_message                # its own not-found text
    assert any("Row bad" in n for n in notes)


def test_nothing_failing_changes_nothing(monkeypatch):
    notes = []
    got = _run(["A a", "B b"], monkeypatch, lambda names, uksi, **kw: _not_found(names), notes)
    assert notes == [] and all("Not found" in r.error_message or "not found" in r.error_message.lower()
                               for r in got)
