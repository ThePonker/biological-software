"""B1 dry run: where each specimen photo WOULD go in the Life tree. READ ONLY -- moves nothing.

    py -3.14 scripts\\plan_photo_consolidation.py
    py -3.14 scripts\\plan_photo_consolidation.py --check-csv scripts\\_oneoff\\media_library_check_20261013.csv

Works from the library check's CSV (scripts\\check_media_library.py; newest one by default) and
UKSI (read-only). The photos planned: every image under Photos\\Microscope Photos\\, and under
Photos\\Life\\Dead Spiders\\ and Photos\\Life\\Dead Craneflies\\.

Where a photo goes (agreed 13 Oct 2026), always into a 'Specimen' subfolder:
  1. the species already has a folder in Life           -> <that folder>\\Specimen\\
  2. its family has a folder in Life                    -> <family>\\<species>\\Specimen\\
  3. its order has a folder in Life                     -> <order>\\[<level>\\]<family>\\<species>\\Specimen\\
     A level between order and family (Hemiptera's suborder) is taken from the species'
     UKSI ancestors when one of them names a folder already there; otherwise review.
  4. none of these                                     -> Life\\_New species\\<species>\\Specimen\\
Only an exact UKSI match is planned outright. A synonym or fuzzy match gets a proposed place
but is marked review; a name not read or not found is 'cannot place'. A folder found twice is
review. The file name is kept (renaming is a separate decision). A clash with a file already
there, or with another planned photo, is marked and a free name suggested.

If the library folder is reachable (--root, as the check script), each source is confirmed to
exist and each destination to be free. Writes one CSV row per planned photo (default
scripts\\_oneoff\\photo_consolidation_plan_<date>.csv) -- the only file it writes. That CSV is
the input for the later move step and its log for reversing.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import glob
import os
import posixpath
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import paths  # noqa: E402

FINAL = "READ ONLY. Nothing has been moved or changed."
LIFE = "Photos/Life"
SOURCES = ("Photos/Microscope Photos/", "Photos/Life/Dead Spiders/", "Photos/Life/Dead Craneflies/")
NEW_SPECIES = f"{LIFE}/_New species"
SPECIMEN = "Specimen"

PLANNED, REVIEW, CANNOT = "planned", "review", "cannot place"


def newest_check_csv() -> str | None:
    found = sorted(glob.glob(os.path.join(ROOT, "scripts", "_oneoff", "media_library_check_*.csv")))
    return found[-1] if found else None


def read_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def is_source(rel: str) -> bool:
    return rel.startswith(SOURCES)


def life_folders(rows):
    """{folder name: [full folder paths]} for every folder in Life outside the source trees,
    and the set of every existing file path (for clashes)."""
    by_name = defaultdict(set)
    files = set()
    for r in rows:
        rel = r["rel_path"]
        if not rel.startswith(LIFE + "/") or is_source(rel):
            continue
        files.add(rel.casefold())
        parts = rel.split("/")
        for i in range(3, len(parts)):                    # Photos/Life/<...>/<file>
            by_name[parts[i - 1].casefold()].add("/".join(parts[:i]))
    by_name.pop("life", None)
    return by_name, files


class Uksi:
    """Order, family and ancestor names for a TVK, read-only."""

    def __init__(self, path):
        self.conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)

    def taxon(self, tvk):
        r = self.conn.execute('SELECT "order", family, parent_tvk FROM taxa WHERE tvk = ?',
                              (tvk,)).fetchone()
        return r or (None, None, None)

    def species(self, name):
        return [r[0] for r in self.conn.execute(
            "SELECT tvk FROM taxa WHERE scientific_name = ? AND rank = 'Species'", (name,))]

    def ancestors(self, tvk, limit=40):
        names, seen = [], set()
        while tvk and tvk not in seen and len(names) < limit:
            seen.add(tvk)
            r = self.conn.execute("SELECT scientific_name, parent_tvk FROM taxa WHERE tvk = ?",
                                  (tvk,)).fetchone()
            if not r:
                break
            names.append(r[0])
            tvk = r[1]
        return names


def one(folders, name):
    found = sorted(folders.get((name or "").casefold(), ()))
    return found


def species_of(row, uksi):
    """(species name, tvk, review note) for a photo, or None when it cannot be placed."""
    status = row.get("match_status") or ""
    name, tvk = row.get("uksi_name") or "", row.get("tvk") or ""
    if name and tvk and status and not status.startswith("none"):
        return name, tvk, "" if status == "exact" else f"UKSI match: {status}"
    # The name reader does not yet know 'Male 29092026', '5cm', ' b ' (groundwork issue 2):
    # try the file name's first two words as a current UKSI species name, for review only
    words = os.path.splitext(row["rel_path"].rsplit("/", 1)[1])[0].split()
    found = uksi.species(" ".join(words[:2])) if len(words) >= 2 else []
    if len(found) != 1:
        return None
    return " ".join(words[:2]), found[0], "species read from the file name's first two words"


def place(name, tvk, review, folders, uksi):
    """(destination folder or '', status, reason)."""
    sp = one(folders, name)
    if len(sp) == 1:
        return posixpath.join(sp[0], SPECIMEN), REVIEW if review else PLANNED, \
            review or "species folder exists"
    if len(sp) > 1:
        return "", REVIEW, f"species folder found {len(sp)} times: " + " | ".join(sp)

    order, family, _ = uksi.taxon(tvk)
    fam = one(folders, family)
    if len(fam) == 1:
        return posixpath.join(fam[0], name, SPECIMEN), REVIEW if review else PLANNED, \
            review or "new species folder in an existing family folder"
    if len(fam) > 1:
        return "", REVIEW, f"family folder found {len(fam)} times: " + " | ".join(fam)

    orders = one(folders, order)
    if len(orders) > 1:
        return "", REVIEW, f"order folder found {len(orders)} times"
    if len(orders) == 1 and family:
        o = orders[0]
        below = {p.split("/")[o.count("/") + 1] for paths_ in folders.values() for p in paths_
                 if p.startswith(o + "/") and p.count("/") == o.count("/") + 1}
        level = Counter(b for b in below if b.casefold() in {a.casefold() for a in uksi.ancestors(tvk)})
        known_families = {b for b in below if uksi.conn.execute(
            "SELECT 1 FROM taxa WHERE family = ? LIMIT 1", (b,)).fetchone()}
        if level:
            o = posixpath.join(o, next(iter(level)))
        elif below and not known_families:
            return "", REVIEW, (f"{order}: a level between order and family "
                                f"({', '.join(sorted(below))}) -- none matches this species")
        return posixpath.join(o, family, name, SPECIMEN), REVIEW if review else PLANNED, \
            review or "new family folder in an existing order folder"
    return posixpath.join(NEW_SPECIES, name, SPECIMEN), REVIEW, \
        (review + "; " if review else "") + "no order folder in Life: _New species"


def free_name(folder, fname, taken):
    stem, ext = os.path.splitext(fname)
    n = 2
    while posixpath.join(folder, f"{stem} ({n}){ext}").casefold() in taken:
        n += 1
    return f"{stem} ({n}){ext}"


def plan(rows, uksi):
    folders, taken = life_folders(rows)
    out = []
    # The same file name and size in two source folders (e.g. Coleoptera\Labs and the family
    # folder): almost certainly one photo held twice -- the first is planned, the rest reviewed
    first_seen = {}
    for r in rows:
        rel = r["rel_path"]
        if not is_source(rel) or r.get("kind") != "image":
            continue
        who = species_of(r, uksi)
        name, tvk = (who[0], who[1]) if who else ("", "")
        dest, status, reason = place(*who, folders, uksi) if who else \
            ("", CANNOT, "name not read or not found in UKSI")
        fname = rel.rsplit("/", 1)[1]
        new_name = fname
        twin = first_seen.setdefault((fname.casefold(), r.get("size_bytes")), rel)
        if twin != rel:
            dest, status = "", REVIEW
            reason = f"probably a copy: same name and size as {twin}"
        if dest:
            target = posixpath.join(dest, fname)
            if target.casefold() in taken:
                new_name = free_name(dest, fname, taken)
                reason += f"; name taken there, suggested '{new_name}'"
                status = REVIEW
            taken.add(posixpath.join(dest, new_name).casefold())
        out.append({
            "source": rel,
            "destination": posixpath.join(dest, new_name) if dest else "",
            "status": status, "reason": reason,
            "uksi_name": name, "tvk": tvk,
            "match_status": r.get("match_status", ""), "date": r.get("date", ""),
            "size_bytes": r.get("size_bytes", ""),
        })
    return out


def check_on_disk(plan_rows, root: Path):
    missing = blocked = 0
    for p in plan_rows:
        if not (root / p["source"]).exists():
            p["status"], missing = REVIEW, missing + 1
            p["reason"] += "; source not found now"
        if p["destination"] and (root / p["destination"]).exists():
            p["status"], blocked = REVIEW, blocked + 1
            p["reason"] += "; destination already exists"
    return missing, blocked


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check-csv", default=None, help="the library check CSV (newest by default)")
    ap.add_argument("--root", default=str(Path.home() / "OneDrive" / "Documents" / "Media"))
    ap.add_argument("--uksi", default=str(paths.UKSI_DB))
    ap.add_argument("--csv", default=None)
    a = ap.parse_args(argv)

    src = a.check_csv or newest_check_csv()
    if not src or not os.path.exists(src):
        print("No library check CSV found: run scripts\\check_media_library.py first.")
        print(FINAL)
        return 1
    print(f"From: {src}")
    rows = read_rows(src)
    plan_rows = plan(rows, Uksi(a.uksi))
    root = Path(a.root)
    if root.is_dir():
        missing, blocked = check_on_disk(plan_rows, root)
        print(f"Library {root}: sources not found now {missing}, destinations taken {blocked}")
    else:
        print(f"Library {root} not reachable: files not checked on disk")

    print(f"\nPhotos considered: {len(plan_rows):,} "
          f"({sum(int(p['size_bytes'] or 0) for p in plan_rows) / 1024 ** 3:.2f} GB)")
    for k, v in Counter(p["status"] for p in plan_rows).most_common():
        print(f"  {k:<14}{v:>7,}")
    print("\nBy source folder:")
    for k, v in Counter("/".join(p["source"].split("/")[:3]) for p in plan_rows).most_common():
        print(f"  {k:<40}{v:>7,}")
    planned = [p for p in plan_rows if p["status"] == PLANNED]
    print("\nPlanned, by reason:")
    for k, v in Counter(p["reason"] for p in planned).most_common():
        print(f"  {k:<50}{v:>7,}")
    print(f"  species: {len({p['uksi_name'] for p in planned}):,}; new folders: "
          f"{len({p['destination'].rsplit('/', 1)[0] for p in planned if 'new ' in p['reason']}):,}")
    print("\nReview / cannot place, by reason (top 12):")
    for k, v in Counter(p["reason"].split(";")[0].split(": same name")[0] for p in plan_rows
                        if p["status"] != PLANNED).most_common(12):
        print(f"  {v:>5}  {k}")

    out = a.csv or os.path.join(ROOT, "scripts", "_oneoff",
                                f"photo_consolidation_plan_{datetime.date.today():%Y%m%d}.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(plan_rows[0]) if plan_rows else ["source"])
        w.writeheader()
        w.writerows(plan_rows)
    print(f"\nOne row per photo written to {out}")
    print(FINAL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
