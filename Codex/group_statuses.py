"""The species under a genus, family, order... that hold a Codex status.

Codex Manager > Species Search said "No conservation status recorded for this species"
for a genus or family (Wil 10 Oct 2026). A taxon above species rank now lists its member
species -- UKSI's taxa below it (taxa.parent_tvk, through subgenera, tribes,
subfamilies) -- that hold any status, each summarised, statuses read with
CodexRepository.get_statuses_batch (the species view's own path, s.l. fallback
included). Read-only: uksi.db through the shared species index, codex.db through the
repository.
"""
from typing import Dict, List, Optional

from shared.repositories.codex_repository import _priority_label
from shared.species_search import get_index, rank_group

# Track order for the one-line summary (the species view's card order)
_SINGLE = ("threat_iucn_2001", "threat_iucn_2001_breeding", "threat_iucn_2001_nonbreeding",
           "threat_iucn_legacy", "threat_global_iucn", "rarity_modern", "rarity_legacy",
           "bocc", "specialist_panel", "red_list_england", "red_list_wales")
_LABEL = {"threat_global_iucn": "Global ", "bocc": "BoCC ", "red_list_england": "England ",
          "red_list_wales": "Wales "}


def is_group(tvk: str, uksi_path: Optional[str] = None) -> bool:
    """True for a genus, family, order or higher taxon (not a species or below)."""
    idx = get_index(uksi_path)
    i = idx.pos.get(tvk)
    return i is not None and rank_group(idx.rank[i]) >= 2


def _children(idx) -> Dict[str, List[int]]:
    kids = getattr(idx, "_children_map", None)
    if kids is None:
        kids = {}
        for i, p in enumerate(idx.parent):
            if p:
                kids.setdefault(p, []).append(i)
        idx._children_map = kids          # built once per index (it is read-only)
    return kids


def member_taxa(tvk: str, uksi_path: Optional[str] = None) -> List[tuple]:
    """(tvk, scientific name, rank) of every species and infraspecific taxon under tvk."""
    idx = get_index(uksi_path)
    kids = _children(idx)
    out, stack, seen = [], [tvk], {tvk}
    while stack:
        for i in kids.get(stack.pop(), ()):
            t = idx.tvk[i]
            if t in seen:
                continue
            seen.add(t)
            stack.append(t)
            if rank_group(idx.rank[i]) in (0, 1):
                out.append((t, idx.label[i] or idx.sci[i], idx.rank[i]))
    return out


def status_codes(status) -> List[str]:
    """A SpeciesStatus as short codes in the species view's track order."""
    codes = []
    for track in _SINGLE:
        entry = getattr(status, track, None)
        if entry is not None and entry.value:
            codes.append(_LABEL.get(track, "") + entry.value)
    for entry in status.priority:
        codes.append(_priority_label(entry.value))
    if status.legal_protection:
        codes.append(f"Legal ({len(status.legal_protection)})")
    return list(dict.fromkeys(codes))


def species_with_status(tvk: str, repo, uksi_path: Optional[str] = None) -> dict:
    """{'members': n species/infraspecific taxa under tvk,
        'rows': [(tvk, name, rank, [codes], note)] for those holding a status, by name}."""
    members = member_taxa(tvk, uksi_path)
    statuses = repo.get_statuses_batch([t for t, _, _ in members]) if members else {}
    rows = []
    for t, name, rank in members:
        st = statuses.get(t)
        codes = status_codes(st) if st is not None else []
        if codes:
            rows.append((t, name, rank, codes, st.status_note))
    rows.sort(key=lambda r: r[1].lower())
    return {"members": len(members), "rows": rows}
