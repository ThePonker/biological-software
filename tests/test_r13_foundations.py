"""Round 13 foundations: one settings store, one sex list, one date reader, one VC path.

Built in tmp_path / the conftest settings sandbox; nothing here reads Wil's live data.
"""
import datetime as dt

import pytest
from PySide6.QtCore import QCoreApplication

import paths
from shared import settings_store as ss
from shared import vocab

# ---------------------------------------------------------------- the date table
# (input, DataEntry.date_utils.parse, DataEntry.date_utils.to_iso, parse_display_date with
#  dd/mm/yyyy chosen, parse_display_date with mm/dd/yyyy chosen, unreadable_full_date)
# OLD is what the functions gave BEFORE the refactor (generated from the old code, 24 Oct 2026).
# NEW_WHERE_DIFFERENT lists the intended differences: every one was unreadable (None / True)
# before and is a real date now.
OLD = [('2026-06-05', ('2026-06-05', 'D'), '2026-06-05', '2026-06-05', '2026-06-05', False),
 ('2026-6-5', ('2026-06-05', 'D'), '2026-06-05', '2026-06-05', '2026-06-05', False),
 ('5/6/2026', ('2026-06-05', 'D'), '2026-06-05', '2026-06-05', '2026-05-06', False),
 ('05.06.2026', ('2026-06-05', 'D'), '2026-06-05', None, None, True),
 ('5-6-2026', ('2026-06-05', 'D'), '2026-06-05', '2026-06-05', '2026-06-05', False),
 ('5/6/26', ('2026-06-05', 'D'), '2026-06-05', None, None, True),
 ('1/1/99', ('2099-01-01', 'D'), '2099-01-01', None, None, True),
 ('31/02/2026', None, None, None, None, True),
 ('2026-02-30', None, None, None, None, False),
 ('13/13/2026', None, None, None, None, True),
 ('2026', ('2026', 'Y'), None, None, None, False),
 ('1650', None, None, None, None, False),
 ('06/2026', ('2026-06', 'O'), None, None, None, False),
 ('6/2026', ('2026-06', 'O'), None, None, None, False),
 ('2026-06', ('2026-06', 'O'), None, None, None, False),
 ('2026-6', ('2026-06', 'O'), None, None, None, False),
 ('Jun 2026', ('2026-06', 'O'), None, None, None, False),
 ('June 2026', ('2026-06', 'O'), None, None, None, False),
 ('sept 2026', ('2026-09', 'O'), None, None, None, False),
 ('Sept 2026', ('2026-09', 'O'), None, None, None, False),
 ('Foo 2026', None, None, None, None, False),
 ('13/2026', None, None, None, None, False),
 ('', None, None, None, None, False),
 ('  ', None, None, None, None, False),
 ('summer', None, None, None, None, False),
 ('6 June 2021', None, None, '2021-06-06', '2021-06-06', False),
 ('6.vi.2021', None, None, None, None, False),
 ('vi.2021', None, None, None, None, False),
 ('15 Jun 2024', None, None, '2024-06-15', '2024-06-15', False),
 ('15th June 2024', None, None, None, None, False),
 ('2024/06/01', None, None, None, None, False),
 ('2024-05-01/2024-05-15', None, None, '2024-05-01', '2024-05-01', False),
 ('1/5/2024 to 15/5/2024', None, None, None, None, False),
 ('2019-2021', None, None, None, None, False),
 ('01/06/2024 10:30', None, None, None, None, False),
 ('2026-06-05T10:30:00', None, None, '2026-06-05', '2026-06-05', False),
 ('2026-06-05 00:00:00', None, None, '2026-06-05', '2026-06-05', False),
 ('06/26', None, None, None, None, False),
 ('6 6 2026', None, None, None, None, False),
 ('1500-01-01', ('1500-01-01', 'D'), '1500-01-01', '1500-01-01', '1500-01-01', False),
 ('2024-06-15 extra', None, None, '2024-06-15', '2024-06-15', False),
 ('06/13/2024', None, None, None, '2024-06-13', True),
 ('12/25/2024', None, None, None, '2024-12-25', True),
 ('29/02/2024', ('2024-02-29', 'D'), '2024-02-29', '2024-02-29', '2024-02-29', False),
 ('29/02/2023', None, None, None, None, True),
 ('1/6/2024x', None, None, None, None, False),
 ('  5/6/2026  ', ('2026-06-05', 'D'), '2026-06-05', '2026-06-05', '2026-05-06', False),
 ('5 / 6 / 2026', None, None, None, None, False)]

NEW_WHERE_DIFFERENT = {'01/06/2024 10:30': (('2024-06-01', 'D'), '2024-06-01', '2024-06-01', '2024-06-01', False),
 '05.06.2026': (('2026-06-05', 'D'), '2026-06-05', '2026-06-05', '2026-06-05', False),
 '15 Jun 2024': (('2024-06-15', 'D'), '2024-06-15', '2024-06-15', '2024-06-15', False),
 '15th June 2024': (('2024-06-15', 'D'), '2024-06-15', '2024-06-15', '2024-06-15', False),
 '2024/06/01': (('2024-06-01', 'D'), '2024-06-01', '2024-06-01', '2024-06-01', False),
 '2026-06-05 00:00:00': (('2026-06-05', 'D'), '2026-06-05', '2026-06-05', '2026-06-05', False),
 '2026-06-05T10:30:00': (('2026-06-05', 'D'), '2026-06-05', '2026-06-05', '2026-06-05', False),
 '5 / 6 / 2026': (('2026-06-05', 'D'), '2026-06-05', '2026-06-05', '2026-06-05', False),
 '6 6 2026': (('2026-06-06', 'D'), '2026-06-06', '2026-06-06', '2026-06-06', False),
 '6 June 2021': (('2021-06-06', 'D'), '2021-06-06', '2021-06-06', '2021-06-06', False),
 '6.vi.2021': (('2021-06-06', 'D'), '2021-06-06', '2021-06-06', '2021-06-06', False),
 'vi.2021': (('2021-06', 'O'), None, None, None, False)}


def _clear(*stores):
    for s in stores:
        s.clear()
        s.sync()


@pytest.fixture
def stores():
    old, new = ss.named("Flauna", "Observatum"), ss.named(ss.ORG, ss.APP)
    _clear(old, new)
    yield old, new
    _clear(old, new)


# ---------------------------------------------------------------- 1. settings store
def test_org_and_app_constants():
    assert (ss.ORG, ss.APP) == ("Observatum", "Observatum V2")
    s = ss.app_settings()
    assert (s.organizationName(), s.applicationName()) == ("Observatum", "Observatum V2")


def test_merge_copies_only_missing_keys_and_never_overwrites(stores):
    old, new = stores
    old.setValue("general/default_recorder", "Flauna Wil")
    old.setValue("DataEntry/gridHeaderState", "abc")
    old.setValue("photo/folder", "C:/pics")
    new.setValue("general/default_recorder", "Observatum Wil")
    new.sync()
    copied = ss.merge_flauna_store_once()
    assert sorted(copied) == ["DataEntry/gridHeaderState", "photo/folder"]
    cur = ss.app_settings()
    assert cur.value("general/default_recorder") == "Observatum Wil"      # Observatum's wins
    assert cur.value("DataEntry/gridHeaderState") == "abc"
    assert cur.value("photo/folder") == "C:/pics"
    assert cur.value(ss.MERGED_KEY) == dt.date.today().isoformat()


def test_merge_is_idempotent_and_keeps_the_old_store(stores):
    old, new = stores
    old.setValue("a/b", "1")
    old.sync()
    assert ss.merge_flauna_store_once() == ["a/b"]
    old.setValue("later/key", "2")                  # added after the merge: not copied again
    old.sync()
    assert ss.merge_flauna_store_once() == []
    assert not ss.app_settings().contains("later/key")
    assert sorted(ss.named("Flauna", "Observatum").allKeys()) == ["a/b", "later/key"]   # untouched


def test_merge_with_an_empty_old_store_still_marks_it(stores):
    assert ss.merge_flauna_store_once() == []
    assert ss.app_settings().contains(ss.MERGED_KEY)


def test_standalone_and_embedded_read_the_same_default_recorder(stores, monkeypatch):
    from DataEntry.photo_intake_dialog import PhotoIntakeDialog
    from DataEntry.entry_grid import EntryGridPage
    from shared import species_counting
    s = ss.app_settings()
    s.setValue("general/default_recorder", "W. Heeney")
    s.setValue("general/default_determiner", "W. J. Heeney")
    s.sync()
    got = []
    for org, app in ((ss.ORG, ss.APP), ("Flauna", "Observatum")):   # inside Observatum / the old standalone name
        monkeypatch.setattr(QCoreApplication, "organizationName", staticmethod(lambda o=org: o))
        monkeypatch.setattr(QCoreApplication, "applicationName", staticmethod(lambda a=app: a))
        got.append((PhotoIntakeDialog._defaults(), EntryGridPage._settings(None).value("general/default_recorder"),
                    species_counting._settings().fileName()))
    assert got[0] == got[1]
    assert got[0][0] == {"recorder": "W. Heeney", "determiner": "W. J. Heeney"}
    assert got[0][1] == "W. Heeney"


def test_dataentry_main_registers_the_shared_names():
    import inspect
    from DataEntry import __main__ as m
    src = inspect.getsource(m)
    assert "setOrganizationName(ORG)" in src and "setApplicationName(APP)" in src
    assert "merge_flauna_store_once()" in src and '"Flauna"' not in src


def test_photo_attach_uses_the_shared_store(stores):
    from DataEntry import photo_attach
    assert photo_attach._settings().fileName() == ss.app_settings().fileName()


# ---------------------------------------------------------------- 3. one sex list
def test_the_sex_lists_are_one_object():
    from DataEntry import session_header
    from shared import bench_photos
    from src.utils import constants
    from src.views.home import quick_entry_fields_mixin as qe
    from src.views.dialogs import add_specimen_dialog as asd
    from src.views.dialogs.observation_import_wizard import validation_worker as vw
    assert vocab.SEX_OPTIONS == ["Female", "Male", "Mixed", "Not recorded"]
    assert constants.SEX_OPTIONS is vocab.SEX_OPTIONS
    assert session_header.FALLBACK_SEXES is vocab.SEX_OPTIONS
    assert session_header.load_sexes()[0] == vocab.SEX_OPTIONS
    assert qe.SEX_OPTIONS is vocab.SEX_CHOICES and vocab.SEX_CHOICES == [""] + vocab.SEX_OPTIONS
    assert asd.SEX_CHOICES is vocab.SEX_CHOICES
    assert vw.VALID_SEX_VALUES == [s.casefold() for s in vocab.SEX_CHOICES]
    # the photo-name words keep matching exactly what they matched before
    assert bench_photos.SEX_WORDS == {"male", "female", "males", "females", "mixed", "worker",
                                      "queen", "hermaphrodite"}


def test_add_specimen_offers_the_shared_list_but_keeps_a_stored_unknown():
    import inspect
    from src.views.dialogs.add_specimen_dialog import AddSpecimenDialog
    assert "Unknown" not in vocab.SEX_CHOICES
    src = inspect.getsource(AddSpecimenDialog)
    assert "self.sex_combo.addItems(SEX_CHOICES)" in src
    assert "self.sex_combo.addItem(sex)" in src       # an older row's 'Unknown' is added when it is shown


# ---------------------------------------------------------------- 4. one date reader
@pytest.fixture
def date_funcs(monkeypatch):
    from DataEntry import date_utils as de
    from src.utils import date_utils as ou
    return de, ou


@pytest.mark.parametrize("row", OLD, ids=[r[0] or "blank" for r in OLD])
def test_date_readers_give_the_same_answers_as_before(row, date_funcs, monkeypatch):
    de, ou = date_funcs
    s, old_parse, old_iso, old_dmy, old_mdy, old_unread = row
    new = NEW_WHERE_DIFFERENT.get(s)
    if new:
        old = (old_parse, old_iso, old_dmy, old_mdy, old_unread)
        for o, n in zip(old, new):                 # an intended change was unreadable before
            assert n == o or o is None or o is True
        want = new
    else:
        want = (old_parse, old_iso, old_dmy, old_mdy, old_unread)
    monkeypatch.setattr(ou, "get_user_date_format", lambda: "%d/%m/%Y")
    got_dmy = ou.parse_display_date(s)
    got_unread = ou.unreadable_full_date(s)
    monkeypatch.setattr(ou, "get_user_date_format", lambda: "%m/%d/%Y")
    got_mdy = ou.parse_display_date(s)
    assert (de.parse(s), de.to_iso(s), got_dmy, got_mdy, got_unread) == want


def test_date_table_is_big_enough_and_changes_only_unreadable_inputs():
    assert len(OLD) >= 30 and 0 < len(NEW_WHERE_DIFFERENT) < len(OLD)


def test_today_and_yesterday_still_read(date_funcs):
    de, _ = date_funcs
    today = dt.date.today()
    assert de.parse("Today") == (today.isoformat(), "D")
    assert de.parse("yesterday") == ((today - dt.timedelta(days=1)).isoformat(), "D")
    assert de.is_future("2999-01-01") and de.parse("1/1/99") == ("2099-01-01", "D")


def test_ranges_are_still_not_one_date_for_data_entry(date_funcs):
    de, _ = date_funcs
    assert de.parse("2019-2021") is None and de.parse("1/5/2024 to 15/5/2024") is None


# ---------------------------------------------------------------- 5. one VC database path
def test_vc_path_functions_return_paths_vc_lookup_db(tmp_path, monkeypatch):
    from src.services.vc_lookup_service import VCLookupService
    from src.views.dialogs.observation_import_wizard import validation_worker as ow
    from src.views.dialogs.specimen_import_wizard import validation_worker as sw
    real = tmp_path / "real" / "vc_lookup.db"
    real.parent.mkdir()
    real.write_bytes(b"")
    decoy = tmp_path / "cwd" / "data" / "vc_lookup.db"          # a place the old search used
    decoy.parent.mkdir(parents=True)
    decoy.write_bytes(b"")
    monkeypatch.chdir(tmp_path / "cwd")
    monkeypatch.setattr(paths, "VC_LOOKUP_DB", real)
    svc = VCLookupService.__new__(VCLookupService)
    svc._db_path = None
    assert svc._get_db_path() == real
    assert ow._find_vc_database() == str(real) and sw._find_vc_database() == str(real)
    monkeypatch.setattr(paths, "VC_LOOKUP_DB", tmp_path / "missing.db")          # absent: None, no search
    assert svc._get_db_path() is None
    assert ow._find_vc_database() is None and sw._find_vc_database() is None


def test_review_date_shapes():
    """Review 24 Oct: ISO with a one-digit month, 'June, 2021', December 9999."""
    from DataEntry.date_utils import parse
    from src.utils.date_utils import parse_display_date
    assert parse_display_date("2024-6-15") == "2024-06-15"
    assert parse("June, 2021") == ("2021-06", "O")
    assert parse("1/1/99") == ("2099-01-01", "D")        # two-digit years stay 2000s
    assert parse("12/9999") is None and parse_display_date("12/9999") is None
