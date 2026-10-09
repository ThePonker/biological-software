"""Examen report figures: taxonomic summary (E8b), compartments (E6), presentation (E8).

Pure functions on small hand-built inputs; no database.
"""
from types import SimpleNamespace as S

from Examen import compartments as cp
from Examen import presentation as pr
from Examen import taxonomic_summary as tx


def sp(name, tvk, order="", family=""):
    return S(name=name, tvk=tvk, order_name=order, family=family)


# ---- taxonomic summary --------------------------------------------------------

SPECIES = [
    sp("Carabus a", "T1", "Coleoptera", "Carabidae"),
    sp("Carabus b", "T2", "Coleoptera", "Carabidae"),
    sp("Stenus c", "T3", "Coleoptera", "Staphylinidae"),
    sp("Stenus c", "T3", "Coleoptera", "Staphylinidae"),        # same TVK twice: one taxon
    sp("Pardosa d", "T4", "Araneae", "Lycosidae"),
    sp("Mystery e", "T5", "", ""),                              # UKSI order unknown
    sp("No tvk f", "", "Coleoptera", "Carabidae"),              # cannot be analysed
]


def test_taxonomic_summary_counts_and_order():
    ts = tx.taxonomic_summary(SPECIES, {"T1", "T4", "T9"}, is_saproxylic=None)
    rows = {r.group: r for r in ts.rows}
    assert [r.group for r in ts.rows] == ["Coleoptera", "Araneae", tx.NO_ORDER]   # most taxa first, unknown last
    assert (rows["Coleoptera"].taxa, rows["Coleoptera"].with_status) == (3, 1)
    assert rows["Coleoptera"].pct == 33.3
    assert rows["Coleoptera"].families == "Carabidae 2, Staphylinidae 1"
    assert (rows["Araneae"].taxa, rows["Araneae"].with_status, rows["Araneae"].pct) == (1, 1, 100.0)
    assert ts.total.taxa == 5 and ts.total.with_status == 2          # T9 not recorded: not counted
    assert ts.without_tvk == 1 and ts.saproxylic is None


def test_taxonomic_summary_table_and_saproxylic_row():
    ts = tx.taxonomic_summary(SPECIES, {"T1", "T3"}, is_saproxylic=lambda s: s.tvk in ("T1", "T3"))
    heads, rows, notes = ts.table()
    assert heads == tx.HEADS
    assert rows[-2] == [tx.SAPROXYLIC_LABEL, "", 2, 2, "100.0%"]
    assert rows[-1] == [tx.TOTAL_LABEL, "3 groups", 5, 2, "40.0%"]
    assert any("without a TVK" in n and "is not counted" in n for n in notes)
    assert all(len(n) > 60 for n in notes)          # report_model reads short lines as rows


def test_families_text_caps_at_three():
    assert tx._families_text({"A": 1, "B": 5, "C": 2, "D": 2, "": 3}) == "B 5, C 2, D 2 (+1 more)"


def test_saproxylic_predicate_uses_the_list():
    assert tx.saproxylic_beetle(sp("Carabus intricatus", "", "Coleoptera"))
    assert not tx.saproxylic_beetle(sp("Pterostichus madidus", "", "Coleoptera"))


def test_for_result_without_a_species_list():
    assert tx.for_result(S(key_species=[]), None) is None


# ---- compartments --------------------------------------------------------------

def test_compartment_name_normalises_blanks():
    assert cp.compartment_name(None) == cp.NO_COMPARTMENT
    assert cp.compartment_name("   ") == cp.NO_COMPARTMENT
    assert cp.compartment_name(" Parcel  4 ") == "Parcel 4"


def test_split_records_accumulates():
    split = cp.split_records([
        ("A", "T1", "Sp one", 3), ("A", "T1", "Sp one (alt)", 2),   # same TVK, two names
        ("A", "", "Unmatched", 4), (None, "T2", "Sp two", 1), ("", "T3", "Sp three", 1),
        ("B", "T2", "Sp two", 5)])
    assert split["A"]["records"] == 9 and split["A"]["tvks"] == ["T1"]
    assert split[cp.NO_COMPARTMENT]["records"] == 2
    assert split[cp.NO_COMPARTMENT]["tvks"] == ["T2", "T3"]
    assert split["B"]["records"] == 5


def _sqi(value, scoring, reliable):
    return S(sqi=value, species_with_sqs=scoring, reliable=reliable)


def _fake_analyse(calls):
    def analyse(tvks, names):
        calls.append(sorted(tvks))
        key = sum(1 for t in tvks if t.startswith("K"))
        return S(total_species=len(tvks), key_species_count=key,
                 overall_sqi=_sqi(150.4, len(tvks) * 10, len(tvks) * 10 >= 15))
    return analyse


def test_analyse_compartments_figures_and_threshold():
    split = {
        "Big": {"records": 90, "tvks": ["K1", "T2", "T3"], "names": {}},
        cp.NO_COMPARTMENT: {"records": 7, "tvks": ["T4"], "names": {}},
        "Tiny": {"records": 3, "tvks": ["K1"], "names": {}},
    }
    combined = S(total_species=4, key_species_count=1, overall_sqi=_sqi(160, 40, True))
    calls = []
    res = cp.analyse_compartments(split, _fake_analyse(calls), combined=combined, threshold_pct=5)
    assert res.shown
    assert [r.name for r in res.rows] == ["Big", "Tiny", cp.NO_COMPARTMENT]   # no-compartment last
    big, tiny, none = res.rows
    assert (big.records, big.share_pct, big.species, big.key, big.key_pct) == (90, 90.0, 3, 1, 33.3)
    assert tiny.below_threshold and tiny.share_pct == 3.0
    assert not none.below_threshold                                             # 7% >= 5%
    assert [r.name for r in res.flagged] == ["Tiny"]
    assert res.combined.records == 100 and res.combined.species == 4            # the survey's own result
    assert len(calls) == 3                                                      # combined not re-analysed
    heads, rows, notes = res.table()
    assert rows[0][:8] == ["Big", 90, "90.0%", 3, 1, "33.3%", 30, 150]
    assert rows[1][7] == "(10 spp)" and rows[1][8] == "Below 5% of records"     # SQI withheld < 15
    assert rows[-1][0] == cp.COMBINED and rows[-1][7] == 160
    assert "5%" in notes[0] and any(cp.NO_COMPARTMENT in n for n in notes)


def test_single_compartment_is_not_shown_or_analysed():
    calls = []
    res = cp.analyse_compartments({cp.NO_COMPARTMENT: {"records": 12, "tvks": ["T1"], "names": {}}},
                                  _fake_analyse(calls))
    assert not res.shown and calls == []


def test_threshold_comes_from_config():
    assert cp.config()["min_share_pct"] == 5


# ---- presentation ---------------------------------------------------------------

def test_vernacular_fallback():
    assert pr.vernacular("Violet Ground Beetle", "Carabidae", "Coleoptera") == "Violet Ground Beetle"
    assert pr.vernacular("", "Carabidae", "Coleoptera") == "A ground beetle"
    assert pr.vernacular("", "Unknownidae", "Araneae") == "A spider"
    assert pr.vernacular("", "", "Dermaptera") == "An earwig"
    assert pr.vernacular("", "Ichneumonidae", "Hymenoptera") == "An ichneumon wasp"
    assert pr.vernacular("", "Strophariaceae", "Agaricales") == ""
    assert pr.is_description("", "A spider") and not pr.is_description("Wasp spider", "Wasp spider")


def test_status_names():
    assert pr.status_name("NS") == "Nationally Scarce"
    assert pr.status_name("RDB 3") == "Red Data Book 3"
    assert pr.status_name("Legal (2)") == "Legally protected (2)"
    assert pr.status_name("pNS") == "pNS"                      # unknown: unchanged
    assert pr.status_names("NT, NS, S41") == "Near Threatened, Nationally Scarce, Section 41"
    assert pr.status_name("") == ""
