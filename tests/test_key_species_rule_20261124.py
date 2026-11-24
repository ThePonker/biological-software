"""One Rare / Scarce Key Species rule for Examen and Codex (24 Nov 2026).
Purpose-made entries only; no live data."""
from types import SimpleNamespace as S

import pytest

from Examen import workbook_export as we
from shared import key_species_rule as ks
from shared.repositories.codex_repository import (
    KeySpeciesTier as T,
    SpeciesStatus,
    StatusEntry,
    _classify,
)

FIELDS = {"threat": "threat_iucn_2001", "rarity": "rarity_modern",
          "threat_legacy": "threat_iucn_legacy", "rarity_legacy": "rarity_legacy"}


def _status(**kw):
    st = SpeciesStatus(tvk="T1")
    for k, v in kw.items():
        setattr(st, FIELDS[k], StatusEntry(value=v))
    return st


def _entry(**kw):
    base = dict(rarity="", threat="", threat_legacy="", priority=[], legal=[], tier="")
    base.update(kw)
    return S(**base)


def _both(**kw):
    """(Examen tier, Codex tier) for one code. Examen merges both rarity fields."""
    ex = dict(kw)
    if "rarity_legacy" in ex:
        ex["rarity"] = ex.pop("rarity_legacy")
    return we.telfer_tier(_entry(**ex)), _classify(_status(**kw)).value.lower()


@pytest.mark.parametrize("code", ["RDB3", "RDBK", "RDB 3", "RDBI", "rdb1"])
def test_rdb_codes_are_rare_in_both(code):
    assert _both(threat_legacy=code) == ("rare", "rare")


def test_ew_is_rare_in_both():
    assert _both(threat="EW") == ("rare", "rare")


@pytest.mark.parametrize("code", ["Na", "NA ", "nb", " Notable ", "N", "Scarce"])
def test_legacy_rarity_normalises_to_scarce(code):
    st = _status(rarity_legacy=code)
    assert _classify(st) == T.SCARCE
    assert we.telfer_tier(_entry(rarity=code)) == "scarce"


def test_na_threat_is_never_key():
    assert _classify(_status(threat="NA", rarity="NR")) == T.NONE
    assert _classify(_status(threat=" na ", threat_legacy="RDB1")) == T.NONE
    assert we.telfer_tier(_entry(threat="NA", rarity="NR")) == ""


def test_codex_other_rules_unchanged():
    st = _status(rarity="NS")
    st.specialist_panel = StatusEntry(value="Amber")
    assert _classify(st) == T.SCARCE
    st = _status(threat="NT")
    st.specialist_panel = StatusEntry(value="Red")
    assert _classify(st) == T.SCARCE
    assert _classify(_status(threat="LC")) == T.NONE
    assert _classify(_status(threat="NT", rarity="NR")) == T.RARE


def test_examen_and_codex_agree_on_every_shared_code():
    for code in sorted(ks.ALL_CODES):
        for field in ("threat", "rarity", "threat_legacy"):
            ex = we.telfer_tier(_entry(**{field: code}))
            cx = _classify(_status(**{field: code}))
            if code == "NA" and field == "threat":
                assert ex == "" and cx == T.NONE      # NA threat: not applicable
                continue
            # Codex reads each code in its own field; the shared rule must give the same
            # answer as the field's helper, and Codex must never be less than that.
            helper = {"threat": ks.threat_tier, "rarity": ks.rarity_tier,
                      "threat_legacy": ks.legacy_threat_tier}[field](code)
            assert ex == helper
            assert cx.value.lower() == (helper or "none")


def test_status_codes_cover_shared_sets():
    assert we.STATUS_CODES == frozenset(c.strip().upper() for c in ks.ALL_CODES)
