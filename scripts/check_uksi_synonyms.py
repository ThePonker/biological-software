"""F14 / fault F25: does uksi.synonyms send old names to the wrong species?  READ ONLY.

The live uksi.db (since 6 Oct 2026) was built by build_uksi_from_release.py:
synonyms = the July 2025 NAMES sheet's Latin S/U names  PLUS  every synonym and old
taxon name carried over from the 2023 file, remapped to current. Errors in the old
table were inherited, so one name can now point at two TVKs.

uksi.db keeps the NAMES mapping in `name_map` (every name TVK -> recommended TVK),
so each synonyms row can be classed without the spreadsheet:

  NAMES      the July NAMES sheet gives this name -> this taxon
  CONFLICT   the NAMES sheet knows the name but sends it to a DIFFERENT current
             taxon: the carried row disagrees with the authority
  CARRIED    the NAMES sheet does not have the name at all; only the old file says so

then, per the handover (claude/27_UKSI_Synonyms_Handover.md, section 3):
  1. epithet mismatch: the synonym's epithet differs from its target's AND another
     current species in the target's family has that epithet (Lamia sartor ->
     L. textor while Monochamus sartor exists)
  2. names that map to more than one TVK
  3. origin of every flagged row
  4. exposure: codex.tvk_bridge rows matched through a flagged name; records and
     specimens stored under a flagged name
  5. the Lamia / Cerambyx textor example

Writes every flagged row to scripts\\_oneoff\\f14_flagged.csv.
  py -3.14 scripts\\check_uksi_synonyms.py
"""
import csv
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths  # noqa: E402

OUT = os.path.join(ROOT, "scripts", "_oneoff", "f14_flagged.csv")
SPLEVEL = {"species", "species pro parte", "species aggregate", "species sensu lato",
           "species sensu stricto", "species hybrid", "microspecies", "subspecies"}
ENDINGS = sorted(["us", "a", "um", "is", "e", "er", "ra", "rum", "ae", "i", "os", "on"],
                 key=len, reverse=True)


def ro(p):
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)


def epithet(name):
    """Species epithet of a Latin name, or '' (skips subgenus brackets and markers)."""
    toks = [t for t in (name or "").split() if not t.startswith("(") and not t.endswith(")")]
    if len(toks) < 2 or not toks[1][:1].islower() or not toks[1].isalpha():
        return ""
    return toks[1].lower()


def stem(e):
    for end in ENDINGS:
        if e.endswith(end) and len(e) - len(end) >= 3:
            return e[: -len(end)]
    return e


def main():
    u = ro(paths.UKSI_DB)
    tables = {n for (n,) in u.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    need = {"synonyms", "taxa", "name_map"}
    if not need <= tables:
        print(f"  x uksi.db lacks {sorted(need - tables)} -- is this the July 2025 build?")
        return 1
    tcols = {r[1] for r in u.execute("PRAGMA table_info(taxa)")}

    print("UKSI synonyms -- wrong targets?   READ ONLY")
    print("=" * 96)
    rank_x = "LOWER(COALESCE(rank,''))" if "rank" in tcols else "''"
    fam_x = "COALESCE(family,'')" if "family" in tcols else "''"
    taxa = {}
    for row in u.execute(f"SELECT tvk, scientific_name, {rank_x}, {fam_x} FROM taxa"):
        taxa[row[0]] = row[1:]
    remap = dict(u.execute("SELECT old_tvk, new_tvk FROM tvk_remap WHERE new_tvk IS NOT NULL")) \
        if "tvk_remap" in tables else {}
    nm_rec = dict(u.execute("SELECT tvk, recommended_tvk FROM name_map"))

    def to_current(t, depth=0):
        if t in taxa:
            return t
        if t in remap:
            return remap[t] if remap[t] in taxa else None
        if depth < 5 and nm_rec.get(t) and nm_rec[t] != t:
            return to_current(nm_rec[t], depth + 1)
        return None

    names_targets = defaultdict(set)          # lower(name) -> current TVKs the NAMES sheet gives
    for name, rec in u.execute("SELECT name, recommended_tvk FROM name_map WHERE COALESCE(name,'')!=''"):
        c = to_current(rec)
        if c:
            names_targets[name.lower()].add(c)

    by_fam_stem = defaultdict(set)            # (family, epithet stem) -> current species TVKs
    for t, (sci, rank, fam) in taxa.items():
        e = epithet(sci)
        if e and rank in SPLEVEL and fam:
            by_fam_stem[(fam, stem(e))].add(t)

    syn = list(u.execute("SELECT synonym, tvk FROM synonyms"))
    print(f"  synonyms rows: {len(syn):,}   current taxa: {len(taxa):,}   name_map names: {len(names_targets):,}")
    if "family" not in tcols:
        print("  ! taxa has no family column -- the epithet check cannot run")

    rows, origin = [], Counter()
    soft = Counter()   # CARRIED rows whose epithet differs, with no same-epithet species to point at
    targets_by_name = defaultdict(set)
    for name, tvk in syn:
        targets_by_name[name.lower()].add(tvk)
    for name, tvk in syn:
        nt = names_targets.get(name.lower())
        kind = "NAMES" if nt and tvk in nt else ("CONFLICT" if nt else "CARRIED")
        origin[kind] += 1
        tgt = taxa.get(tvk)
        ep, tep = epithet(name), epithet(tgt[0]) if tgt else ""
        other = set()
        if ep and tep and stem(ep) != stem(tep) and tgt and tgt[2]:
            other = by_fam_stem.get((tgt[2], stem(ep)), set()) - {tvk}
        multi = len(targets_by_name[name.lower()]) > 1
        differs = bool(ep and tep and stem(ep) != stem(tep))
        if kind == "CARRIED" and differs and not other:
            soft[name.split()[0]] += 1
            rows.append({"synonym": name, "tvk": tvk, "target": tgt[0] if tgt else "",
                         "family": tgt[2] if tgt else "", "origin": kind, "epithet_suspect": "differs only",
                         "same_epithet_species": "", "names_sheet_says": "", "other_targets": ""})
            continue
        if kind == "CONFLICT" or other or (multi and kind != "NAMES"):
            rows.append({
                "synonym": name, "tvk": tvk, "target": tgt[0] if tgt else "(not a current taxon)",
                "family": tgt[2] if tgt else "", "origin": kind,
                "epithet_suspect": "yes" if other else "",
                "same_epithet_species": "; ".join(sorted(taxa[o][0] for o in other))[:120],
                "names_sheet_says": "; ".join(sorted(taxa[c][0] for c in (nt or ()) if c in taxa))[:120],
                "other_targets": "; ".join(sorted(taxa[x][0] for x in targets_by_name[name.lower()] - {tvk}
                                                  if x in taxa))[:120],
            })

    print("\n1. Origin of every synonyms row")
    for k in ("NAMES", "CONFLICT", "CARRIED"):
        print(f"     {k:9} {origin[k]:>8,}")
    multi_names = {n for n, ts in targets_by_name.items() if len(ts) > 1}
    print(f"\n2. Names mapped to more than one TVK: {len(multi_names):,}")
    print(f"\n   Weaker signal -- CARRIED rows whose epithet differs from the target's, with no")
    print(f"   same-epithet species in the family to point at (Lamia titillator): {sum(soft.values()):,}")
    print(f"   in {len(soft):,} genera; most frequent: {soft.most_common(8)}")
    print("   Genuine synonyms can differ in epithet (Ranunculus ficaria -> Ficaria verna); these are")
    print("   in the CSV as 'differs only' for reading, not counted below.")
    rows_soft = [r for r in rows if r["epithet_suspect"] == "differs only"]
    rows = [r for r in rows if r["epithet_suspect"] != "differs only"]
    flagged = Counter((r["origin"], r["epithet_suspect"] == "yes") for r in rows)
    print("\n3. Flagged rows (CONFLICT, epithet-suspect, or a non-NAMES row of a multi-target name)")
    print(f"     {'origin':9} {'epithet-suspect':>16} {'other':>8}")
    for k in ("NAMES", "CONFLICT", "CARRIED"):
        print(f"     {k:9} {flagged[(k, True)]:>16,} {flagged[(k, False)]:>8,}")
    print(f"     total flagged: {len(rows):,}")
    print("\n   Examples -- CONFLICT and epithet-suspect first:")
    rows.sort(key=lambda r: (r["origin"] != "CONFLICT", r["epithet_suspect"] != "yes", r["family"], r["synonym"]))
    for r in rows[:30]:
        print(f"     {r['origin']:8} {r['synonym'][:30]:30} -> {r['target'][:28]:28}"
              + (f"  NAMES: {r['names_sheet_says'][:30]}" if r["names_sheet_says"] else "")
              + (f"  same epithet: {r['same_epithet_species'][:30]}" if r["same_epithet_species"] else ""))

    # 4. exposure
    bad = {(r["synonym"].lower(), r["tvk"]) for r in rows if r["origin"] == "CONFLICT" or r["epithet_suspect"]}
    bad_names = {n for n, _ in bad}
    print(f"\n4. Exposure of the {len(bad):,} CONFLICT / epithet-suspect rows")
    try:
        c = ro(paths.CODEX_DB)
        bcols = {r[1] for r in c.execute("PRAGMA table_info(tvk_bridge)")}
        methods = Counter(m for (m,) in c.execute("SELECT match_method FROM tvk_bridge"))
        print(f"     tvk_bridge match methods: {dict(methods)}")
        hit = Counter()
        examples = []
        pan = {}
        try:   # Pantheon's own name for each of its TVKs -- the name the bridge matched on
            pan = dict(ro(paths.PANTHEON_DB).execute("SELECT tvk, species_name FROM species"))
        except sqlite3.Error:
            pass
        if {"uksi_tvk", "match_method", "pantheon_tvk"} <= bcols:
            name_x = "species_name" if "species_name" in bcols else "''"
            for bn, ut, mm, pt in c.execute(f"SELECT {name_x}, uksi_tvk, match_method, pantheon_tvk FROM tvk_bridge"):
                for nm in {pan.get(pt) or "", bn or ""}:
                    if nm.lower() in bad_names and (nm.lower(), ut) in bad:
                        hit[mm] += 1
                        examples.append((nm, pt, ut, mm))
                        break
        print(f"     bridge rows that used a flagged name -> its flagged target: {sum(hit.values())} {dict(hit)}")
        for nm, pt, ut, mm in examples[:15]:
            print(f"       {nm[:30]:30} {pt} -> {taxa.get(ut, ('?',))[0][:30]} [{mm}]")
        c.close()
    except sqlite3.Error as e:
        print(f"     ! codex.db not readable: {e}")
    try:
        o = ro(paths.OBSERVATUM_DB)
        for tbl in ("observations", "specimens", "contributed_observations"):
            try:
                n = sum(1 for nm, t in o.execute(f"SELECT species_name, species_tvk FROM {tbl}")
                        if (nm or "").lower() in bad_names and ((nm or "").lower(), t) in bad)
            except sqlite3.Error:
                continue
            print(f"     {tbl}: records stored under a flagged name with its flagged TVK: {n}")
        o.close()
    except sqlite3.Error as e:
        print(f"     ! observatum.db not readable: {e}")
    print("     (remap_record_tvks.py maps through name_map / tvk_remap, not synonyms, so the")
    print("      6 Oct remap could not have used a flagged synonym.)")

    # 5. the example
    print("\n5. The Lamia example")
    for name, tvk in u.execute("SELECT synonym, tvk FROM synonyms WHERE synonym LIKE 'Lamia %' "
                               "OR synonym LIKE 'Cerambyx textor%' OR synonym LIKE 'Monochamus %' ORDER BY synonym"):
        nt = names_targets.get(name.lower())
        kind = "NAMES" if nt and tvk in nt else ("CONFLICT" if nt else "CARRIED")
        print(f"     {name:28} -> {taxa.get(tvk, ('?',))[0]:24} {kind}")
    for probe in ("Cerambyx textor", "Lamia sartor", "Lamia sutor"):
        nt = names_targets.get(probe.lower())
        print(f"     NAMES sheet has '{probe}': {'yes -> ' + ', '.join(taxa[x][0] for x in nt) if nt else 'no'}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        allrows = rows + rows_soft
        w = csv.DictWriter(f, fieldnames=list(allrows[0]) if allrows else ["synonym"])
        w.writeheader()
        w.writerows(allrows)
    print(f"\n  every flagged row: {OUT}")
    print("READ ONLY -- nothing in the databases has been changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
