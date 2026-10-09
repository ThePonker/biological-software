"""Examen -- Saproxylic Quality Index and Index of Ecological Continuity (backlog E7).

Scores come from Examen/reference/saproxylic_scores.csv: Wil's compiled list (khepri.uk,
updated from Alexander's BENHS revision) -- 605 scored species on the Fowles et al. (1999)
scale (1, 2, 4, 8, 16, 24, 32) and IEC points (1-3). Each name is tied to its current UKSI
taxon (`tvk`); links were checked online on 9 Oct 2026 and doubtful ones left out.

    SQI = sum of the scores of the listed species recorded x 100 / number of them
    IEC = sum of the IEC points of the listed species recorded (a minimum: cumulative
          across surveys; post-1950 records only)

Thresholds are in saproxylic_config.json and are shown side by side, not as a verdict:
Fowles (SQI 500 national, 590 international), Alexander (300+ marks a top British site),
IEC >15 regional, >25 national, >80 international. An SQI from fewer than 40 listed
species is flagged.

    from Examen.saproxylic import assess
    r = assess(detail.species_list)          # items with .tvk and .name
    r.sqi, r.iec, r.n_scored, r.rows
"""
from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
LIST_CSV = os.path.join(HERE, "reference", "saproxylic_scores.csv")
CONFIG = os.path.join(HERE, "saproxylic_config.json")

DEFAULT_CONFIG = {
    "min_species": 40,
    "sqi_thresholds": [
        {"source": "Fowles et al. (1999)", "value": 500, "label": "national importance"},
        {"source": "Fowles et al. (1999)", "value": 590, "label": "international importance"},
        {"source": "Alexander", "value": 300, "label": "a top British site"},
    ],
    "iec_thresholds": [
        {"value": 15, "label": "regional importance"},
        {"value": 25, "label": "national importance"},
        {"value": 80, "label": "international importance"},
    ],
    "citation": ("SQI after Fowles, Alexander & Key (1999); IEC after Alexander (2004), "
                 "scores as revised by Alexander (BENHS)."),
}


def _norm(name) -> str:
    return " ".join(str(name or "").replace(" ", " ").split()).casefold()


@dataclass
class Entry:
    species: str
    sqi: Optional[int]
    iec: int
    status: str
    uksi_name: str


@dataclass
class SapResult:
    sqi: Optional[float] = None
    sqs_total: int = 0
    n_scored: int = 0
    iec: int = 0
    n_iec: int = 0
    reliable: bool = False
    rows: List[dict] = field(default_factory=list)          # one per listed species recorded
    sqi_bands: List[dict] = field(default_factory=list)     # [{source, value, label, met}]
    iec_bands: List[dict] = field(default_factory=list)
    min_species: int = 40
    citation: str = ""

    @property
    def summary(self) -> str:
        if not self.n_scored:
            return "No species on the saproxylic list recorded."
        s = f"Saproxylic SQI {self.sqi:g} from {self.n_scored} listed species"
        if not self.reliable:
            s += f" (fewer than {self.min_species}: treat with caution)"
        return s + f"; IEC {self.iec} from {self.n_iec} species."


_cache: Dict[str, object] = {}


def config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def load_list(path: str = LIST_CSV):
    """(by_tvk, by_name, genera): the list keyed for matching. Cached per path."""
    if path in _cache:
        return _cache[path]
    by_tvk: Dict[str, Entry] = {}
    by_name: Dict[str, Entry] = {}
    genera: Dict[str, Entry] = {}
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(line for line in f if not line.startswith("#")))
    # Where the list names one species twice (an old and a current name), the entry under
    # the CURRENT name wins -- it is the later revision (e.g. Hypnogyra angularis over
    # Xantholinus angularis).
    rows.sort(key=lambda r: _norm(r["species"]) in {_norm(n) for n in (r.get("uksi_name") or "").split(";")})
    for r in rows:
        if (r.get("note") or "").startswith(("valid species", "doubtful", "synonymy with",
                                             "ambiguous", "not British")):
            continue                                       # links left out after checking
        e = Entry(r["species"], int(r["sqi_score"]) if r["sqi_score"] else None,
                  int(r["iec_score"] or 0), r.get("status", ""), r.get("uksi_name", ""))
        if len(r["species"].split()) == 1:                 # Melanotus, Leiopus: genus only
            genera[_norm(r["species"])] = e
            continue
        for t in filter(None, (r.get("tvk") or "").split(";")):
            by_tvk[t] = e
        for n in [r["species"]] + (r.get("uksi_name") or "").split(";"):
            if n:
                by_name[_norm(n)] = e
    out = (by_tvk, by_name, genera)
    _cache[path] = out
    return out


def match(tvk: str, name: str, lists=None) -> Optional[Entry]:
    by_tvk, by_name, genera = lists or load_list()
    e = by_tvk.get(tvk or "") or by_name.get(_norm(name))
    if e is None and name:
        if _norm(name) == "globicornis nigripes":          # rufitarsis on the British list
            e = by_name.get("globicornis rufitarsis")
        else:
            e = genera.get(_norm(name).split(" ")[0])     # a Melanotus / Leiopus species
    return e


def assess(species_list, lists=None, cfg: Optional[dict] = None) -> SapResult:
    """SQI and IEC for the species recorded (items with .tvk and .name)."""
    cfg = cfg or config()
    seen: Dict[str, dict] = {}
    for sp in species_list or []:
        e = match(getattr(sp, "tvk", ""), getattr(sp, "name", ""), lists)
        if e is None or e.species in seen:                 # each list entry counted once
            continue
        seen[e.species] = {"species": getattr(sp, "name", "") or e.species, "list_name": e.species,
                           "sqi_score": e.sqi, "iec": e.iec, "status": e.status}
    rows = sorted(seen.values(), key=lambda r: (-(r["sqi_score"] or 0), -r["iec"], r["species"]))
    scored = [r for r in rows if r["sqi_score"]]
    res = SapResult(rows=rows, min_species=cfg["min_species"], citation=cfg["citation"])
    res.n_scored = len(scored)
    res.sqs_total = sum(r["sqi_score"] for r in scored)
    res.sqi = round(res.sqs_total * 100 / res.n_scored, 1) if scored else None
    res.reliable = res.n_scored >= cfg["min_species"]
    res.iec = sum(r["iec"] for r in rows)
    res.n_iec = sum(1 for r in rows if r["iec"])
    res.sqi_bands = [dict(b, met=res.sqi is not None and res.sqi >= b["value"])
                     for b in cfg["sqi_thresholds"]]
    res.iec_bands = [dict(b, met=res.iec > b["value"]) for b in cfg["iec_thresholds"]]
    return res


def band_text(res: SapResult) -> str:
    """'SQI 312: above Alexander's 300 (a top British site); below Fowles' 500 ...'"""
    if res.sqi is None:
        return ""
    parts = []
    for b in sorted(res.sqi_bands, key=lambda b: b["value"]):
        parts.append(f"{'meets' if b['met'] else 'below'} {b['value']} ({b['label']}, {b['source']})")
    iec = [b for b in res.iec_bands if b["met"]]
    iec_txt = (f"IEC above {iec[-1]['value']} ({iec[-1]['label']})" if iec
               else f"IEC below {res.iec_bands[0]['value']}" if res.iec_bands else "")
    return "; ".join(parts) + (f". {iec_txt}." if iec_txt else ".")
