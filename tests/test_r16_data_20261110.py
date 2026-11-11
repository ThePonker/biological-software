"""Round 16 data fixes (10 Nov 2026): a Data Entry row named by a UKSI synonym is committed
under the recommended name with the recommended taxon's taxonomy; a name typed over a
species never keeps the old species' TVK; the commit check lists a name that is not its TVK's.
Small purpose-made UKSI-like and Observatum-like databases only."""
import os
import sqlite3
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from DataEntry import commit_service as cs  # noqa: E402
from DataEntry import staging_repo as repo  # noqa: E402
from shared import taxon_groups as tg  # noqa: E402

REC, SYN, OTHER = "NHMSYS_REC", "NHMSYS_SYN", "NHMSYS_OTHER"
VERN, H1, H2, SYN2, LOST = "NHMSYS_VERN", "NHMSYS_H1", "NHMSYS_H2", "NHMSYS_SYN2", "NHMSYS_LOST"


@pytest.fixture
def uksi(tmp_path):
    path = str(tmp_path / "uksi.db")
    u = sqlite3.connect(path)
    u.execute('CREATE TABLE taxa (tvk TEXT, scientific_name TEXT, rank TEXT, parent_tvk TEXT, '
              'kingdom TEXT, phylum TEXT, class TEXT, "order" TEXT, family TEXT, sort_code INTEGER, '
              'superfamily TEXT)')
    u.executemany("INSERT INTO taxa VALUES (?,?,?,?,?,?,?,?,?,?,?)", [
        (REC, "Botanophila striolata", "Species", None, "Animalia", "Arthropoda", "Insecta", "Diptera",
         "Anthomyiidae", 700, "Muscoidea"),
        (OTHER, "Carabus nemoralis", "Species", None, "Animalia", "Arthropoda", "Insecta", "Coleoptera",
         "Carabidae", 18000, "Caraboidea"),
    ])
    u.execute("CREATE TABLE name_map (tvk TEXT PRIMARY KEY, recommended_tvk TEXT, name TEXT, "
              "recommended_name TEXT, name_status TEXT, deprecated TEXT, source TEXT)")
    u.executemany("INSERT INTO name_map VALUES (?,?,?,?,?,?,?)", [
        (SYN, REC, "Botanophila discreta", "Botanophila striolata", "S", "", ""),
        (REC, REC, "Botanophila striolata", "Botanophila striolata", "R", "", ""),   # the real 'R' row
        (VERN, REC, "A vernacular name", "Botanophila striolata", "S", "", ""),
        (H1, REC, "Amara obsoleta", "Botanophila striolata", "S", "", ""),         # a homonym:
        (H2, OTHER, "Amara obsoleta", "Carabus nemoralis", "S", "", ""),           # two targets
        (SYN2, OTHER, "Carabus tie", "Carabus nemoralis", "S", "", ""),
        (LOST, "NHMSYS_GONE", "Old gone", "Gone gone", "S", "", ""),               # target not in taxa
    ])
    u.execute("CREATE TABLE synonyms (synonym TEXT, tvk TEXT)")
    u.execute("INSERT INTO synonyms VALUES ('Botanophila discreta', ?)", (REC,))
    u.execute("CREATE TABLE common_names (tvk TEXT, common_name TEXT, preferred INTEGER)")
    u.execute("INSERT INTO common_names VALUES (?, 'A Root Fly', 1)", (REC,))
    # two names that tie on every sort term: the first one stored must win, always
    u.executemany("INSERT INTO common_names VALUES (?, ?, 1)", [(OTHER, "Zeta Beetle"), (OTHER, "Alfa Beetle")])
    u.commit()
    u.close()
    return path


def _stage(tmp_path, rows):
    conn = sqlite3.connect(tmp_path / "o.db")
    conn.row_factory = sqlite3.Row
    repo.ensure_schema(conn)
    jid = repo.create_job(conn, "Personal", "Personal", None, None)
    for r in rows:
        base = {"date": "05/06/2026", "quantity": "1", "recorder": "Heeney, W.J.",
                "site_name": "Site", "grid_ref": "SP0000"}
        repo.insert_row(conn, jid, {**base, **r})
    return conn, jid


def _commit(conn, jid, uksi):
    made, updates = [], []

    class Model:
        def create(self, o, extra=None):
            made.append(o)
            e = extra or {}      # R18 B5: the survey / taxonomy columns arrive with create()
            updates.append((e.get("sub_location"), e.get("trap_number"), e.get("visit_number"),
                            e.get("import_notes"), e.get("superfamily"), e.get("taxonomic_sort_key"),
                            100 + len(made)))
            return 100 + len(made)

    class Db:
        def execute_main_write(self, sql, params):
            raise AssertionError("commit_job no longer writes a second UPDATE (R18 B5)")

    s = cs.commit_job(Db(), Model(), conn, repo.get_job(conn, jid),
                      observation_cls=lambda **kw: SimpleNamespace(**kw), uksi_path=uksi)
    return s, made, updates


# ---------------------------------------------------------------- UKSI helpers
def test_recommended_for_tvks_only_for_synonyms(uksi):
    got = tg.recommended_for_tvks([SYN, REC, OTHER, "NOPE", "", LOST, H1, SYN2], uksi)
    assert set(got) == {SYN, H1, SYN2}                  # not the 'R' row, a taxon, an unknown, or LOST
    assert got[SYN] == {"tvk": REC, "scientific_name": "Botanophila striolata",
                        "common_name": "A Root Fly", "name": "Botanophila discreta", "targets": 1}
    assert got[H1]["targets"] == 2 and got[SYN2]["targets"] == 1


def test_common_name_pick_is_deterministic(uksi):
    for _ in range(3):
        # tied on preferred / capital start / length / capitals: alphabetical (R17 B5; was row order)
        assert tg.recommended_for_tvks([SYN2], uksi)[SYN2]["common_name"] == "Alfa Beetle"


def test_names_for_tvks(uksi):
    got = tg.names_for_tvks([SYN, REC, "NOPE"], uksi)
    assert got[SYN] == got[REC] == {"botanophila striolata", "botanophila discreta"}
    assert "NOPE" not in got


# ---------------------------------------------------------------- commit
def test_synonym_row_committed_under_the_recommended_name(tmp_path, uksi):
    conn, jid = _stage(tmp_path, [
        {"species_name": "Botanophila discreta", "species_tvk": SYN},          # synonym
        {"species_name": "Botanophila striolata", "species_tvk": REC,           # recommended
         "order_name": "Diptera", "family": "Anthomyiidae"},
        {"species_name": "Unknownia nonesuch", "species_tvk": "NOPE", "order_name": "Coleoptera"},
    ])
    s, made, updates = _commit(conn, jid, uksi)
    assert s["committed"] == 3 and s["error"] is None
    syn, rec, unk = made
    # synonym: stored under the recommended name and TVK; taxonomy from the recommended taxon
    assert (syn.species_name, syn.species_tvk) == ("Botanophila striolata", REC)
    assert (syn.kingdom, syn.order_name, syn.family, syn.taxon_rank) == (
        "Animalia", "Diptera", "Anthomyiidae", "Species")
    assert syn.taxon_group == "insect - true fly (Diptera)"
    assert syn.common_name == "A Root Fly"
    assert syn.identification_remarks == \
        "Entered as 'Botanophila discreta' (UKSI synonym of 'Botanophila striolata')"
    assert s["synonyms"] == ["Botanophila discreta -> Botanophila striolata"]
    # the supplementary UPDATE: sub_location, trap, visit, import_notes, superfamily, sort key, id
    assert updates[0][4] == "Muscoidea" and updates[0][5] == updates[1][5] and updates[0][5]
    assert updates[0][3] == s["batch"]                      # import_notes stays the batch stamp
    # a recommended name is untouched, with no remark
    assert (rec.species_name, rec.species_tvk, rec.identification_remarks) == (
        "Botanophila striolata", REC, None)
    # an unknown name is committed as staged, as before, with no taxonomy invented
    assert (unk.species_name, unk.species_tvk, unk.kingdom) == ("Unknownia nonesuch", "NOPE", None)
    assert unk.order_name == "Coleoptera" and unk.identification_remarks is None
    assert updates[2][4] is None and updates[2][5] is None


def test_build_kwargs_without_a_recommended_entry_is_unchanged():
    row = {"species_name": " Amara aenea ", "species_tvk": "T1", "common_name": "c", "order_name": "O",
           "family": "F", "date": "05/06/2026", "quantity": "1"}
    kw = cs.build_kwargs_from_row(row, {"mode": "Personal"}, None, {"kingdom": "Animalia"})
    assert (kw["species_name"], kw["species_tvk"], kw["common_name"], kw["order_name"],
            kw["family"]) == ("Amara aenea", "T1", "c", "O", "F")
    assert kw["identification_remarks"] is None


# ---------------------------------------------------------------- commit check
def test_precommit_lists_a_name_that_is_not_its_tvks(uksi):
    base = {"date": "05/06/2026", "quantity": "1", "recorder": "r", "site_name": "s", "grid_ref": "SP0000",
            "vc_number": "23"}
    rows = [{**r, "date": f"0{i}/06/2026"} for i, r in enumerate([
        {**base, "species_name": "Botanophila striolata", "species_tvk": REC},
        {**base, "species_name": "Botanophila discreta", "species_tvk": SYN},      # synonym: fine
        {**base, "species_name": "Botanophila discreta", "species_tvk": REC},      # synonym of it: fine
        {**base, "species_name": "Carabus nemoralis", "species_tvk": REC},         # changed, TVK stale
        {**base, "species_name": "Carabus nemoralis", "species_tvk": "NOPE"},      # TVK not in UKSI
        {**base, "species_name": "Botanophila striolata agg.", "species_tvk": REC},
    ], start=1)]
    names = cs.uksi_names_for_rows(rows, uksi)
    assert cs.precommit_issues(rows, names) == {"name and TVK differ": [4]}
    assert "name and TVK differ" not in cs.precommit_issues(rows)       # no names given: no check


# ---------------------------------------------------------------- the grid's model
def test_plain_text_in_the_species_cell_never_keeps_the_old_species(tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from DataEntry.grid_columns import COLIDX
    from DataEntry.staging_model import StagingTableModel
    QApplication.instance() or QApplication([])
    conn, jid = _stage(tmp_path, [{"species_name": "Carabus nemoralis", "species_tvk": OTHER,
                                   "common_name": "Violet Ground Beetle", "order_name": "Coleoptera",
                                   "family": "Carabidae", "taxon_rank": "Species"}])
    m = StagingTableModel(conn, jid)
    ix = m.index(0, COLIDX["species_name"])
    assert m.setData(ix, "Carabus nemoralis", Qt.ItemDataRole.EditRole)      # same name: no change
    assert m.row_dict(0)["species_tvk"] == OTHER
    assert m.setData(ix, "  carabus   NEMORALIS ", Qt.ItemDataRole.EditRole)  # same name, other spacing/case
    assert m.row_dict(0)["species_tvk"] == OTHER
    assert m.setData(ix, "Amara aenea", Qt.ItemDataRole.EditRole)            # a different name
    for source in (m.row_dict(0), dict(repo.fetch_rows(conn, jid)[0])):     # in memory and stored
        assert source["species_name"] == "Amara aenea"
        assert all(source[k] is None for k in
                   ("species_tvk", "common_name", "order_name", "family", "taxon_rank"))


# ---------------------------------------------------------------- B1, S1, S2, S3 and the rest
def _kinds(made):
    return [(o.species_name, o.species_tvk, o.kingdom, o.identification_remarks) for o in made]


def test_a_name_that_is_not_its_tvks_is_written_as_staged(tmp_path, uksi):
    conn, jid = _stage(tmp_path, [
        {"species_name": "Carabus nemoralis", "species_tvk": SYN, "order_name": "Coleoptera"},   # B1
        {"species_name": "Rutpela maculata", "species_tvk": VERN},                                 # vernacular TVK
    ])
    s, made, updates = _commit(conn, jid, uksi)
    assert _kinds(made) == [("Carabus nemoralis", SYN, None, None), ("Rutpela maculata", VERN, None, None)]
    assert made[0].order_name == "Coleoptera" and made[0].family is None
    assert s["name_tvk_differ"] == ["Carabus nemoralis", "Rutpela maculata"] and s["synonyms"] == []
    assert all(u[4] is None and u[5] is None for u in updates)     # no other taxon's superfamily or key


def test_a_homonym_is_written_as_staged(tmp_path, uksi):
    conn, jid = _stage(tmp_path, [{"species_name": "Amara obsoleta", "species_tvk": H1}])
    s, made, _ = _commit(conn, jid, uksi)
    assert _kinds(made) == [("Amara obsoleta", H1, None, None)]
    assert s["ambiguous_names"] == ["Amara obsoleta"] and s["synonyms"] == []


def test_a_recommended_taxon_missing_from_taxa_leaves_the_row_alone(tmp_path, uksi):
    conn, jid = _stage(tmp_path, [{"species_name": "Old gone", "species_tvk": LOST}])
    s, made, _ = _commit(conn, jid, uksi)
    assert _kinds(made) == [("Old gone", LOST, None, None)]
    assert s["synonyms"] == [] and s["name_tvk_differ"] == []


def test_qualifiers_in_recommended_mode(tmp_path, uksi):
    conn, jid = _stage(tmp_path, [
        {"species_name": "Botanophila cf. discreta", "species_tvk": SYN, "sex": "Male"},   # cf. carried
        {"species_name": "Botanophila discreta agg.", "species_tvk": SYN, "sex": "Female"},  # not carried
    ])
    s, made, _ = _commit(conn, jid, uksi)
    assert (made[0].species_name, made[0].species_tvk) == ("Botanophila cf. striolata", REC)
    assert "Entered as 'Botanophila cf. discreta'" in made[0].identification_remarks
    assert (made[1].species_name, made[1].species_tvk, made[1].kingdom) == (
        "Botanophila discreta agg.", SYN, None)
    assert s["qualified_names"] == ["Botanophila discreta agg."]


def test_as_recorded_rule_keeps_the_name_and_moves_the_tvk(tmp_path, uksi, monkeypatch):
    monkeypatch.setattr(cs, "SYNONYM_NAME_RULE", "as_recorded")
    conn, jid = _stage(tmp_path, [{"species_name": "Botanophila discreta", "species_tvk": SYN}])
    s, made, updates = _commit(conn, jid, uksi)
    o = made[0]
    assert (o.species_name, o.species_tvk) == ("Botanophila discreta", REC)
    assert (o.kingdom, o.order_name, o.family, o.common_name) == (
        "Animalia", "Diptera", "Anthomyiidae", "A Root Fly")
    assert "Botanophila discreta" in o.identification_remarks and "Botanophila striolata" in o.identification_remarks
    assert updates[0][4] == "Muscoidea" and updates[0][5]
    assert s["synonyms"] == [f"Botanophila discreta -> Botanophila discreta ({REC})"]


def test_a_renamed_row_files_its_photos_under_the_recommended_species(tmp_path, uksi, monkeypatch):
    from shared import bench_photos
    seen = []
    monkeypatch.setattr(bench_photos, "file_on_commit",
                        lambda conn, sid, row, oid: seen.append(dict(row)) or (True, []))
    conn, jid = _stage(tmp_path, [{"species_name": "Botanophila discreta", "species_tvk": SYN,
                                   "family": "Wrongidae"}])
    _commit(conn, jid, uksi)
    assert (seen[0]["species_name"], seen[0]["species_tvk"], seen[0]["family"], seen[0]["order_name"]) == (
        "Botanophila striolata", REC, "Anthomyiidae", "Diptera")


def test_tvk_with_stray_spaces_is_still_found(tmp_path, uksi):
    conn, jid = _stage(tmp_path, [{"species_name": "Botanophila discreta", "species_tvk": f" {SYN} "}])
    s, made, _ = _commit(conn, jid, uksi)
    assert made[0].species_tvk == REC
    names = cs.uksi_names_for_rows([{"species_tvk": f" {SYN}"}], uksi)
    assert SYN in names


def test_the_workbook_loader_lists_name_tvk_mismatches(uksi):
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "scripts", "load_workbook_to_staging.py")
    spec = importlib.util.spec_from_file_location("load_workbook_to_staging", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    recs = [{"row_order": 1, "species_name": "Botanophila discreta", "species_tvk": SYN},
            {"row_order": 2, "species_name": "Carabus nemoralis", "species_tvk": REC},
            {"row_order": 3, "species_name": "Anything", "species_tvk": "NOPE"},
            {"row_order": 4}]
    assert m.find_mismatches(recs, uksi) == [(2, "Carabus nemoralis", REC)]
