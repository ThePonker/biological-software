"""Fix the synonyms in uksi.db that point at the wrong species (backlog F14, fault F25).

    py -3.14 scripts\\fix_uksi_synonyms.py > scripts\\_oneoff\\uksi_synonyms_dry.txt
        dry run: read-only, lists every change and writes uksi_synonym_changes.csv
    py -3.14 scripts\\fix_uksi_synonyms.py --apply
        backup (data\\_backups\\uksi_pre_synonym_fix_<time>.db), then fix (close the apps first)

Two kinds of wrong row, both left by the 6 Oct build (build_uksi_from_release.py), which kept
every synonym of the old extractor-built file as well as the July 2025 NAMES sheet's:

1. CONFLICT -- a name the NAMES sheet itself maps to taxon X also has a carried-over row
   pointing at a different taxon Y. NAMES wins: the Y row goes. (Measured 8 Oct: 366.)
   The NAMES mapping is read from uksi.db's own name_map table (built from that sheet).
2. Corrections the NAMES sheet gets wrong or lacks, listed in
   scripts\\uksi_synonym_corrections.csv (e.g. Lamia sartor -> Lamia textor removed;
   Cerambyx textor -> Lamia textor added). Add rows there and re-run.

Only the synonyms table changes: taxa, records, Codex and analyses are untouched (the Codex
bridge has gone by NAMES key since 8 Oct). It affects species search and Lector's --synonyms.
build_uksi_from_release.py applies the same two rules, so the next UKSI build comes out right.
"""
import csv
import os
import sqlite3
import sys
import time
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths  # noqa: E402

APPLY = "--apply" in sys.argv
try:                                   # names include Greek letters etc.; keep a redirect to a file working
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass
CORRECTIONS = os.path.join(ROOT, "scripts", "uksi_synonym_corrections.csv")
REPORT = os.path.join(ROOT, "scripts", "_oneoff", "uksi_synonym_changes.csv")
SYN_STATUS = ("S", "U")


def load_corrections(path=CORRECTIONS):
    out = {"exclude": set(), "add": set()}
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                a = (r.get("action") or "").strip().lower()
                if a in out and r.get("synonym") and r.get("tvk"):
                    out[a].add((r["synonym"].strip(), r["tvk"].strip()))
    return out


def plan(conn, corrections):
    """(removals, additions): lists of (synonym, tvk, reason)."""
    current = {t for (t,) in conn.execute("SELECT tvk FROM taxa")}
    remap = dict(conn.execute("SELECT old_tvk, new_tvk FROM tvk_remap WHERE new_tvk IS NOT NULL")) \
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name='tvk_remap'").fetchone() else {}
    nm = {}
    for tvk, rec in conn.execute("SELECT tvk, recommended_tvk FROM name_map"):
        nm[tvk] = rec

    def to_current(t, depth=0):
        if t in current:
            return t
        if t in remap:
            return remap[t] if remap[t] in current else None
        if depth < 5 and t in nm and nm[t] != t:
            return to_current(nm[t], depth + 1)
        return None

    names_target = defaultdict(set)              # what the NAMES sheet says each old name is
    for name, rec, status in conn.execute("SELECT name, recommended_tvk, name_status FROM name_map"):
        if name and (status or "").upper() in SYN_STATUS:
            ct = to_current(rec)
            if ct:
                names_target[name.strip().lower()].add(ct)

    rows = list(conn.execute("SELECT synonym, tvk FROM synonyms"))
    kept_target = defaultdict(set)               # names whose NAMES row is in the table too
    for syn, tvk in rows:
        key = (syn or "").strip().lower()
        if tvk in names_target.get(key, ()):
            kept_target[key].add(tvk)
    removals, seen = [], set()
    for syn, tvk in rows:
        key = (syn or "").strip().lower()
        if (syn, tvk) in corrections["exclude"]:
            removals.append((syn, tvk, "correction list")); seen.add((syn, tvk))
        elif key in kept_target and tvk not in names_target[key]:   # never leave a name with no row
            removals.append((syn, tvk, "conflicts with NAMES -> " + ";".join(sorted(names_target[key]))))
            seen.add((syn, tvk))
    have = set(conn.execute("SELECT synonym, tvk FROM synonyms"))
    additions = [(s, t, "correction list") for s, t in sorted(corrections["add"])
                 if (s, t) not in have and t in current]
    return removals, additions


def main():
    print("UKSI synonyms fix (F14)" + ("" if APPLY else "  --  DRY RUN"))
    print("=" * 84)
    corr = load_corrections()
    c = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
    total = c.execute("SELECT COUNT(*) FROM synonyms").fetchone()[0]
    removals, additions = plan(c, corr)
    names = dict(c.execute("SELECT tvk, scientific_name FROM taxa"))
    c.close()
    by_reason = defaultdict(int)
    for _, _, why in removals:
        by_reason["correction list" if why == "correction list" else "conflicts with NAMES"] += 1
    print(f"synonyms rows now: {total:,}")
    print(f"to remove: {len(removals):,}  {dict(by_reason)}")
    print(f"to add:    {len(additions):,}")
    print("\nExamples (old name -> wrong taxon removed):")
    for syn, tvk, why in removals[:25]:
        print(f"    {syn[:38]:38} -> {names.get(tvk, tvk)[:34]:34} [{why[:60]}]")
    for syn, tvk, _ in additions:
        print(f"    + {syn} -> {names.get(tvk, tvk)}")
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["change", "synonym", "tvk", "taxon", "reason"])
        for s, t, why in removals:
            w.writerow(["remove", s, t, names.get(t, ""), why])
        for s, t, why in additions:
            w.writerow(["add", s, t, names.get(t, ""), why])
    print(f"\nFull list: {REPORT}")
    if not APPLY:
        print("DRY RUN -- nothing changed. Re-run with --apply (apps closed).")
        return
    if not removals and not additions:
        print("Nothing to change.")
        return
    if input(f"\n  Remove {len(removals):,} and add {len(additions):,} synonyms in uksi.db? "
             "Apps closed? Type YES: ").strip() != "YES":
        print("  Stopped -- nothing changed.")
        return
    bdir = os.path.join(str(paths.DATA_DIR), "_backups")
    os.makedirs(bdir, exist_ok=True)
    bpath = os.path.join(bdir, f"uksi_pre_synonym_fix_{time.strftime('%Y%m%d_%H%M%S')}.db")
    src = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
    dst = sqlite3.connect(bpath)
    src.backup(dst)
    dst.close(); src.close()
    print(f"  backup: {bpath}")
    w = sqlite3.connect(str(paths.UKSI_DB))
    with w:
        for s, t, _ in removals:
            w.execute("DELETE FROM synonyms WHERE synonym = ? AND tvk = ?", (s, t))
        w.executemany("INSERT INTO synonyms (synonym, tvk) VALUES (?, ?)", [(s, t) for s, t, _ in additions])
    after = w.execute("SELECT COUNT(*) FROM synonyms").fetchone()[0]
    w.close()
    print(f"\n  Done: synonyms {total:,} -> {after:,}. Run the dry run again: 'to remove' should be 0.")


if __name__ == "__main__":
    main()
