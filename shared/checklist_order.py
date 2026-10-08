"""checklist_order -- checklist (systematic) order within a family. Pure Python, no Qt.

UKSI holds genera alphabetically under each family -- neither the July 2025 release nor the
2023 one carries subfamilies or tribes -- so the UKSI sort key puts Abax before Carabus. A
checklist file supplies the published order instead. reorder() re-sorts specimens within each
family that a checklist covers and leaves everything else exactly as it came (UKSI order).

Checklist files: shared/checklists/*.csv, UTF-8, header row  family,genus,species
(species may be blank), rows in checklist order:
  * a genus row places the genus within its family;
  * a species row places the species within its genus -- and places the genus too, if the
    genus has no row of its own.
Genera or species missing from a checklist keep their UKSI order, after the listed ones.

    specs = checklist_order.reorder(specs)     # specs: dicts with family, genus, species_name
"""
from __future__ import annotations

import csv
import os
from typing import Dict, Iterable, List, Optional, Tuple

DEFAULT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "checklists")


class Checklist:
    def __init__(self):
        self.genus_pos: Dict[Tuple[str, str], int] = {}     # (family, genus) -> position
        self.species_pos: Dict[str, int] = {}               # "genus species" -> position
        self.families: set = set()

    def add(self, family: str, genus: str, species: str = "") -> None:
        fam, gen, sp = _k(family), _k(genus), _k(species)
        if not fam:
            return
        if not gen and sp:
            gen = sp.split()[0]
        if not gen:
            return
        n = len(self.genus_pos) + len(self.species_pos)
        self.families.add(fam)
        self.genus_pos.setdefault((fam, gen), n)
        if sp:
            if " " not in sp:                      # epithet only: "nemoralis" under Carabus
                sp = f"{gen} {sp}"
            self.species_pos.setdefault(_binomial(sp), n)

    def __bool__(self) -> bool:
        return bool(self.families)


def _k(v) -> str:
    return " ".join(str(v or "").split()).lower()


def _binomial(name: str) -> str:
    """Genus + epithet, lower case; drops subgenus in brackets, subspecies and 'agg.'."""
    words = [w for w in _k(name).split() if not w.startswith("(")]
    return " ".join(words[:2])


def load(folder: Optional[str] = None) -> Checklist:
    """Every *.csv in the folder, in file-name order. No folder or no files -> empty."""
    folder = folder or DEFAULT_DIR
    cl = Checklist()
    if not os.path.isdir(folder):
        return cl
    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith(".csv"):
            continue
        with open(os.path.join(folder, name), newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                row = {_k(k): v for k, v in row.items() if k}
                cl.add(row.get("family"), row.get("genus"), row.get("species"))
    return cl


def reorder(specs: Iterable[Dict], checklist: Optional[Checklist] = None) -> List[Dict]:
    """The specimens, re-sorted within each checklisted family; otherwise order kept."""
    specs = list(specs)
    cl = load() if checklist is None else checklist
    if not cl:
        return specs
    fam_rank: Dict[Tuple[str, str], int] = {}
    genus_seen: Dict[Tuple[str, str, str], int] = {}
    keys = []
    for i, s in enumerate(specs):
        order, fam = _k(s.get("order_name")), _k(s.get("family"))
        gen = _k(s.get("genus")) or (_k(s.get("species_name")).split() or [""])[0]
        f = fam_rank.setdefault((order, fam), i)
        if fam not in cl.families:
            keys.append((f, (0, 0), (0, 0), i))
            continue
        g = genus_seen.setdefault((order, fam, gen), i)
        gpos = cl.genus_pos.get((fam, gen))
        spos = cl.species_pos.get(_binomial(s.get("species_name") or ""))
        keys.append((f,
                     (0, gpos) if gpos is not None else (1, g),
                     (0, spos) if spos is not None else (1, i),
                     i))
    return [s for _, s in sorted(zip(keys, specs), key=lambda p: p[0])]
