"""Round A: preview of an uncommitted Data Entry job (read-only) -- Examen.examen_data."""
import hashlib

import pytest
from _round_a_fixture import (NAMES, RECORDS, T_COMMON, T_PLANT, add_committed, add_job,
                              add_staged, build)

from Examen import examen_data as ed


@pytest.fixture()
def world(tmp_path, monkeypatch):
    return build(tmp_path, monkeypatch)


def _digest(folder):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.glob("*.db"))}


def _summary(d):
    s = d.site
    return (s.record_count, s.species_count, s.visit_count, s.first_date, s.last_date,
            s.survey_year, s.key_species_count, s.key_species_pct, s.rare_count, s.scarce_count,
            s.priority_count, s.sqi, s.sqi_reliable, s.species_with_sqs, s.visit_dates,
            s.accumulation)


def _species(d):
    return [(x.name, x.tvk, x.count, x.sqs, x.status, x.tier) for x in d.species_list]


def test_partly_committed_job_previews_as_the_fully_committed_survey(world):
    """Some rows already in observations, the rest staged: the preview is the whole survey."""
    add_committed(world, project="Whole", client="Acme")                 # all six, committed
    add_committed(world, records=RECORDS[:3])                             # three of them committed
    jid = add_job(world, records=RECORDS[3:])                             # the rest still staged
    committed = ed.load_project_detail("Whole", "Acme", survey_year="2026")
    preview = ed.load_entry_job_detail(jid)
    assert committed.analysis is not None and committed.site.key_species_count == 3
    assert _summary(preview) == _summary(committed)
    assert _species(preview) == _species(committed)
    assert preview.jurisdiction == committed.jurisdiction == "Scotland"   # VC 74, from the rows
    assert preview.recorded_tvks == committed.recorded_tvks
    assert preview.site.project_name == "Notts Park" and preview.site.client == "Acme"
    assert preview.site.preview_job == "Notts" and committed.site.preview_job == ""
    assert len(preview.preview_rows) == 6


def test_preview_takes_the_same_project_client_and_year_only(world):
    add_committed(world, records=RECORDS[:2])
    add_committed(world, client="Other", records=RECORDS[2:4])           # another client
    add_committed(world, project="Elsewhere", records=RECORDS[4:5])      # another project
    add_committed(world, records=[("Old", T_COMMON, "2025-05-01", "North", 74)])  # another year
    d = ed.load_entry_job_detail(add_job(world, records=RECORDS[5:]))
    assert d.site.record_count == 3 and d.site.species_count == 1   # the plant is not counted


def test_preview_includes_contributed_records(world):
    import sqlite3
    add_committed(world, records=RECORDS[:2])
    c = sqlite3.connect(str(world / "observatum.db"))
    c.execute("INSERT INTO assessment_records (origin, contributor, record_type, project_name, "
              "client, site_name, date, species_name, species_tvk, quantity, vc_number) VALUES "
              "('contributed', 'Moore, J.', 'Commercial', 'Notts Park', 'Acme', 'North', "
              "'2026-07-01', ?, ?, 1, 74)", (NAMES[T_COMMON], T_COMMON))
    c.commit()
    c.close()
    d = ed.load_entry_job_detail(add_job(world, records=RECORDS[2:3]))
    assert d.site.record_count == 4
    assert any(r[11] == "Moore, J." for r in d.preview_rows)


def test_preview_counts_only_the_rows_commit_would_write(world):
    jid = add_job(world, records=RECORDS)
    add_staged(world, jid, species_name="Checkus", date="2026-07-01", quantity=1, vc_number=74,
               check_flag=1)
    add_staged(world, jid, species_name="Undatus", date="", quantity=1, vc_number=74)
    add_staged(world, jid, species_name="Badate", date="summer", quantity=1, vc_number=74)
    add_staged(world, jid, species_name="Zeroes", date="2026-07-01", quantity=0, vc_number=74)
    add_staged(world, jid, species_name="Badvc", date="2026-07-01", quantity=1, vc_number=0)
    add_staged(world, jid, species_name="", date="", quantity=None, vc_number=None)  # empty grid row
    add_staged(world, jid, species_name=None, date=None, quantity=None, vc_number=None)
    d = ed.load_entry_job_detail(jid)
    assert d.site.record_count == 6 and d.site.preview_held_back == 5
    assert d.site.last_date == "2026-06-11"
    assert not {"Checkus", "Undatus", "Badate", "Zeroes", "Badvc"} & {x.name for x in d.species_list}
    j = ed.list_entry_jobs()[0]
    assert (j["rows"], j["species"], j["held_back"]) == (6, 5, 5)
    assert "5 rows held back (To check, undated or unreadable) are not included." in \
        ed.preview_note("Notts", 5)
    assert "held back" not in ed.preview_note("Notts", 0)


def test_preview_rows_are_written_as_commit_writes_them(world, monkeypatch):
    """A UKSI synonym is under its recommended name and TVK; a month-year is its first day."""
    from DataEntry import commit_service as cs
    syn = {"T_OLD": {"recommended": {"tvk": T_COMMON, "name": "Antiquus beetle",
                                     "scientific_name": NAMES[T_COMMON], "common_name": "",
                                     "targets": 1}}}
    monkeypatch.setattr(cs, "taxonomy_with_synonyms", lambda rows, uksi_path=None: syn)
    jid = add_job(world, records=[("Antiquus beetle", "T_OLD", "2026-05", "North", 74)])
    d = ed.load_entry_job_detail(jid)
    row = d.preview_rows[0]
    assert (row[0], row[1], row[2]) == (NAMES[T_COMMON], T_COMMON, "2026-05-01")
    # and the preview carries on without taxonomy when it cannot be read, as commit does
    def boom(rows, uksi_path=None):
        raise RuntimeError("no UKSI")
    monkeypatch.setattr(cs, "taxonomy_with_synonyms", boom)
    assert ed.load_entry_job_detail(jid).preview_rows[0][0] == "Antiquus beetle"


def test_project_and_client_keys_are_as_typed(world):
    from DataEntry.visit_weather_dialog import job_project_client
    jid = add_job(world, name="D", project="Derby ", client="Acme ")
    d = ed.load_entry_job_detail(jid)
    assert d.site.project_name == "Derby " and d.site.client == "Acme "
    assert job_project_client({"project": "Derby ", "client": "Acme ", "name": "D"}) == (
        "Derby ", "Acme ")
    assert job_project_client({"project": None, "client": None, "name": "D"}) == ("D", "")
    # a committed project carries the same keys, so weather and marks saved from the preview match
    add_committed(world, project="Derby ", client="Acme ")
    c = ed.load_project_detail("Derby ", "Acme ", survey_year="2026")
    assert (c.site.project_name, c.site.client) == (d.site.project_name, d.site.client)
    assert ed.load_entry_job_detail(jid).site.record_count == 12      # picks the committed rows up


def test_preview_writes_nothing(world):
    add_committed(world)
    jid = add_job(world)
    before = _digest(world)
    ed.list_entry_jobs()
    ed.load_entry_job_detail(jid)
    assert _digest(world) == before


def test_list_entry_jobs_only_active_jobs_with_species(world):
    a = add_job(world, name="Active", records=RECORDS)
    add_job(world, name="Done", status="committed")
    add_job(world, name="Empty", records=[("", "", "2026-05-01", "x", 74), (None, None, None, "x", 74)])
    jobs = ed.list_entry_jobs()
    assert [j["name"] for j in jobs] == ["Active"]
    j = jobs[0]
    assert (j["id"], j["project"], j["client"], j["rows"], j["species"]) == (a, "Notts Park", "Acme", 6, 5)
    assert (j["first_date"], j["last_date"]) == ("2026-05-10", "2026-06-11")


def test_rows_without_a_species_name_are_ignored(world):
    jid = add_job(world, extra_rows=[("  ", T_COMMON, "2026-07-01", "North", 74),
                                     ("", "", "2026-08-01", "North", 74)])
    d = ed.load_entry_job_detail(jid)
    assert d.site.record_count == 6 and d.site.last_date == "2026-06-11"


def test_job_name_stands_in_for_a_missing_project(world):
    jid = add_job(world, name="Hook", project=None, client=None)
    d = ed.load_entry_job_detail(jid)
    assert d.site.project_name == "Hook" and d.site.client == ""


def test_non_invertebrates_are_left_out_of_the_species_count(world):
    """A plant entered by mistake is not a species of the assessment: not listed, not counted,
    never Key -- and the analysis names it so the workbook can say so."""
    add_committed(world)
    jid = add_job(world)
    for d in (ed.load_project_detail("Notts Park", "Acme", survey_year="2026"),
              ed.load_entry_job_detail(jid)):
        assert T_PLANT not in {x.tvk for x in d.species_list}
        assert d.site.species_count == 4 and d.analysis.total_species == 4
        assert d.analysis.non_invertebrates == {T_PLANT: NAMES[T_PLANT]}
        assert T_PLANT not in {k.tvk for k in d.analysis.key_species}


def test_jurisdiction_follows_the_vice_counties_or_the_choice(world):
    rows = [(n, t, d, s, 59) for n, t, d, s, _ in RECORDS]
    jid = add_job(world, records=rows)
    assert ed.load_entry_job_detail(jid).jurisdiction == "England"
    assert ed.load_entry_job_detail(jid, jurisdiction="Wales").jurisdiction == "Wales"
    no_vc = add_job(world, name="NoVC", records=[(n, t, d, s, None) for n, t, d, s, _ in RECORDS])
    assert ed.load_entry_job_detail(no_vc).jurisdiction == "England"


def test_dates_over_two_years_take_the_most_common_year_and_say_so(world):
    rows = RECORDS[:2] + [("Later", T_COMMON, "2027-05-01", "North", 74)]
    d = ed.load_entry_job_detail(add_job(world, records=rows))
    assert d.site.survey_year == "2026" and d.site.record_count == 2
    assert "most common of 2026, 2027" in d.site.preview_years
    assert "most common" in ed.preview_note("Notts", 0, d.site.preview_years)
    one = ed.load_entry_job_detail(add_job(world, name="B"))
    assert one.site.survey_year == "2026" and one.site.preview_years == ""


def test_missing_job_gives_none(world):
    assert ed.load_entry_job_detail(999) is None


def test_load_project_detail_is_unchanged_by_the_refactor(world):
    add_committed(world)
    d = ed.load_project_detail("Notts Park", "Acme", survey_year="2026")
    s = d.site
    assert (s.record_count, s.species_count, s.visit_count, s.key_species_count,
            s.rare_count, s.scarce_count) == (6, 4, 2, 3, 2, 1)
    assert s.accumulation == [("2026-05-10", 2), ("2026-06-11", 4)]
    assert s.accumulation[-1][1] == s.species_count            # the curve ends at the species count
    assert ed.load_entry_job_detail(add_job(world)).site.accumulation[-1][1] == 4


def test_view_shows_the_preview_like_a_project(world, monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QMessageBox
    QApplication.instance() or QApplication([])
    from Examen import entry_job_picker, site_analysis_view as sav
    jid = add_job(world)
    monkeypatch.setattr(entry_job_picker.EntryJobPicker, "exec", lambda self: True)
    monkeypatch.setattr(entry_job_picker.EntryJobPicker, "chosen_id", lambda self: jid)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    view = sav.SiteAnalysisView(ed.analysis_service())
    view._on_entry_job()
    assert view.detail_header.text().startswith(
        "Notts Park — Data Entry job 'Notts' (not committed, preview)")
    assert view.workbook_action.isEnabled() and view.pdf_action.isEnabled() and view.word_action.isEnabled()
    assert view._current_detail.site.preview_job == "Notts"
    view._pool_years = True
    assert view._pooled() is False          # pooling never applies to a preview
