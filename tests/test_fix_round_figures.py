"""Fix round, 9 Oct 2026: one SQI, one bridge rule, invertebrates from UKSI, species
and broad group (EXA1, INF1/EXA6, EXA7, CDX-1, EXA4, EXA5, EXA10, EXA13, EXA14, EXA3).

Small hand-built codex.db / pantheon.db / uksi.db in a temporary folder; the real
databases are not touched.
"""
import os
import sqlite3
import sys
from types import SimpleNamespace as S

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "scripts")]

from shared.repositories.codex_repository import (  # noqa: E402
    AnalysisMode, CodexRepository, binomial_key)
from shared.repositories.pantheon_repository import (  # noqa: E402
    NOTVK_PREFIX, PantheonRepository, j2_order)
from shared.services.pantheon_analysis_service import (  # noqa: E402
    RECORDED_SL_SS, PantheonAnalysisService)

# ---- the fixture -------------------------------------------------------------
# UKSI (current) TVKs
A, B, C, D = "U_A", "U_B", "U_C", "U_D"          # bridge cases
X, XSL = "U_X", "U_XSL"                          # species + sensu lato
Y, YAGG = "U_Y", "U_YAGG"                        # species + aggregate
R, V = "U_R", "U_V"                              # review-only invertebrate; a bird
G = "U_GENUS"

TAXA = [  # tvk, name, rank, parent, kingdom, phylum
    (A, "Alpha one", "Species", G, "Animalia", "Arthropoda"),
    (B, "Beta two", "Species", G, "Animalia", "Arthropoda"),
    (C, "Gamma three", "Species", G, "Animalia", "Arthropoda"),
    (D, "Delta four", "Species", G, "Animalia", "Arthropoda"),
    (X, "Xan ped", "Species", G, "Animalia", "Arthropoda"),
    (XSL, "Xan ped", "Species sensu lato", G, "Animalia", "Arthropoda"),
    (Y, "Yota sp", "Species", G, "Animalia", "Arthropoda"),
    (YAGG, "Yota sp agg.", "Species aggregate", G, "Animalia", "Arthropoda"),
    (R, "Rev only", "Species", G, "Animalia", "Arthropoda"),
    (V, "Vert bird", "Species", G, "Animalia", "Chordata"),
    (G, "Genus", "Genus", None, "Animalia", "Arthropoda"),
]

# Bridge rows in build order (rowid order matters: it is the tie-break).
BRIDGE = [  # pantheon_tvk, uksi_tvk, pantheon name, method
    (NOTVK_PREFIX + "Alpha onee", A, "Alpha onee", "name"),   # empty misspelt twin, FIRST
    (A, A, "Alpha one", "direct"),
    ("P_B2", B, "Beta sunk", "name"),                          # collider, listed first
    ("P_B1", B, "Beta two", "name"),                           # incumbent by exact name
    ("P_C1", C, "Gamma old", "name"),                          # no incumbent at all
    ("P_C2", C, "Gamma other", "name"),
    (NOTVK_PREFIX + "Delta fourr", D, "Delta fourr", "name"),
    (D, D, "Delta four", "direct"),
    (X, X, "Xan ped", "direct"),
    (XSL, XSL, "Xan ped", "direct"),
    (Y, Y, "Yota sp", "direct"),
    (YAGG, YAGG, "Yota sp agg.", "direct"),
]

PAN_SPECIES = [(NOTVK_PREFIX + "Alpha onee", "Alpha onee", ""), (A, "Alpha one", "Fam"),
               ("P_B1", "Beta two", "Fam"), ("P_B2", "Beta sunk", "Fam"),
               ("P_C1", "Gamma old", "Fam"), ("P_C2", "Gamma other", "Fam"),
               (NOTVK_PREFIX + "Delta fourr", "Delta fourr", ""), (D, "Delta four", "Fam"),
               (X, "Xan ped", "Fam"), (XSL, "Xan ped", "Fam"),
               (Y, "Yota sp", "Fam"), (YAGG, "Yota sp agg.", "Fam")]
PAN_SQS = [(A, 2), ("P_B1", 1), ("P_B2", 8), ("P_C2", 4), (D, 8), (X, 1), (XSL, 4), (YAGG, 8)]
PAN_STATUS = [("P_B1", "GB Status", "Nb"), ("P_B2", "GB Status", "NR"),
              ("P_B2", "Section 41 Priority Species", "S41"), (D, "GB Status", "NS")]
PAN_BIOTOPE = [(A, "wetland"), ("P_B1", "wetland"), ("P_B2", "wetland"), ("P_B2", "coastal"),
               (D, "tree-associated"), (X, "open habitats"), (XSL, "wetland"), (YAGG, "coastal")]
PAN_HABITAT = [(A, "fen"), (X, "short sward"), (XSL, "fen")]
PAN_SAT = [(X, "sat one"), (XSL, "sat one"), (XSL, "sat two"), (D, "sat one")]
PAN_GUILD = [(C and "P_C1", "larval guild", "predator")]

STATUS = [  # codex status_summary: tvk, track, value
    (XSL, "rarity_modern", "NS"),          # held only at sensu lato
    (Y, "threat_iucn_2001", "LC"),         # the species' own (weaker) status
    (YAGG, "rarity_modern", "NR"),
    (R, "rarity_modern", "NS"),            # from a review only: no designation row
    (V, "rarity_modern", "NR"),            # a bird: never Key
    (D, "rarity_modern", "NS"),
]
DESIGNATIONS = [(D, "Invertebrate")]       # the only JNCC-categorised invertebrate
CODEX_SQS = [(A, 2), (B, 1), (C, 4), (D, 8), (X, 1), (YAGG, 8)]


def _db(path, ddl, rows):
    c = sqlite3.connect(str(path))
    c.executescript(ddl)
    for sql, data in rows:
        c.executemany(sql, data)
    c.commit()
    c.close()
    return str(path)


@pytest.fixture()
def dbs(tmp_path):
    uksi = _db(tmp_path / "uksi.db",
               "CREATE TABLE taxa (tvk TEXT PRIMARY KEY, scientific_name TEXT, rank TEXT, "
               "parent_tvk TEXT, kingdom TEXT, phylum TEXT);",
               [("INSERT INTO taxa VALUES (?,?,?,?,?,?)", TAXA)])
    codex = _db(tmp_path / "codex.db", """
        CREATE TABLE designations (tvk TEXT, category TEXT);
        CREATE TABLE status_summary (tvk TEXT, status_track TEXT, status_value TEXT,
            status_detail TEXT, source TEXT, iucn_version TEXT);
        CREATE TABLE sqs_scores (tvk TEXT PRIMARY KEY, sqs INTEGER, source TEXT DEFAULT 'pantheon');
        CREATE TABLE species_profiles (tvk TEXT, profile_text TEXT, source TEXT);
        CREATE TABLE tvk_bridge (pantheon_tvk TEXT PRIMARY KEY, uksi_tvk TEXT,
            species_name TEXT, match_method TEXT);""", [
        ("INSERT INTO designations VALUES (?,?)", DESIGNATIONS),
        ("INSERT INTO status_summary VALUES (?,?,?,NULL,'test','')", STATUS),
        ("INSERT INTO sqs_scores (tvk, sqs) VALUES (?,?)", CODEX_SQS),
        ("INSERT INTO tvk_bridge VALUES (?,?,?,?)", BRIDGE)])
    pantheon = _db(tmp_path / "pantheon.db", """
        CREATE TABLE species (tvk TEXT PRIMARY KEY, species_name TEXT, family TEXT);
        CREATE TABLE sqs_scores (tvk TEXT, sqs INTEGER);
        CREATE TABLE conservation_status (tvk TEXT, reporting_category TEXT, abbreviation TEXT);
        CREATE TABLE broad_biotope (tvk TEXT, biotope TEXT);
        CREATE TABLE habitats (tvk TEXT, habitat TEXT);
        CREATE TABLE specific_assemblage_types (tvk TEXT, sat_name TEXT);
        CREATE TABLE feeding_guilds (tvk TEXT, life_stage TEXT, guild TEXT);
        CREATE TABLE fidelity_scores (tvk TEXT, index_name TEXT, score TEXT);
        CREATE TABLE associations (tvk TEXT, associated_taxa_type TEXT, associated_taxa TEXT);""", [
        ("INSERT INTO species VALUES (?,?,?)", PAN_SPECIES),
        ("INSERT INTO sqs_scores VALUES (?,?)", PAN_SQS),
        ("INSERT INTO conservation_status VALUES (?,?,?)", PAN_STATUS),
        ("INSERT INTO broad_biotope VALUES (?,?)", PAN_BIOTOPE),
        ("INSERT INTO habitats VALUES (?,?)", PAN_HABITAT),
        ("INSERT INTO specific_assemblage_types VALUES (?,?)", PAN_SAT),
        ("INSERT INTO feeding_guilds VALUES (?,?,?)", PAN_GUILD)])
    pan = PantheonRepository(pantheon, codex_path=codex, uksi_path=uksi)
    cx = CodexRepository(codex, pantheon, uksi_path=uksi)
    yield S(pan=pan, codex=cx, svc=PantheonAnalysisService(pan, cx))
    pan.close()
    cx.close()


# ---- the bridge (INF1 / EXA6 / EXA7) -------------------------------------------

def test_j2_order_incumbent_first_and_notvk_last():
    rows = [("NOTVK:x", "x"), ("P2", "sunk"), ("P1", "Beta two")]
    assert j2_order("U", "Beta two", rows) == ["P1", "P2", "NOTVK:x"]
    assert j2_order("P2", "Beta two", rows) == ["P2", "P1", "NOTVK:x"]   # own TVK beats the name


def test_bridge_sqs_follows_j2_not_the_maximum(dbs):
    got = dbs.pan.get_sqs_scores([A, B, C, D])
    assert got[A] == 2          # the empty NOTVK twin does not hide the score
    assert got[B] == 1          # the incumbent's 1, not the collider's 8
    assert got[C] == 4          # no incumbent: the first candidate that has one
    assert got[D] == 8


def test_strict_mode_reads_through_the_same_bridge(dbs):
    strict = dbs.codex.get_sqs_scores([A, B, C, D], AnalysisMode.PANTHEON_ONLY)
    assert strict == dbs.pan.get_sqs_scores([A, B, C, D])
    st = dbs.codex.get_statuses_batch([B, D], AnalysisMode.PANTHEON_ONLY)
    # GB Status is single-valued: the incumbent's Nb, never the collider's NR ...
    assert st[B].rarity_legacy.value == "Nb" and st[B].rarity_modern is None
    # ... while list categories are unioned
    assert [e.value for e in st[B].priority] == ["NERC S.41 England"]
    assert st[D].sqs == 8 and st[D].rarity_modern.value == "NS"


def test_ecology_is_unioned_incumbent_first(dbs):
    assert dbs.pan.get_broad_biotopes([B])[B] == ["wetland", "coastal"]
    assert dbs.pan.get_feeding_guilds([C])[C] == {"larval guild": "predator"}


def test_profile_combines_candidates_and_skips_the_empty_twin(dbs):
    p = dbs.pan.get_species_profile(D)
    assert p.species_name == "Delta four" and p.sqs == 8 and p.gb_status == "NS"
    assert p.pantheon_tvks == [D, NOTVK_PREFIX + "Delta fourr"]
    b = dbs.pan.get_species_profile(B)
    assert b.sqs == 1 and b.gb_status == "Nb" and b.section41
    assert b.broad_biotopes == ["wetland", "coastal"]


def test_national_pool_counts_each_species_once(dbs):
    pool = dbs.pan.national_pool_counts()
    # P_B1 and P_B2 are both wetland but are one current species
    assert pool["biotope"]["wetland"] == 3          # A, B, XSL
    assert pool["sat"]["sat one"] == 3              # X, XSL, D


def test_held_by_pantheon_is_any_ecology_or_score(dbs):
    assert dbs.pan.held_by_pantheon([A, C, R, V]) == {A, C}     # C: a guild only


# ---- invertebrates from UKSI (CDX-1) and species / broad group --------------------

def test_invertebrate_from_uksi_taxonomy(dbs):
    st = dbs.codex.get_statuses_batch([R, V])
    assert st[R].is_invertebrate and st[R].is_key          # review-only status: Key now
    assert not st[V].is_invertebrate and not st[V].is_key  # Chordata: never Key


def test_status_held_at_sensu_lato(dbs):
    s = dbs.codex.get_status_summary(X)
    assert s.rarity_modern.value == "NS" and s.is_key
    assert (s.status_held_at, s.status_from_tvk) == ("sensu lato", XSL)
    assert s.display_status.endswith("status held at sensu lato")
    y = dbs.codex.get_status_summary(Y)                    # has its own: no fallback
    assert y.status_held_at == "" and y.rarity_modern is None
    summary = dbs.codex.get_species_conservation_summary(X)
    assert summary["status_held_at"] == "sensu lato"


def test_binomial_key_strips_group_suffixes():
    assert binomial_key("Yota sp agg.") == "yota sp"
    assert binomial_key("Xan  ped s.l.") == "xan ped"
    assert binomial_key("Xan ped") == "xan ped"


def test_derived_sqs_is_flagged(dbs):
    s = dbs.codex.get_status_summary(R)       # no stored score; NS from a review only
    assert s.sqs == 4 and s.sqs_derived
    assert not dbs.codex.get_status_summary(D).sqs_derived
    assert dbs.codex.get_sqs_scores([V]) == {}            # a bird is never scored


# ---- two TVKs, one species (EXA14) and the counts (EXA4 / EXA5) --------------------

def test_two_tvks_one_species(dbs):
    r = dbs.svc.analyse([X, XSL, Y, YAGG, B], {X: "Xan ped", Y: "Yota sp", B: "Beta two"})
    assert r.total_species == 3
    assert r.merged_tvks == {XSL: X, YAGG: Y}
    assert r.sqs_by_tvk[X] == 1                       # the species' own score (J2)
    # Y's own score would only be derived (LC -> 1); the aggregate's is published
    assert r.sqs_by_tvk[Y] == 8 and Y not in r.derived_sqs_tvks
    assert r.statuses[Y].rarity_modern.value == "NR"  # the stronger status
    assert set(r.biotopes_by_tvk[X]) == {"open habitats", "wetland"}
    keyed = {k.tvk: k for k in r.key_species}
    assert keyed[Y].recorded_note == RECORDED_SL_SS
    assert XSL not in r.sqs_by_tvk and YAGG not in r.statuses


def test_stenotopic_species_counted_once(dbs):
    r = dbs.svc.analyse([X, XSL, D])
    assert sum(r.sat_counts.values()) == 3            # X in two SATs, D in one
    assert r.stenotopic_count == 2


def test_scoring_never_exceeds_analysed(dbs):
    r = dbs.svc.analyse([A, B, C, D, R, X, XSL])
    assert r.species_with_sqs <= r.species_analysed
    assert r.overall_sqi.species_analysed == r.species_analysed
    assert r.species_in_pantheon <= r.species_analysed


# ---- one SQI (EXA1) ------------------------------------------------------------------

@pytest.mark.parametrize("mode", [AnalysisMode.CODEX_FULL, AnalysisMode.PANTHEON_ONLY])
def test_compute_sqi_is_the_analysis_sqi(dbs, mode):
    tvks = [A, B, C, D, R, X, XSL]
    o = dbs.svc.analyse(tvks, mode=mode).overall_sqi
    got = dbs.codex.compute_sqi(tvks, mode)
    assert (got["sqi"], got["sqs_sum"], got["scoring_species"], got["species_analysed"]) == \
        (o.sqi, o.sqs_sum, o.species_with_sqs, o.species_analysed)
    # divides by species analysed, not by scoring species
    assert got["sqi"] == round(got["sqs_sum"] / got["species_analysed"] * 100)


# ---- report wording (EXA10, EXA3, EXA2) -------------------------------------------

def test_key_rows_name_each_legal_instrument():
    from Examen.workbook_export import status_parts, status_string
    k = S(threat="", threat_legacy="", rarity="NS", priority=[],
          legal=["WCA 1981 Sch5", "NI Wildlife Order Sch5"], status_note="")
    parts = status_parts(k, "England")
    assert ("Legal: WCA 1981 Sch5", True) in parts
    assert ("Legal: NI Wildlife Order Sch5", False) in parts     # greyed, not counted
    assert not any(t.startswith("Legal (") for t, _ in parts)
    assert "Legal: WCA 1981 Sch5" in status_string(k)


def test_jncc_date_comes_from_the_file():
    import build_codex_db as b
    assert b.jncc_date_of("x/taxon-designations-20260609.xlsx") == "2026-06-09"
    assert b.jncc_date_of(os.path.join("nowhere", "designations.xlsx")) == "unknown"


def test_jurisdiction_resolution_is_shared():
    from Examen import examen_data as ed
    assert ed.resolve_jurisdiction(None, "Wales") == ("Wales", "chosen")
    assert ed.resolve_jurisdiction(None, ed.AUTO_JURISDICTION)[0] == "England"
    assert ed.country_for_vc(35) == "Wales" and ed.country_for_vc(80) == "Scotland"
