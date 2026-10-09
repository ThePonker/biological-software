"""Examen -- taxonomic summary table (backlog E8b).

    Group | Main families | Taxa | Spp. with status | % with status

after EMG2 Table 2, with an "All saproxylic beetles" row to show where the interest
sits. Computed here once; the Conservation tab, the workbook sheet and (through the
workbook) the PDF and Word reports all lay out the same rows.

* Group is the UKSI order -- the grouping the species appendix and key-species table
  already use (examen_data.load_taxonomy).
* "With status" means a Key Species: the same set the Summary's Key Species count is
  taken from (AnalysisResult.key_species, Codex's is_key under the assessment's
  jurisdiction). Nothing is reclassified here.
* Taxa are counted once per TVK, as the Summary counts species; species without a
  TVK cannot be analysed and are reported as excluded, not silently dropped.
* The saproxylic row counts recorded beetles that match the saproxylic list
  (Examen.saproxylic.match), the same matching the Saproxylic sheet uses.

    from Examen.taxonomic_summary import taxonomic_summary
    ts = taxonomic_summary(detail.species_list, {k.tvk for k in result.key_species})
    heads, rows, notes = ts.table()
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

NO_ORDER = "(order not known)"
SAPROXYLIC_LABEL = "All saproxylic beetles"
TOTAL_LABEL = "All groups"
TOP_FAMILIES = 3
HEADS = ["Group", "Main families (taxa)", "Taxa", "Spp. with status", "% with status"]


@dataclass
class TaxRow:
    group: str
    families: str
    taxa: int
    with_status: int

    @property
    def pct(self) -> Optional[float]:
        return round(self.with_status / self.taxa * 100, 1) if self.taxa else None

    def cells(self) -> list:
        return [self.group, self.families, self.taxa, self.with_status,
                f"{self.pct}%" if self.pct is not None else "-"]


@dataclass
class TaxSummary:
    rows: List[TaxRow] = field(default_factory=list)      # one per group, most taxa first
    saproxylic: Optional[TaxRow] = None                   # None when no listed beetle occurs
    total: Optional[TaxRow] = None
    without_tvk: int = 0

    def table(self):
        """(heads, rows, notes) -- the one layout every renderer uses."""
        rows = [r.cells() for r in self.rows]
        if self.saproxylic is not None:
            rows.append(self.saproxylic.cells())
        if self.total is not None:
            rows.append(self.total.cells())
        notes = ["Spp. with status are Key Species, as counted on the Summary: rare, scarce, "
                 "threatened or near threatened status, or a priority listing that applies in "
                 "this jurisdiction."]
        if self.saproxylic is not None:
            notes.append(f"{SAPROXYLIC_LABEL}: recorded beetles on the saproxylic list "
                         "(see Saproxylic indices); they are also counted under Coleoptera.")
        if self.without_tvk:
            one = self.without_tvk == 1
            notes.append(f"{self.without_tvk} name{'' if one else 's'} without a TVK "
                         f"cannot be analysed and {'is' if one else 'are'} not counted here.")
        return list(HEADS), rows, notes


def _families_text(fam_counts: dict, top: int = TOP_FAMILIES) -> str:
    named = sorted(((f, n) for f, n in fam_counts.items() if f), key=lambda x: (-x[1], x[0]))
    text = ", ".join(f"{f} {n}" for f, n in named[:top])
    if len(named) > top:
        text += f" (+{len(named) - top} more)"
    return text


def saproxylic_beetle(sp) -> bool:
    """True for a recorded species on the saproxylic list (a list of beetles). Not
    filtered on UKSI order: a beetle record carrying a homonym's TVK (Kent Deadwood's
    'Melanotus', on the fungus genus) is still the beetle the list names."""
    try:
        from Examen.saproxylic import match
    except ImportError:  # pragma: no cover
        from saproxylic import match
    return match(getattr(sp, "tvk", ""), getattr(sp, "name", "")) is not None


def taxonomic_summary(species, key_tvks,
                      is_saproxylic: Optional[Callable] = saproxylic_beetle) -> TaxSummary:
    """species: items with .tvk, .name, .order_name, .family (examen_data.SiteSpecies).
    key_tvks: the TVKs counted as Key Species. is_saproxylic: predicate for the
    saproxylic row, or None for no such row."""
    key_tvks = set(key_tvks or ())
    seen, groups = set(), {}
    sap_taxa = sap_key = 0
    out = TaxSummary()
    for sp in species or []:
        tvk = getattr(sp, "tvk", "") or ""
        if not tvk:
            out.without_tvk += 1
            continue
        if tvk in seen:
            continue
        seen.add(tvk)
        order = (getattr(sp, "order_name", "") or "").strip() or NO_ORDER
        g = groups.setdefault(order, {"taxa": 0, "key": 0, "fam": {}})
        g["taxa"] += 1
        g["key"] += tvk in key_tvks
        fam = (getattr(sp, "family", "") or "").strip()
        g["fam"][fam] = g["fam"].get(fam, 0) + 1
        if is_saproxylic is not None and is_saproxylic(sp):
            sap_taxa += 1
            sap_key += tvk in key_tvks

    out.rows = [TaxRow(o, _families_text(g["fam"]), g["taxa"], g["key"])
                for o, g in sorted(groups.items(),
                                   key=lambda kv: (kv[0] == NO_ORDER, -kv[1]["taxa"], kv[0]))]
    if sap_taxa:
        out.saproxylic = TaxRow(SAPROXYLIC_LABEL, "", sap_taxa, sap_key)
    out.total = TaxRow(TOTAL_LABEL, f"{len(groups)} group{'s' if len(groups) != 1 else ''}",
                       len(seen), sum(g["key"] for g in groups.values()))
    return out


def for_result(result, detail) -> Optional[TaxSummary]:
    """The summary for an analysis, or None when there is no species list (imported list)."""
    species = getattr(detail, "species_list", None)
    if not species:
        return None
    return taxonomic_summary(species, {k.tvk for k in getattr(result, "key_species", []) if k.tvk})
