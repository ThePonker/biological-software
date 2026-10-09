"""What an import wizard stores for a species match -- the same for all three (fix round,
9 Oct 2026, items 13-15). species_lookup.py decides WHICH taxon a name matches; entry() turns
its answer into the columns, warning and import note each validation worker files:

  species_name   the UKSI scientific name of the matched TVK (IMP-15); the name as typed
                 goes into the import notes ("Imported as '...'") when it differs
  warning        synonym / cf. / aggregate / "no aggregate in UKSI -- matched to species"
  error          not found or ambiguous: the closest UKSI names are named, and the row stays
                 an error until the user confirms one (Resolve Species / Match Report)
"""
from __future__ import annotations

from typing import Dict

from .species_lookup import (AMBIGUOUS, FAILED, NOT_FOUND, LookupFailure, Result,
                             is_species_error)


def failure_text(r: LookupFailure, shown: int = 3) -> str:
    """The row error for a name not matched. Starts with NOT_FOUND / AMBIGUOUS / FAILED."""
    if r.kind == "error":
        return (f"{FAILED} for {r.name} ({r.message}) — the name may well be in UKSI; "
                f"re-run validation")
    names = []
    for t in r.candidates:
        label = t.scientific_name or ""
        if t.rank and t.rank != "Species":
            label += f" [{t.rank}]"
        elif t.qualifier:
            label += f" [{t.qualifier}]"
        if label not in names:
            names.append(label)
    head = f"{AMBIGUOUS}: {r.name}" if r.kind == "ambiguous" else f"{NOT_FOUND}: {r.name}"
    if names:
        more = f" (+{len(names) - shown} more)" if len(names) > shown else ""
        head += f" — {'choose from' if r.kind == 'ambiguous' else 'closest'}: " \
                f"{', '.join(names[:shown])}{more}"
    return head + " — confirm with Resolve Species"


def entry(r: Result) -> dict:
    """What a wizard stores for one name.

    Matched: {tvk, species_name (the UKSI scientific name of the TVK), common_name, order_name,
    family, kingdom, phylum, class_name, genus, rank, warning, import_notes}.
    Not matched: {error, kind, candidates}."""
    if isinstance(r, LookupFailure):
        return {"error": failure_text(r), "kind": r.kind,
                "candidates": [c.as_dict() for c in r.candidates]}
    t = r.taxon
    return {"tvk": t.tvk or "", "species_name": t.scientific_name or r.looked_up,
            "common_name": t.common_name or "", "order_name": t.order_name or "",
            "family": t.family or "", "kingdom": t.kingdom or "", "phylum": t.phylum or "",
            "class_name": t.class_name or "", "genus": t.genus or "", "rank": t.rank or "",
            "warning": "; ".join(r.warnings), "import_notes": "; ".join(r.notes)}


def entries(results: Dict[str, Result]) -> Dict[str, dict]:
    return {n: entry(r) for n, r in results.items()}


def resolution_entry(uksi_data: dict, original: str) -> dict:
    """A choice the user confirmed (Resolve Species / Match Report) as an entry()."""
    name = uksi_data.get("scientific_name", "") or original
    return {"tvk": uksi_data.get("tvk", "") or "", "species_name": name,
            "common_name": uksi_data.get("common_name", "") or "",
            "order_name": uksi_data.get("order_name", "") or "",
            "family": uksi_data.get("family", "") or "",
            "kingdom": uksi_data.get("kingdom", "") or "", "rank": uksi_data.get("rank", "") or "",
            "warning": f"Species confirmed by you: '{name}'",
            "import_notes": f"Imported as '{original}'; confirmed by you as '{name}'"}


def apply_confirmed(row, uksi_data: dict, original: str, how: str = "confirmed by you") -> None:
    """Put a species the user confirmed onto an import row (any of the three wizards' row
    classes): the UKSI name and taxonomy, the import note, and a warning. Only the species
    error is removed -- any other error (a bad date, a bad grid ref) stays, so the row stays
    an error (IMP-5)."""
    e = resolution_entry(uksi_data, original)
    e["import_notes"] = e["import_notes"].replace("confirmed by you", how)
    row.species_name = e["species_name"]
    row.species_tvk = e["tvk"]
    for attr in ("common_name", "order_name", "family", "kingdom"):
        if hasattr(row, attr):
            setattr(row, attr, e[attr])
    if hasattr(row, "subfamily"):
        row.subfamily = uksi_data.get("subfamily", "") or ""
    if hasattr(row, "taxon_rank"):
        row.taxon_rank = e["rank"]
    row.import_notes = e["import_notes"]

    status = type(row.status)
    was_error = row.status == status.ERROR
    errors = ([x for x in (row.error_message or "").split("; ") if x and not is_species_error(x)]
              if was_error else [])
    warnings = [w for w in (getattr(row, "warnings", None) or [])
                if w and not is_species_error(w) and not w.startswith("Missing TVK")]
    warnings.append(e["warning"])
    row.warnings = warnings
    if errors:
        row.status = status.ERROR
        row.error_message = "; ".join(errors)
    else:
        row.status = status.WARNING
        row.error_message = "; ".join(warnings)


__all__ = ["entry", "entries", "failure_text", "resolution_entry", "apply_confirmed"]
