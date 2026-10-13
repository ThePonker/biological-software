"""One place for saved filters (13 Oct 2026): the filter bar's top row saves/loads the bar
AND the Filter Wizard's chips; the wizard has no save/load/reset/apply row any more.

Temp INI QSettings and temp JSON only -- never the app's real settings or data."""
import os
import types

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QSettings  # noqa: E402
from PySide6.QtWidgets import QComboBox, QLineEdit, QPushButton  # noqa: E402

CHIPS = {"species": ["Rutpela maculata", "~Lamia"], "year": 2019,
         "site_name": ["Wytham Woods"], "notes_search": ["~oak"]}


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def ini(qapp, tmp_path):
    """QSettings on a temp INI file under a test organisation."""
    old_fmt = QSettings.defaultFormat()
    org, app = QCoreApplication.organizationName(), QCoreApplication.applicationName()
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    QCoreApplication.setOrganizationName("ObservatumTestsSavedFilters")
    QCoreApplication.setApplicationName("one_place")
    QSettings().clear()
    yield tmp_path
    QSettings().clear()
    QCoreApplication.setOrganizationName(org)
    QCoreApplication.setApplicationName(app)
    QSettings.setDefaultFormat(old_fmt)


@pytest.fixture
def no_wizard_json(monkeypatch, tmp_path):
    """The bars read wizard-saved filters from an empty temp file, never data/."""
    from src.services.saved_filters_service import SavedFiltersService
    from src.views.components import saved_filters_mixin as m
    monkeypatch.setattr(m, "SavedFiltersService",
                        lambda: SavedFiltersService(tmp_path / "none.json"))


class Holder:
    """Stands in for a tab: a real wizard and the quiet setter."""

    def __init__(self):
        from src.views.components.filter_wizard.filter_wizard import FilterWizard
        self.wizard = FilterWizard(tab_name="observations")

    def set_chips(self, chips):
        self.wizard.set_filters(chips)


def _bar_with_wizard(qapp):
    from src.views.observations.observation_filter_bar import ObservationFilterBar
    bar = ObservationFilterBar()
    h = Holder()
    bar.attach_wizard(h.wizard.get_all_filters, h.set_chips)
    return bar, h


def test_save_and_select_restores_bar_and_chips_with_one_reload(ini, no_wizard_json, qapp,
                                                                monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    bar, h = _bar_with_wizard(qapp)
    bar.species_edit.setText("Lamia textor")
    h.wizard.set_filters(CHIPS)
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("Both", True)))
    bar._on_save_filter()
    assert bar._saved_filters[-1]["filters"]["wizard"] == CHIPS

    # a new bar (as after a restart) reads the list back from QSettings
    bar2, h2 = _bar_with_wizard(qapp)
    assert [s["name"] for s in bar2._saved_filters] == ["Both"]
    assert bar2._saved_filters[0]["filters"]["wizard"] == CHIPS      # round trip, equal
    seen = []
    bar2.filters_changed.connect(lambda f: seen.append((dict(f), dict(h2.wizard.get_all_filters()))))
    bar2.saved_combo.setCurrentIndex(bar2.saved_combo.findText("Both"))
    assert len(seen) == 1                                            # one reload only
    assert seen[0][1] == CHIPS                                       # chips already in place
    assert bar2.species_edit.text() == "Lamia textor"
    assert h2.wizard.get_all_filters() == CHIPS


def test_one_element_list_coming_back_as_str_is_normalised(ini, no_wizard_json, qapp):
    from src.views.components.saved_filters_mixin import normalise_chips
    out = normalise_chips({"species": "Lamia textor", "year": 2019, "date_from": "2020-01-01",
                           "site_name": ["~Wood", "Oak"]})
    assert out == {"species": ["Lamia textor"], "year": 2019, "date_from": "2020-01-01",
                   "site_name": ["~Wood", "Oak"]}


def test_bar_only_saved_filter_clears_wizard_chips(ini, no_wizard_json, qapp):
    bar, h = _bar_with_wizard(qapp)
    bar.add_saved_filter("BarOnly", {"species": "Lamia"})
    h.wizard.set_filters(CHIPS)
    bar.saved_combo.setCurrentIndex(bar.saved_combo.findText("BarOnly"))
    assert h.wizard.get_all_filters() == {}
    assert bar.species_edit.text() == "Lamia"


def test_wizard_only_saved_filter_blanks_the_bar_boxes(ini, no_wizard_json, qapp):
    bar, h = _bar_with_wizard(qapp)
    bar.species_edit.setText("stale")
    bar.add_saved_filter("WizOnly", {"wizard": CHIPS})
    bar.saved_combo.setCurrentIndex(bar.saved_combo.findText("WizOnly"))
    assert bar.species_edit.text() == ""
    assert h.wizard.get_all_filters() == CHIPS


@pytest.mark.parametrize("which", ["scheme", "collection"])
def test_other_bars_ignore_the_wizard_key(ini, no_wizard_json, qapp, which):
    if which == "scheme":
        from src.views.scheme.scheme_filter_bar import SchemeFilterBar as Bar
    else:
        from src.views.collection.collection_filters import CollectionFilterBar as Bar
    bar = Bar()
    bar.attach_wizard(lambda: {}, lambda c: None)
    got = []
    bar.filters_changed.connect(got.append)
    bar._apply_saved_filter({"species": "Lamia", "wizard": CHIPS})
    assert len(got) == 1 and bar.species_edit.text() == "Lamia"


def test_tab_quiet_setters_set_state_and_cards(qapp):
    from src.views.scheme.recording_scheme_tab import RecordingSchemeTab
    from src.views.collection.insect_collection_tab import InsectCollectionTab
    for cls in (RecordingSchemeTab, InsectCollectionTab):
        ns = types.SimpleNamespace(_wizard_filters={}, filter_wizard=Holder().wizard)
        cls.set_wizard_filters_quietly(ns, CHIPS)
        assert ns._wizard_filters == CHIPS and ns.filter_wizard.get_all_filters() == CHIPS


def test_migration_moves_wizard_json_once(ini, qapp, tmp_path, monkeypatch):
    from src.services.saved_filters_service import SavedFiltersService
    from src.views.components import saved_filters_mixin as m
    from src.views.observations.observation_filter_bar import ObservationFilterBar
    path = tmp_path / "saved_filters.json"
    svc = SavedFiltersService(path)
    svc.save_filter("Oak", {"notes_search": ["~oak"], "year": 2024}, tab="observations")
    svc.save_filter("Clash", {"year": 2020}, tab="observations")
    svc.save_filter("Other", {"year": 2021}, tab="recording_scheme")
    before = path.read_text()
    monkeypatch.setattr(m, "SavedFiltersService", lambda: SavedFiltersService(path))

    first = ObservationFilterBar()                           # migrates at init
    assert sorted(s["name"] for s in first._saved_filters) == ["Clash", "Oak"]
    second = ObservationFilterBar()
    names2 = [s["name"] for s in second._saved_filters]
    assert names2.count("Oak") == 1                          # flag stops a second copy
    assert "Other" not in names2                              # other tabs' entries stay out
    oak = next(s for s in second._saved_filters if s["name"] == "Oak")
    assert oak["filters"] == {"wizard": {"notes_search": ["~oak"], "year": 2024}}
    assert path.read_text() == before                         # JSON untouched


def test_migration_name_clash_gets_wizard_suffix(ini, qapp, tmp_path, monkeypatch):
    from src.services.saved_filters_service import SavedFiltersService
    from src.views.components import saved_filters_mixin as m
    from src.views.observations.observation_filter_bar import ObservationFilterBar
    # a top-row filter called "Clash" already exists in QSettings
    s = QSettings()
    s.beginWriteArray(ObservationFilterBar._settings_key)
    s.setArrayIndex(0)
    s.setValue("name", "Clash")
    s.setValue("filters", {"species": "x"})
    s.endArray()
    path = tmp_path / "saved_filters.json"
    SavedFiltersService(path).save_filter("Clash", {"year": 2020}, tab="observations")
    monkeypatch.setattr(m, "SavedFiltersService", lambda: SavedFiltersService(path))
    bar = ObservationFilterBar()
    names = [x["name"] for x in bar._saved_filters]
    assert names == ["Clash", "Clash (wizard)"]
    assert len(ObservationFilterBar()._saved_filters) == 2            # flag: no third copy


def test_accepting_a_card_dialog_applies(qapp, monkeypatch):
    from PySide6.QtWidgets import QDialog
    from src.views.components.filter_wizard import filter_wizard as fw

    class FakeDialog:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def get_values(self):
            return {"year": 2019}

    monkeypatch.setattr(fw, "WhenFilterDialog", FakeDialog)
    w = fw.FilterWizard(tab_name="observations")
    monkeypatch.setattr(w, "_ensure_tab_values", lambda: None)
    applied = []
    w.filters_applied.connect(applied.append)
    w._on_card_clicked("when")
    assert applied == [{"year": 2019}]


def test_wizard_has_no_save_row(qapp):
    from src.views.components.filter_wizard.filter_wizard import FilterWizard
    w = FilterWizard(tab_name="observations")
    assert not w.findChildren(QComboBox)
    assert not w.findChildren(QLineEdit)
    assert not w.findChildren(QPushButton)
    for gone in ("_add_save_controls", "_save_filter", "_delete_saved_filter",
                 "_on_load_saved_filter", "_load_saved_filter_names", "_reset_filters",
                 "_get_saved_filters_service"):
        assert not hasattr(w, gone)
    w.clear_filters()      # does not touch a removed combo
