"""Build shared/checklists/*.csv from the published checklists. READ ONLY on the databases.

shared/checklist_order.py re-sorts specimens within a family into checklist order, matching
on the record's UKSI family, genus and binomial. This script reads each published list
(scripts/checklist_parsers.py), keeps its sequence, and RESOLVES every listed name to the
current UKSI name so the rows carry the names and FAMILY that Wil's records carry:

  1. exact       the listed binomial is a current UKSI species in that order (a UKSI
                 subgenus in brackets is ignored: "Psallus (Psallus) anaemicus")
  2. synonym     uksi.synonyms / name_map send the listed name to one current species
                 (if to several, the one that keeps the epithet, when only one does)
  3. subgenus    the listed subgenus is now a genus: "Subgenus epithet" is a current species
  4. moved       same epithet (or its other gender ending) under a current genus that UKSI
                 lists the checklist genus as a synonym of -- only if exactly one fits
  5. spelling    one current species of that genus within one letter or a gender ending
                 (heerii / heeri), or the same epithet under a genus one letter off (two
                 within the family: Steadota / Steatoda)
  6. genus differs  the list is newer than UKSI: the only species in that family with the
                 epithet, in a UKSI genus the list itself never uses
  7. unresolved  left as listed (reported); ambiguous candidates are reported, not guessed
Every step after 1 is written in the row's `note`, so each can be checked.

Output (UTF-8, header family,genus,species,name_as_listed,source,note):
  10_coleoptera.csv  20_diptera.csv  30_hymenoptera_aculeata.csv  40_hemiptera.csv
  50_lepidoptera.csv  60_araneae.csv

The lists are copyright ("all rights reserved"): the CSVs and the PDFs stay on this PC
(shared/checklists/*.csv is git-ignored; the PDFs live in data\\checklists\\, under data/).

  py -3.14 scripts\\build_checklists.py                 dry run: counts per file
  py -3.14 scripts\\build_checklists.py --write         writes the CSVs
      --sources DIR   where the PDFs / pasted pages are (default data\\checklists)
      --out DIR       where the CSVs go (default shared\\checklists)
      --only coleoptera,diptera   build just these
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths  # noqa: E402
from scripts import checklist_parsers as P  # noqa: E402

DEFAULT_SOURCES = os.path.join(str(paths.DATA_DIR), "checklists")
DEFAULT_OUT = os.path.join(ROOT, "shared", "checklists")
FIELDS = ["family", "genus", "species", "name_as_listed", "source", "note"]

# key: (output file, UKSI order, [(source label, file, how to read it)])
LISTS = {
    "coleoptera": ("10_coleoptera.csv", "Coleoptera",
                   [("Duff 2008", "duff2008.pdf", "duff")]),
    "diptera": ("20_diptera.csv", "Diptera",
                [("Dipterists Forum 2025", "diptera2025.pdf", "diptera")]),
    "hymenoptera": ("30_hymenoptera_aculeata.csv", "Hymenoptera",
                    [("Else, Bolton & Broad 2016", "bdj_e8050.pdf", "aculeates")]),
    "hemiptera": ("40_hemiptera.csv", "Hemiptera",
                  [("britishbugs Heteroptera", "heteroptera_britishbugs.txt", "heteroptera"),
                   ("britishbugs Auchenorrhyncha", "auchenorrhyncha_britishbugs.txt",
                    "auchenorrhyncha")]),
    "lepidoptera": ("50_lepidoptera.csv", "Lepidoptera",
                    [("Agassiz et al. 2024", "lepidoptera2024.pdf", "lepidoptera")]),
    "araneae": ("60_araneae.csv", "Araneae",
                [("Merrett & Murphy 2000", "spiders2000.pdf", "spiders")]),
}


def read_source(path: str, how: str) -> List[dict]:
    if how == "duff":
        return P.parse_duff(P.pdf_lines(path, columns=2, min_size=8.5))
    if how == "diptera":
        return P.parse_diptera(P.pdf_lines(path))
    if how == "aculeates":
        return P.parse_aculeates(P.pdf_lines(path, x_tolerance=1.5))
    if how == "lepidoptera":
        return P.parse_lepidoptera(P.pdf_lines(path, min_size=7))
    if how == "spiders":
        return P.parse_spiders(P.pdf_lines(path, columns=2))
    with open(path, encoding="utf-8-sig") as f:
        src = f.read()
    if how == "heteroptera":
        return P.parse_heteroptera_text(src)
    return P.parse_auchenorrhyncha_text(src)


# ---------------------------------------------------------------- resolving to UKSI

SPECIES_RANKS = ("Species", "Species aggregate", "Species sensu lato", "Species group",
                 "Species pro parte", "Microspecies")
BELOW = ("Subspecies", "Variety", "Form", "Abberation", "Aberration")
ENDING_SWAPS = [("us", "a"), ("us", "um"), ("a", "um"), ("is", "e"), ("er", "ra"),
                ("er", "rum"), ("ra", "rum"), ("ii", "i")]


def _key(s: str) -> str:
    return " ".join((s or "").split()).lower()


def _drop_subgenus(name: str) -> str:
    return " ".join(w for w in (name or "").split() if not w.startswith("("))


def gender_variants(epithet: str) -> List[str]:
    out = []
    for a, b in ENDING_SWAPS:
        for x, y in ((a, b), (b, a)):
            if epithet.endswith(x) and len(epithet) > len(x) + 2:
                out.append(epithet[: -len(x)] + y)
    return [v for v in dict.fromkeys(out) if v != epithet]


def _edits(a: str, b: str) -> int:
    """Edit distance (letters added, dropped, changed or two swapped); 3 if clearly more."""
    if abs(len(a) - len(b)) > 2:
        return 3
    d = [[i + j if i * j == 0 else 0 for j in range(len(b) + 1)] for i in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1,
                          d[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)     # swapped letters: Steadota
    return d[-1][-1]


def _close(listed: str, other: str) -> bool:
    """Same epithet bar a gender ending or one letter (heerii / heeri, pastinaceae /
    pastinacae). Only ever used when exactly one current name is that close."""
    return other != listed and (other in gender_variants(listed) or _edits(listed, other) == 1)


def _close_epithet(listed_epithet: str, name: str) -> bool:
    w = _drop_subgenus(name).lower().split()
    return len(w) >= 2 and (w[1] == listed_epithet.lower() or _close(listed_epithet.lower(), w[1]))


class Resolver:
    """Listed (genus, epithet, subgenus) -> current UKSI species within one order."""

    def __init__(self, conn: sqlite3.Connection, order: str):
        self.order = order
        self.taxa: Dict[str, Tuple] = {}             # tvk -> (name, rank, family, parent)
        self.species: Dict[str, str] = {}            # lower name -> tvk (species ranks)
        self.genera: Dict[str, Tuple[str, str]] = {}  # lower genus -> (Name, family)
        for tvk, name, rank, fam, parent in conn.execute(
                'SELECT tvk, scientific_name, rank, family, parent_tvk FROM taxa '
                'WHERE "order" = ?', (order,)):
            self.taxa[tvk] = (name, rank, fam or "", parent)
            if rank in SPECIES_RANKS:
                k = _key(_drop_subgenus(name))     # "Eurydema (Eurydema) dominulus"
                if k not in self.species or rank == "Species":
                    self.species[k] = tvk
            elif rank == "Genus":
                self.genera[_key(name)] = (name, fam or "")
        self.by_genus: Dict[str, list] = defaultdict(list)    # genus -> [(epithet, tvk)]
        self.by_epithet: Dict[str, list] = defaultdict(list)  # epithet -> [(genus, tvk)]
        for k, tvk in self.species.items():
            w = k.split()
            if len(w) == 2:
                self.by_genus[w[0]].append((w[1], tvk))
                self.by_epithet[w[1]].append((w[0], tvk))
        self.syn: Dict[str, set] = defaultdict(set)   # lower name -> {current tvk}
        rows = list(conn.execute("SELECT synonym, tvk FROM synonyms"))
        rows += list(conn.execute(
            "SELECT name, recommended_tvk FROM name_map WHERE name_status <> 'R'"))
        for name, tvk in rows:
            if tvk in self.taxa:
                for k in {_key(name), _key(_drop_subgenus(name))}:
                    self.syn[k].add(tvk)
        # genus synonyms: old genus (or "Old (Sub)") -> current genera
        self.genus_syn: Dict[str, set] = defaultdict(set)
        for k, tvks in self.syn.items():
            for t in tvks:
                if self.taxa[t][1] == "Genus":
                    self.genus_syn[k].add(_key(self.taxa[t][0]))

    def _species_tvk(self, tvk: str) -> Optional[str]:
        """The species a TVK stands for (a subspecies rolls up to its species)."""
        seen = 0
        while tvk in self.taxa and seen < 3:
            name, rank, _, parent = self.taxa[tvk]
            if rank in SPECIES_RANKS:
                return tvk
            if rank not in BELOW:
                return None
            tvk, seen = parent, seen + 1
        return None

    def _listed_genera(self, listed: frozenset) -> set:
        if getattr(self, "_lg_key", None) is not listed:
            self._lg_key, self._lg = listed, {k.split()[0] for k in listed if k}
        return self._lg

    def name(self, tvk: str) -> Tuple[str, str]:
        name, _, fam, _ = self.taxa[tvk]
        return name, fam

    def resolve(self, genus: str, epithet: str, subgenus: str = "", family: str = "",
                checklist_names: frozenset = frozenset()) -> Tuple[Optional[str], str]:
        """(tvk or None, how). `checklist_names`: every name the list gives (lower case),
        so step 6 only moves a name into a UKSI genus the list itself never uses."""
        listed = _key(f"{genus} {epithet}")
        if listed in self.species:
            return self.species[listed], "exact"
        cands = {self._species_tvk(t) for t in self.syn.get(listed, ())} - {None}
        names = {_key(_drop_subgenus(self.name(t)[0])) for t in cands}
        if len(cands) > 1 and len(names) == 1 and names <= set(self.species):
            cands = {self.species[names.pop()]}     # one name held on two TVKs (species, agg.)
        if len(cands) == 1:
            return cands.pop(), "synonym"
        if len(cands) > 1:
            same = {t for t in cands if _close_epithet(epithet, self.name(t)[0])}
            if len(same) == 1:
                return same.pop(), "synonym (one of %d targets keeps the epithet)" % len(cands)
            return None, "ambiguous synonym: " + "; ".join(sorted(self.name(t)[0] for t in cands))
        if subgenus:
            k = _key(f"{subgenus} {epithet}")
            if k in self.species:
                return self.species[k], "subgenus now genus"
        gens = set(self.genus_syn.get(_key(genus), ()))
        if subgenus:
            gens |= self.genus_syn.get(_key(f"{genus} ({subgenus})"), set())
        gens.discard(_key(genus))
        hits = set()
        for g in gens:
            for ep in [epithet] + gender_variants(epithet):
                t = self.species.get(f"{g} {ep.lower()}")
                if t:
                    hits.add(t)
        if len(hits) == 1:
            return hits.pop(), "genus moved"
        if len(hits) > 1:
            return None, "ambiguous genus move: " + "; ".join(sorted(self.name(t)[0] for t in hits))
        g, e = _key(genus), epithet.lower()
        hits = {t for k, t in self.by_genus.get(g, ()) if _close(e, k)}
        if len(hits) == 1:
            return hits.pop(), "spelling"
        fam = _key(family)
        hits = {t for gg, t in self.by_epithet.get(e, ())
                if _edits(g, gg) == 1 or (_edits(g, gg) == 2 and _key(self.taxa[t][2]) == fam)}
        if len(hits) == 1:
            return hits.pop(), "spelling (genus)"
        # 6. the list is newer than UKSI: same epithet, and only one species in the family
        #    has it (Cleigastra armillata -> Nanna armillata),
        #    and whose UKSI genus the list never uses (so it is not a different species the
        #    list simply lacks -- Abax parallelus is not Ophonus parallelus)
        genera = self._listed_genera(checklist_names)
        hits = {t for gg, t in self.by_epithet.get(e, ())
                if _key(self.taxa[t][2]) == fam and gg not in genera}
        if len(hits) == 1 and len([1 for gg, t in self.by_epithet.get(e, ())
                                   if _key(self.taxa[t][2]) == fam]) == 1:
            return hits.pop(), "genus differs (only one '%s' in the family)" % e
        return None, "unresolved"


def resolve_rows(rows: List[dict], resolver: Resolver, source: str) -> Tuple[List[dict], Counter]:
    """CSV rows in list order, one per current species (first listing wins)."""
    out, seen, stats = [], set(), Counter()
    listed = frozenset(_key(r["listed"]) for r in rows)
    for r in rows:
        tvk, how = resolver.resolve(r["genus"], r["epithet"], r.get("subgenus", ""),
                                    r["family"], listed)
        stats[re.split(r" \(|:", how)[0]] += 1
        if tvk:
            name, fam = resolver.name(tvk)
            name = _drop_subgenus(name)
            note = "" if how == "exact" else how
        else:
            name = r["listed"]
            g = resolver.genera.get(_key(r["genus"]))
            fam = g[1] if g else r["family"]
            note = how
        k = _key(name)
        if k in seen:
            stats["duplicate"] += 1
            continue
        seen.add(k)
        out.append({"family": fam, "genus": name.split()[0], "species": name,
                    "name_as_listed": r["listed"], "source": source, "note": note})
    return out, stats


def build(keys, sources: str, uksi_path: str) -> Dict[str, Tuple[List[dict], Counter]]:
    conn = sqlite3.connect(f"file:{uksi_path}?mode=ro", uri=True)
    result = {}
    try:
        for key in keys:
            fname, order, srcs = LISTS[key]
            resolver = Resolver(conn, order)
            rows, stats = [], Counter()
            for label, src, how in srcs:
                path = os.path.join(sources, src)
                if not os.path.exists(path):
                    stats["missing source: " + src] += 1
                    continue
                parsed = read_source(path, how)
                stats["parsed " + label] += len(parsed)
                got, st = resolve_rows(parsed, resolver, label)
                done = {_key(x["species"]) for x in rows}
                for g in got:
                    if _key(g["species"]) in done:
                        st["duplicate"] += 1
                    else:
                        rows.append(g)
                stats.update(st)
            result[key] = (rows, stats)
    finally:
        conn.close()
    return result


def write_csv(path: str, rows: List[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sources", default=DEFAULT_SOURCES)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--uksi", default=str(paths.UKSI_DB))
    ap.add_argument("--only", default="")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    keys = [k.strip() for k in a.only.split(",") if k.strip()] or list(LISTS)
    if not os.path.isdir(a.sources):
        print(f"No sources folder: {a.sources}\nPut the lists there ("
              + ", ".join(src for k in keys for _, src, _ in LISTS[k][2])
              + ") or pass --sources FOLDER. Nothing has been written.")
        return 1
    result = build(keys, a.sources, a.uksi)
    for key in keys:
        rows, stats = result[key]
        fname = LISTS[key][0]
        fams = len({r["family"] for r in rows})
        print(f"{fname:30} {len(rows):6} rows  {fams:4} families   "
              + ", ".join(f"{k} {v}" for k, v in sorted(stats.items())))
        if a.write and rows:
            write_csv(os.path.join(a.out, fname), rows)
    print("Written to " + a.out if a.write else "Dry run -- nothing has been written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
