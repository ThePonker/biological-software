"""PhotoAttachDialog: names, moving bench photos into the holding folder (_Bench), links."""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SPECIES = "Amara aenea"


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def env(tmp_path, monkeypatch, qapp):
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QImage
    import paths
    from shared import photo_files, photo_links
    from DataEntry import photo_attach
    (tmp_path / "Photos" / "Life" / "Insecta" / "Coleoptera" / "Carabidae" / SPECIES).mkdir(parents=True)
    monkeypatch.setattr(paths, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(photo_files, "new_log_path", lambda: tmp_path / "moves.csv")
    photo_files.refresh()
    cap = tmp_path / "capture"
    cap.mkdir()
    files = []
    for i, name in enumerate(("a.jpg", "b.jpg")):
        f = cap / name
        assert QImage(8, 8, QImage.Format.Format_RGB32).save(str(f))
        os.utime(f, (1_700_000_000 + i * 100, 1_700_000_000 + i * 100))
        files.append(f)
    s = QSettings("Flauna", "Observatum")
    old = s.value(photo_attach.KEY_FOLDER)
    s.setValue(photo_attach.KEY_FOLDER, str(cap))
    conn = sqlite3.connect(":memory:")
    photo_links.ensure_schema(conn)
    yield tmp_path, cap, files, conn
    if old is None:
        s.remove(photo_attach.KEY_FOLDER)
    else:
        s.setValue(photo_attach.KEY_FOLDER, old)
    photo_files.refresh()


def test_name_for():
    from DataEntry.photo_attach import name_for
    row = {"species_name": SPECIES, "sex": "Male", "date": "05/06/2026"}
    assert name_for(row, "gen") == "Amara aenea male gen 5.vi.26"
    assert name_for({**row, "date": "06/2026"}, "gen") == "Amara aenea male gen"


def _row(species=SPECIES, **kw):
    return {"id": 7, "species_name": species, "sex": "Male", "date": "05/06/2026",
            "family": "Carabidae", "order_name": "Coleoptera", **kw}


def test_attach_moves_oldest_first(env):
    from DataEntry.photo_attach import PhotoAttachDialog
    from shared import photo_links
    root, cap, files, conn = env
    dlg = PhotoAttachDialog(conn, _row())
    assert dlg.list.count() == 2
    assert dlg.list.item(0).data(256) == str(files[1])          # newest first
    dlg.view_box.setCurrentText("gen")
    dlg.list.selectAll()
    dlg._attach()
    spec = root / "Photos/_Bench"                       # take 2: held until commit
    assert not (root / "Photos/Life/Insecta/Coleoptera/Carabidae" / SPECIES / "Specimen").exists()
    assert sorted(p.name for p in spec.iterdir()) == [
        "Amara aenea male gen 5.vi.26 2.jpg", "Amara aenea male gen 5.vi.26.jpg"]
    assert (spec / "Amara aenea male gen 5.vi.26.jpg").stat().st_mtime == 1_700_000_000
    assert list(cap.iterdir()) == []
    assert dlg.attached == 2
    assert len(photo_links.photos_for_staging(conn, 7)) == 2
    assert "now 2 on this row" in dlg._msg.text()


def test_attach_makes_no_library_folder(env):
    from DataEntry.photo_attach import PhotoAttachDialog
    root, cap, files, conn = env
    dlg = PhotoAttachDialog(conn, _row("Nebria brevicollis", family="", order_name=""))
    dlg.list.item(0).setSelected(True)
    dlg._attach()
    assert [p.name for p in (root / "Photos/_Bench").iterdir()] == ["Nebria brevicollis male 5.vi.26.jpg"]
    assert not (root / "Photos/Life/_New species").exists()
