"""Round 4A (24 Nov 2026): 1994-criteria fly statuses are Rare Key; the native rule for
derived SQS; one Key rule in import_status_review; the research-only S41 label.
Purpose-made objects and small databases only; no live data."""
import itertools
import os
import sqlite3
import sys
from types import SimpleNamespace as S

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "scripts")]

from Examen import workbook_export as we  # noqa: E402
from shared import key_species_rule as ks  # noqa: E402
from shared import sqs_derivation as sd  # noqa: E402
from shared.repositories.codex_repository import (  # noqa: E402
    AnalysisMode, CodexRepository, KeySpeciesTier as T, SpeciesStatus, StatusEntry,
    _classify, _priority_label)
from shared.services.pantheon_analysis_service import PantheonAnalysisService  # noqa: E402
from shared.repositories.pantheon_repository import PantheonRepository  # noqa: E402

POST94 = ("CR", "EN", "VU", "DD", "NT")


# ---- 1. 1994-criteria codes on the legacy threat track -------------------------------

def _status(**kw):
    st = SpeciesStatus(tvk="T1")
    for field, v in kw.items():
        setattr(st, field, StatusEntry(value=v))
    return st


@pytest.mark.parametrize("code", POST94)
def test_legacy_post94_codes_are_rare_in_codex_and_examen(code):
    assert ks.legacy_threat_tier(code) == "rare"
    assert _classify(_status(threat_iucn_legacy=code)) == T.RARE
    entry = S(rarity="", threat="", threat_legacy=code, priority=[], legal=[], tier="")
    assert we.telfer_tier(entry) == "rare"
    assert we.status_only_tier(entry) == "rare"


def test_legacy_ex_and_modern_nt_unchanged():
    assert ks.legacy_threat_tier("EX") == ""                       # EX on legacy: as before
    assert _classify(_status(threat_iucn_legacy="EX")) == T.NONE
    assert _classify(_status(threat_iucn_2001="NT")) == T.SCARCE   # modern NT stays Scarce
    assert _classify(_status(threat_iucn_2001="EX")) == T.RARE
    assert _classify(_status(threat_iucn_legacy="RDB3")) == T.RARE


def test_na_gate_still_beats_legacy_rare():
    assert _classify(_status(threat_iucn_2001="NA", threat_iucn_legacy="VU")) == T.NONE


# ---- 3. import_status_review.key_tiers agrees with the shared rule -------------------

def test_key_tiers_agrees_with_shared_rule():
    from import_status_review import key_tiers
    t2001 = ["", "NA", "LC", "NT", "VU", "EX", "DD"]
    rar = ["", "NR", "NS"]
    leg = ["", "RDB3", "NT", "DD", "EX"]
    rl = ["", "Na", "Notable"]
    for t, r, tl, l in itertools.product(t2001, rar, leg, rl):
        tracks = {"threat_iucn_2001": t, "rarity_modern": r,
                  "threat_iucn_legacy": tl, "rarity_legacy": l}
        st = _status(threat_iucn_2001=t, rarity_modern=r, threat_iucn_legacy=tl, rarity_legacy=l)
        want = _classify(st)
        key, rare = key_tiers(tracks)
        assert rare == (want == T.RARE), tracks
        assert key == (want in (T.RARE, T.SCARCE)), tracks


def test_key_tiers_examples():
    from import_status_review import key_tiers
    assert key_tiers({"threat_iucn_legacy": "NT"}) == (True, True)
    assert key_tiers({"threat_iucn_2001": "NT"}) == (True, False)
    assert key_tiers({"threat_iucn_2001": "NA", "rarity_modern": "NR"}) == (False, False)
    assert key_tiers({"threat_iucn_2001": "RE"}) == (True, True)
    assert key_tiers({}) == (False, False)


# ---- 2. the native rule for derived SQS ----------------------------------------------

def test_zero_reason_and_derivation():
    assert sd.zero_reason("NA") == sd.REASON_NA
    assert sd.zero_reason(" na ", True) == sd.REASON_NA
    assert sd.zero_reason("", True) == sd.REASON_PANTHEON_ZERO
    assert sd.zero_reason("NE", True) == sd.REASON_PANTHEON_ZERO
    assert sd.zero_reason("LC", True) == ""
    assert sd.zero_reason("", False) == ""
    assert sd.derive_from_tracks({"threat_iucn_2001": "NA", "rarity_modern": "NR"}) == 0
    assert sd.derive_from_tracks({"rarity_modern": "NS"}, pantheon_zero=True) == 0
    assert sd.derive_from_tracks({"rarity_modern": "NS", "threat_iucn_2001": "LC"},
                                 pantheon_zero=True) == 4


NA1, PZ, PZ_NE, PZ_LC, PZ_VU, PP_NA, PLAIN = ("U_NA", "U_PZ", "U_PZNE", "U_PZLC", "U_PZVU",
                                              "U_PPNA", "U_PLAIN")
ALL = [NA1, PZ, PZ_NE, PZ_LC, PZ_VU, PP_NA, PLAIN]


@pytest.fixture
def repos(tmp_path):
    def run(name, ddl, rows=()):
        p = tmp_path / name
        c = sqlite3.connect(str(p))
        c.executescript(ddl)
        for sql, data in rows:
            c.executemany(sql, data)
        c.commit()
        c.close()
        return str(p)
    uksi = run("uksi.db",
               "CREATE TABLE taxa (tvk TEXT PRIMARY KEY, scientific_name TEXT, rank TEXT, "
               "parent_tvk TEXT, kingdom TEXT, phylum TEXT, family TEXT, \"order\" TEXT, "
               "sort_code INTEGER);"
               "CREATE TABLE common_names (tvk TEXT, common_name TEXT, preferred INTEGER);",
               [("INSERT INTO taxa VALUES (?,?,'Species','G','Animalia','Arthropoda','F','O',1)",
                 [(t, f"Sp {t}") for t in ALL])])
    ss = [(NA1, "threat_iucn_2001", "NA"), (NA1, "rarity_modern", "NR"),
          (PZ, "rarity_modern", "NS"),
          (PZ_NE, "threat_iucn_2001", "NE"), (PZ_NE, "rarity_modern", "NS"),
          (PZ_LC, "threat_iucn_2001", "LC"), (PZ_LC, "rarity_modern", "NS"),
          (PZ_VU, "threat_iucn_2001", "VU"),
          (PP_NA, "threat_iucn_2001", "NA"),
          (PLAIN, "rarity_modern", "NS")]
    codex = run("codex.db", """
        CREATE TABLE designations (tvk TEXT, category TEXT);
        CREATE TABLE status_summary (tvk TEXT, status_track TEXT, status_value TEXT,
            status_detail TEXT, source TEXT, iucn_version TEXT);
        CREATE TABLE sqs_scores (tvk TEXT PRIMARY KEY, sqs INTEGER, source TEXT DEFAULT 'pantheon');
        CREATE TABLE species_profiles (tvk TEXT, profile_text TEXT, source TEXT);
        CREATE TABLE tvk_bridge (pantheon_tvk TEXT PRIMARY KEY, uksi_tvk TEXT,
            species_name TEXT, match_method TEXT);""", [
        ("INSERT INTO status_summary VALUES (?,?,?,NULL,'test','')", ss),
        ("INSERT INTO sqs_scores (tvk, sqs) VALUES (?,?)", [(PP_NA, 8)]),
        ("INSERT INTO tvk_bridge VALUES (?,?,?,'exact')",
         [(f"P_{t}", t, f"Sp {t}") for t in (PZ, PZ_NE, PZ_LC, PZ_VU, PP_NA)])])
    pan = run("pantheon.db", """
        CREATE TABLE species (tvk TEXT PRIMARY KEY, species_name TEXT, family TEXT);
        CREATE TABLE sqs_scores (tvk TEXT, sqs INTEGER);
        CREATE TABLE conservation_status (tvk TEXT, reporting_category TEXT, abbreviation TEXT);
        CREATE TABLE broad_biotope (tvk TEXT, biotope TEXT);
        CREATE TABLE habitats (tvk TEXT, habitat TEXT);
        CREATE TABLE specific_assemblage_types (tvk TEXT, sat_name TEXT);
        CREATE TABLE feeding_guilds (tvk TEXT, life_stage TEXT, guild TEXT);
        CREATE TABLE fidelity_scores (tvk TEXT, index_name TEXT, score TEXT);
        CREATE TABLE associations (tvk TEXT, associated_taxa_type TEXT, associated_taxa TEXT);""",
              [("INSERT INTO sqs_scores VALUES (?,?)",
                [(f"P_{t}", 0) for t in (PZ, PZ_NE, PZ_LC, PZ_VU)] + [(f"P_{PP_NA}", 8)])])
    cx = CodexRepository(codex, pan, uksi_path=uksi)
    yield cx, PantheonRepository(pan, codex_path=codex, uksi_path=uksi)
    cx.close()


def test_native_rule_in_codex_full(repos):
    cx, _ = repos
    got = cx.get_sqs_scores(ALL)
    assert NA1 not in got                          # NA: no score (would have been 8)
    assert PZ not in got and PZ_NE not in got      # Pantheon 0, no JNCC assessment (NE counts as none)
    assert got[PZ_LC] == 4                         # LC with Pantheon 0 keeps its derived score
    assert got[PZ_VU] == 8                         # any other assessment keeps its score
    assert got[PP_NA] == 8                         # a published score is never touched
    assert got[PLAIN] == 4
    assert cx.get_zero_sqs_reasons(ALL) == {
        NA1: sd.REASON_NA, PZ: sd.REASON_PANTHEON_ZERO, PZ_NE: sd.REASON_PANTHEON_ZERO}
    assert cx.get_sqs_scores(ALL, AnalysisMode.PANTHEON_ONLY) == {PP_NA: 8}


def test_pantheon_published_zero(repos):
    _, pan = repos
    assert pan.get_published_zero_tvks(ALL) == {PZ, PZ_NE, PZ_LC, PZ_VU}


def test_analysis_reports_zero_reasons_and_sqi(repos):
    cx, pan = repos
    r = PantheonAnalysisService(pan, cx).analyse(ALL)
    assert r.zero_sqs_reasons == {NA1: sd.REASON_NA, PZ: sd.REASON_PANTHEON_ZERO,
                                  PZ_NE: sd.REASON_PANTHEON_ZERO}
    # NA1 is neither scored nor held by Pantheon, so it is not analysed; the two
    # Pantheon-held zeros are analysed with no score.
    assert r.species_analysed == 6 and r.overall_sqi.sqs_sum == 4 + 8 + 8 + 4
    p = PantheonAnalysisService(pan, cx).analyse(ALL, mode=AnalysisMode.PANTHEON_ONLY)
    assert p.zero_sqs_reasons == {}
    text = we.zero_sqs_text(r, S(species_list=[S(tvk=NA1, name="Naus alienus")]))
    assert "Naus alienus" in text and sd.REASON_NA in text and sd.REASON_PANTHEON_ZERO in text
    assert we.zero_sqs_text(p, None) == ""


# ---- 4. research-only S41 label ------------------------------------------------------

def test_research_only_s41_label_in_workbook():
    v = "NERC S.41 England (research)"
    assert _priority_label(v) == "S41 (research only)"
    assert we._short_jurisdiction(v) == "S41 (research only)"
    assert we._short_jurisdiction("UK BAP (research)") == "UK BAP (research only)"
    assert we._short_jurisdiction("NERC S.41 England") == "S41"
    entry = S(threat="", threat_legacy="", rarity="NS", priority=[v], legal=[], status_note="")
    assert we.status_string(entry) == "NS, S41 (research only)"
    assert we.status_parts(entry, "England")[-1][0] == "S41 (research only)"
