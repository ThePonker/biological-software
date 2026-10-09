"""The one species-lookup rule set (shared/species_lookup.py, fix round 9 Oct 2026, items
13 and 16) on a made-up UKSI in memory -- no real database.

test_species_lookup_characterisation.py checks the wizards against the real uksi.db."""
import sqlite3

import pytest

from shared.species_lookup import (
    AMBIGUOUS, NO_AGGREGATE, NOT_FOUND, LookupFailure, NameMatch, is_species_error,
    is_unresolved_error, lookup_names, parse_qualifier, search_candidates)
from shared.species_lookup_entries import apply_confirmed, entry


def _uksi():
    c = sqlite3.connect(":memory:")
    c.executescript("""
        CREATE TABLE taxa (tvk TEXT PRIMARY KEY, scientific_name TEXT, rank TEXT, kingdom TEXT,
            phylum TEXT, class TEXT, "order" TEXT, family TEXT, genus TEXT, sort_code INTEGER);
        CREATE TABLE synonyms (synonym TEXT, tvk TEXT);
        CREATE TABLE common_names (common_name TEXT, tvk TEXT, preferred INTEGER);
        CREATE TABLE taxon_qualifiers (tvk TEXT PRIMARY KEY, authority TEXT, qualifier TEXT,
            shared_name INTEGER, label TEXT);
        INSERT INTO taxa VALUES
          ('CN', 'Carabus nemoralis', 'Species', 'Animalia', 'Arthropoda', 'Insecta', 'Coleoptera', 'Carabidae', 'Carabus', 1),
          ('RM', 'Rutpela maculata', 'Species', 'Animalia', 'Arthropoda', 'Insecta', 'Coleoptera', 'Cerambycidae', 'Rutpela', 2),
          ('APS', 'Andrena proxima', 'Species', 'Animalia', 'Arthropoda', 'Insecta', 'Hymenoptera', 'Andrenidae', 'Andrena', 3),
          ('APL', 'Andrena proxima', 'Species sensu lato', 'Animalia', 'Arthropoda', 'Insecta', 'Hymenoptera', 'Andrenidae', 'Andrena', 4),
          ('BL', 'Bombus lucorum', 'Species', 'Animalia', 'Arthropoda', 'Insecta', 'Hymenoptera', 'Apidae', 'Bombus', 5),
          ('BLSL', 'Bombus lucorum', 'Species sensu lato', 'Animalia', 'Arthropoda', 'Insecta', 'Hymenoptera', 'Apidae', 'Bombus', 6),
          ('AGS', 'Agyneta saxatilis', 'Species', 'Animalia', 'Arthropoda', 'Arachnida', 'Araneae', 'Linyphiidae', 'Agyneta', 7),
          ('AGL', 'Agyneta saxatilis', 'Species', 'Animalia', 'Arthropoda', 'Arachnida', 'Araneae', 'Linyphiidae', 'Agyneta', 8),
          ('CS1', 'Cheilosia semifasciata', 'Species', 'Animalia', 'Arthropoda', 'Insecta', 'Diptera', 'Syrphidae', 'Cheilosia', 9),
          ('CS2', 'Cheilosia semifasciata', 'Species', 'Animalia', 'Arthropoda', 'Insecta', 'Diptera', 'Syrphidae', 'Cheilosia', 10),
          ('LOT', 'Lotus', 'Genus', 'Plantae', '', 'Magnoliopsida', 'Fabales', 'Fabaceae', 'Lotus', 11),
          ('PA', 'Populus alba', 'Species', 'Plantae', '', 'Magnoliopsida', 'Malpighiales', 'Salicaceae', 'Populus', 12),
          ('CL', 'Cochlicopa lubrica agg.', 'Species aggregate', 'Animalia', 'Mollusca', 'Gastropoda', 'Stylommatophora', 'Cochlicopidae', 'Cochlicopa', 13);
        INSERT INTO taxon_qualifiers VALUES ('AGS', '', 'sensu stricto', 1, ''), ('AGL', '', 'sensu lato', 1, '');
        INSERT INTO synonyms VALUES ('Strangalia maculata', 'RM'), ('Leptura maculata', 'RM');
        INSERT INTO common_names VALUES ('Spotted Longhorn', 'RM', 1), ('White Poplar', 'PA', 1);
    """)
    return c


@pytest.fixture
def uksi():
    return _uksi()


@pytest.mark.parametrize("text, want", [
    ("Carabus cf. nemoralis", ("cf.", "Carabus nemoralis")),
    ("Carabus cf nemoralis", ("cf.", "Carabus nemoralis")),
    ("Carabus CF. nemoralis", ("cf.", "Carabus nemoralis")),
    ("cf. Carabus nemoralis", ("cf.", "Carabus nemoralis")),
    ("Bombus lucorum agg.", ("agg.", "Bombus lucorum")),
    ("Bombus lucorum AGG", ("agg.", "Bombus lucorum")),
    ("Bombus  lucorum agg. ", ("agg.", "Bombus lucorum")),
    ("Bombus lucorum s.l.", ("s.l.", "Bombus lucorum")),
    ("Bombus lucorum S.L", ("s.l.", "Bombus lucorum")),
    ("Bombus lucorum sensu lato", ("s.l.", "Bombus lucorum")),
    ("Cheilosia albitarsis sens.lat.", ("s.l.", "Cheilosia albitarsis")),
    ("Araniella cucurbitina sensu stricto", ("s.str.", "Araniella cucurbitina")),
    ("Chthonius orthodactylus sens.str.", ("s.str.", "Chthonius orthodactylus")),
    ("Bombus lucorum s.str", ("s.str.", "Bombus lucorum")),
    ("Carabus nemoralis", (None, "Carabus nemoralis")),
])
def test_qualifiers_any_case_with_or_without_the_dot(text, want):
    assert parse_qualifier(text) == want


def test_exact_names_case_and_spaces(uksi):
    r = lookup_names(["carabus  nemoralis", "Carabus nemoralis"], uksi)
    assert r["Carabus nemoralis"].taxon.tvk == "CN"
    e = entry(r["carabus  nemoralis"])
    assert e["species_name"] == "Carabus nemoralis"            # UKSI's name is stored (IMP-15)
    assert e["import_notes"] == "Imported as 'carabus  nemoralis'"
    assert entry(r["Carabus nemoralis"])["import_notes"] == ""


def test_a_search_hit_is_never_a_match(uksi):
    """'Ab' must not become Populus alba: it is an error naming the suggestions."""
    r = lookup_names(["Ab", "alba", "Spotted Longhorn", "Rutpela maculta"], uksi)
    for name in r:
        assert isinstance(r[name], LookupFailure) and r[name].kind == "not_found"
    assert [t.tvk for t in r["Ab"].candidates] == ["CN"]          # 'Carabus' contains 'ab'
    assert [t.tvk for t in r["alba"].candidates] == ["PA"]
    assert r["Spotted Longhorn"].candidates[0].tvk == "RM"        # common name: suggested only
    assert r["Rutpela maculta"].candidates[0].tvk == "RM"         # close spelling: suggested only
    e = entry(r["alba"])
    assert e["error"].startswith(f"{NOT_FOUND}: alba") and "Populus alba" in e["error"]
    assert "tvk" not in e and is_unresolved_error(e["error"]) and is_species_error(e["error"])


def test_synonyms_match_and_say_so(uksi):
    m = lookup_names(["Strangalia maculata"], uksi)["Strangalia maculata"]
    assert isinstance(m, NameMatch) and m.how == "synonym" and m.taxon.tvk == "RM"
    e = entry(m)
    assert e["species_name"] == "Rutpela maculata" and e["warning"].startswith("Synonym")
    assert "Strangalia maculata" in e["import_notes"]


def test_species_over_broad_group(uksi):
    """Wil's rule (IMP-14): a plain binomial held as Species and as s.l. is the Species."""
    for name, tvk in (("Andrena proxima", "APS"), ("Bombus lucorum", "BL"),
                      ("Agyneta saxatilis", "AGS")):              # s.l. by UKSI's qualifier
        m = lookup_names([name], uksi)[name]
        assert m.taxon.tvk == tvk and m.taxon.rank == "Species"
        assert "matched to the species" in entry(m)["import_notes"]


def test_sensu_stricto_is_the_species(uksi):
    m = lookup_names(["Andrena proxima s.str."], uksi)["Andrena proxima s.str."]
    assert m.taxon.tvk == "APS" and not m.warnings


def test_homonyms_need_a_choice(uksi):
    r = lookup_names(["Cheilosia semifasciata"], uksi)["Cheilosia semifasciata"]
    assert r.kind == "ambiguous" and {t.tvk for t in r.candidates} == {"CS1", "CS2"}
    assert entry(r)["error"].startswith(AMBIGUOUS) and is_unresolved_error(entry(r)["error"])


def test_agg_takes_the_aggregate_or_says_there_is_none(uksi):
    r = lookup_names(["Bombus lucorum agg", "Carabus nemoralis AGG.", "Cochlicopa lubrica agg.",
                      "Nosuch thing agg."], uksi)
    assert r["Bombus lucorum agg"].taxon.tvk == "BLSL"
    assert entry(r["Bombus lucorum agg"])["kingdom"] == "Animalia"   # kingdom/rank kept
    m = r["Carabus nemoralis AGG."]
    assert m.taxon.tvk == "CN" and entry(m)["warning"] == NO_AGGREGATE
    assert entry(m)["rank"] == "Species" and entry(m)["kingdom"] == "Animalia"
    same = entry(r["Cochlicopa lubrica agg."])            # typed exactly as UKSI holds it
    assert same["tvk"] == "CL" and same["warning"] == "" and same["import_notes"] == ""
    assert r["Nosuch thing agg."].kind == "not_found"


def test_cf_keeps_kingdom_and_rank(uksi):
    e = entry(lookup_names(["Carabus cf nemoralis"], uksi)["Carabus cf nemoralis"])
    assert e["tvk"] == "CN" and e["kingdom"] == "Animalia" and e["rank"] == "Species"
    assert e["warning"].startswith("cf. identification")


def test_a_genus_is_matched_as_a_genus_not_made_specific(uksi):
    m = lookup_names(["Lotus"], uksi)["Lotus"]
    assert m.taxon.rank == "Genus" and m.taxon.tvk == "LOT"


def test_a_failed_lookup_is_not_not_found():
    class Broken:
        def execute(self, *a):
            raise sqlite3.OperationalError("database is locked")
    r = lookup_names(["Carabus nemoralis"], Broken())["Carabus nemoralis"]
    assert r.kind == "error" and "may well be in UKSI" in entry(r)["error"]


def test_cancelled_stops_part_way(uksi):
    assert lookup_names(["Ab", "Carabus nemoralis"], uksi, cancelled=lambda: True) == {}


def test_works_with_a_uksi_model_too(uksi):
    class DB:
        def execute_uksi(self, sql, params):
            cur = uksi.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    class Model:
        db = DB()
    assert lookup_names(["Leptura maculata"], Model())["Leptura maculata"].taxon.tvk == "RM"
    assert search_candidates(Model(), "Populus alba")[0].tvk == "PA"


def test_apply_confirmed_replaces_only_the_species_error():
    from enum import Enum

    class RowStatus(Enum):                     # as the wizards' row_status.RowStatus
        VALID = "valid"
        WARNING = "warning"
        ERROR = "error"

    class Row:
        species_name = "Ab"
        species_tvk = ""
        common_name = order_name = family = kingdom = taxon_rank = import_notes = ""
        status = RowStatus.ERROR
        error_message = "Species not found in UKSI: Ab — closest: Populus alba; Unreadable date: '31/02/2024'"
        warnings = []
    row = Row()
    apply_confirmed(row, {"scientific_name": "Populus alba", "tvk": "PA", "kingdom": "Plantae"}, "Ab")
    assert (row.species_name, row.species_tvk, row.kingdom) == ("Populus alba", "PA", "Plantae")
    assert row.status == RowStatus.ERROR and row.error_message == "Unreadable date: '31/02/2024'"
    row2 = Row()
    row2.error_message = "Species not found in UKSI: Ab"
    apply_confirmed(row2, {"scientific_name": "Populus alba", "tvk": "PA"}, "Ab")
    assert row2.status == RowStatus.WARNING and "Imported as 'Ab'" in row2.import_notes
