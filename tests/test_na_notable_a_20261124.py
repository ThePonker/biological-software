"""Notable A ("Na") and Not Applicable ("NA") told apart (24 Nov 2026).

Upper-cased, both are "NA". The line decides: Notable A on a rarity line, Not Applicable on
a threat line -- except "Na" exactly on a threat line (a misplaced Notable A: counts as
neither). Imports refuse either spelt for the wrong line; Codex and Examen label both.
"""
import sqlite3

import pytest

from shared import key_species_rule as ks
from shared.sqs_derivation import derive_sqs, zero_reason


def test_notable_a_counts_only_as_na_on_a_rarity_line():
    assert ks.rarity_tier("Na") == "scarce"
    assert ks.rarity_tier(" Na ") == "scarce"
    assert ks.rarity_tier("NA") == "scarce"      # a rarity line cannot hold Not Applicable
    assert ks.rarity_tier("Nb") == "scarce"      # other codes still any case
    assert ks.rarity_tier("nb") == "scarce"
    assert ks.legacy_threat_tier("NA") == ""
    assert ks.legacy_threat_tier("Na") == ""     # Notable A lives on the rarity line


def test_not_applicable_is_exact_na():
    assert ks.is_not_applicable("NA") and ks.is_not_applicable(" NA ")
    assert ks.is_not_applicable("na")            # any case on a threat line...
    assert not ks.is_not_applicable("Na")        # ...except Notable A's own spelling
    assert ks.threat_tier("Na") == ""            # and Notable A never counts there


def test_sqs_and_native_rule_follow_the_spelling():
    assert zero_reason("NA")
    assert zero_reason("Na") == ""               # Notable A on the threat line: not "not native"
    notable = derive_sqs(rarity="Na")
    assert notable > 0
    assert derive_sqs(rarity="Nb") == notable    # same rung as Notable B
    assert derive_sqs(rarity="NA") == notable    # rarity line: Notable A
    assert derive_sqs(rarity="Na", threat="Na") == notable   # misplaced: not zeroed


def test_case_problem_names_the_wrong_spelling():
    assert ks.case_problem("rarity_legacy", "Na") == ""
    assert ks.case_problem("threat_iucn_2001", "NA") == ""
    assert ks.case_problem("rarity_modern", "NR") == ""
    assert ks.case_problem("threat_iucn_2001", "VU") == ""
    assert "rarity line" in ks.case_problem("rarity_legacy", "NA")
    assert "threat line" in ks.case_problem("threat_iucn_2001", "Na")
    assert ks.case_problem("threat_iucn_legacy", "na")


def test_code_labels():
    assert ks.code_label("Na") == "Na (Notable A)"
    assert ks.code_label("NA") == "NA (not applicable)"
    assert ks.code_label("VU") == "VU"
    assert "Na" in ks.ALL_CODES and "NA" not in ks.ALL_CODES


def test_codex_colour_never_greys_notable_a():
    from Codex import theme
    assert theme.status_colour("NA") == theme.CAT_COLOURS["NA"]
    assert theme.status_colour("Na") != theme.CAT_COLOURS["NA"]
    assert theme.status_colour("vu") == theme.CAT_COLOURS["VU"]


def test_examen_not_native_gate_is_exact():
    from types import SimpleNamespace
    from Examen.workbook_export import _is_not_native, telfer_tier
    assert _is_not_native(SimpleNamespace(threat="NA"))
    assert not _is_not_native(SimpleNamespace(threat="Na"))
    assert telfer_tier(SimpleNamespace(rarity="Na", threat="", threat_legacy="")) == "scarce"
    assert telfer_tier(SimpleNamespace(rarity="Na", threat="NA", threat_legacy="")) == ""


def test_examen_names_both():
    from Examen.presentation import status_name
    assert status_name("Na") == "Notable A"
    assert status_name("NA").startswith("Not applicable")


def test_apply_status_refuses_the_wrong_spelling_before_deleting():
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))
    from import_status_review import apply_status
    c = sqlite3.connect(":memory:")
    c.execute("""CREATE TABLE status_summary (tvk, status_track, status_value, status_detail,
                 source, iucn_version, date_designated, origin)""")
    c.execute("INSERT INTO status_summary (tvk, status_track, status_value) "
              "VALUES ('T1', 'rarity_legacy', 'Na')")
    with pytest.raises(ValueError, match="rarity line"):
        apply_status(c, "T1", "rarity_legacy", "NA", None, "test", "2026-11-24")
    assert c.execute("SELECT status_value FROM status_summary").fetchall() == [("Na",)]
    apply_status(c, "T1", "threat_iucn_2001", "NA", None, "test", "2026-11-24")
    assert ("NA",) in c.execute("SELECT status_value FROM status_summary").fetchall()
