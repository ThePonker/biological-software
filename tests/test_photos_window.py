"""PhotosWindow: ordering, missing files, empty state."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SPECIES = "Carabus nemoralis"


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def library(tmp_path, monkeypatch, qapp):
    from PySide6.QtGui import QImage
    import paths
    from shared import photo_files
    folder = tmp_path / "Photos" / "Life" / "Insecta" / "Carabidae" / SPECIES
    (folder / "Specimen").mkdir(parents=True)
    spec = folder / "Specimen" / f"{SPECIES} 1.i.20.jpg"
    gen = folder / f"{SPECIES} - Ground Beetle.jpg"
    for f in (spec, gen):
        assert QImage(10, 10, QImage.Format.Format_RGB32).save(str(f))
    monkeypatch.setattr(paths, "MEDIA_ROOT", tmp_path)
    photo_files.refresh()
    yield photo_files.rel(spec), photo_files.rel(gen)
    photo_files.refresh()


def _window(species, record_paths):
    from src.views.dialogs.photos_window import PhotosWindow
    return PhotosWindow(species, record_paths)


def test_record_photo_first_and_counted(library):
    spec, gen = library
    w = _window(SPECIES, [spec])
    assert w.paths == [spec, gen]
    assert w.record_count == 1
    assert w.list.count() == 2
    assert "This record" in w.list.item(0).toolTip()
    assert "1 of this record" in w.header.text()


def test_missing_record_path_listed_as_not_found(library):
    w = _window(SPECIES, ["Photos/Life/Gone/missing.jpg"])
    assert w.paths[0] == "Photos/Life/Gone/missing.jpg"
    assert "file not found" in w.list.item(0).text()
    assert w.list.count() == 3


def test_empty_species_shows_empty_state(library):
    w = _window("Nonexistent species", [])
    assert w.paths == []
    assert w.list.count() == 0
    assert w.empty_label.text() == "No photos of this species in the photo library yet."
    assert "of this record" not in w.header.text()


def test_specimen_photos_first_for_a_specimen(library):
    spec, gen = library
    from src.views.dialogs.photos_window import PhotosWindow
    assert PhotosWindow(SPECIES, [], record_kind="specimen", record_id=1).paths == [spec, gen]
    assert PhotosWindow(SPECIES, [], record_kind="observation", record_id=1).paths == [gen, spec]


def test_link_and_unlink_by_hand(library, tmp_path):
    import sqlite3
    from src.views.dialogs.photos_window import PhotosWindow
    from shared import photo_links
    spec, gen = library
    db = tmp_path / "o.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE specimens (id INTEGER PRIMARY KEY, species_name TEXT, observation_id INTEGER)")
    c.execute("INSERT INTO specimens VALUES (7, ?, NULL)", (SPECIES,))
    photo_links.ensure_schema(c)
    c.commit()
    c.close()
    w = PhotosWindow(SPECIES, [], record_kind="specimen", record_id=7, db_path=str(db))
    counts = []
    w.links_changed.connect(counts.append)
    w.list.setCurrentRow(w.paths.index(spec))
    assert w.link_btn.isEnabled() and not w.unlink_btn.isEnabled()
    w._link()
    assert w.record_count == 1 and w.paths[0] == spec and counts == [1]
    w.list.setCurrentRow(0)
    assert w.unlink_btn.isEnabled()
    w._unlink()
    assert w.record_count == 0 and counts == [1, 0]
    c = sqlite3.connect(db)
    assert photo_links.photos_for_specimen(c, 7) == []
    assert (tmp_path / spec).is_file()                       # the photo itself untouched


def test_record_photo_has_the_band_drawn(library):
    from PySide6.QtCore import QCoreApplication
    from src.views.dialogs.photos_window import PhotosWindow, THUMB
    spec, gen = library
    w = PhotosWindow(SPECIES, [spec])
    while w._timer.isActive():
        QCoreApplication.processEvents()
        w._load_batch()
    img = w.list.item(0).icon().pixmap(THUMB, THUMB).toImage()
    plain = w.list.item(1).icon().pixmap(THUMB, THUMB).toImage()
    assert img.pixelColor(THUMB // 2, 2) != plain.pixelColor(THUMB // 2, 2)
