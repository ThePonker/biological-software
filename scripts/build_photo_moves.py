"""B1: the move list -- the plan's planned rows plus Wil's review sheet -> one CSV. READ ONLY.

    py -3.14 scripts\\build_photo_moves.py
    py -3.14 scripts\\build_photo_moves.py --plan ... --review ... --check-csv ... --out ...

Inputs (newest of each in scripts\\_oneoff\\ by default):
  photo_consolidation_plan_<date>.csv   scripts\\plan_photo_consolidation.py
  photo_review_<date>.csv               the review sheet, with Wil's 'wil' column
  media_library_check_<date>.csv        scripts\\check_media_library.py (the Life folders)

What each row becomes:
  plan row 'planned'                    -> its destination
  review row, wil 'yes' / 'ok'          -> the sheet's proposal (its destination and new name)
  review row, wil blank                 -> the review folder, Photos\\_Photo review\\<its old path>
  wil 'Folder <Name>'                   -> that folder in Life (found by name), name kept
  wil 'move into <Genus species>'       -> that species' folder (not Specimen), name kept
  wil '<Genus species>' / 'Should be <Genus species>' / 'E. species' (genus from the old name)
                                        -> placed like the plan does, renamed to that species
  anything not understood               -> the review folder, with a note
Every new file name is written in the standard (shared.photo_names.standard_photo_stem): dates
'15.ix.17', sex in lower case. Files going to the review folder keep their names.
Writes photo_moves_<date>.csv (source, destination, reason, renamed) -- the only file it writes.
Then: scripts\\move_photos.py (dry run first).
"""
from __future__ import annotations

import argparse
import csv
import datetime
import glob
import os
import posixpath
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import paths  # noqa: E402
from scripts import plan_photo_consolidation as pc  # noqa: E402
from shared.photo_names import standard_photo_stem  # noqa: E402

FINAL = "READ ONLY. Nothing has been moved or changed."
REVIEW_DIR = "Photos/_Photo review"
YES = {"yes", "ok", "y"}


def newest(pattern):
    found = sorted(glob.glob(os.path.join(ROOT, "scripts", "_oneoff", pattern)))
    return found[-1] if found else None


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def standard_name(fname):
    stem, ext = os.path.splitext(fname)
    new, _ = standard_photo_stem(stem)
    return new + ext


def to_review(src):
    return posixpath.join(REVIEW_DIR, src[len("Photos/"):] if src.startswith("Photos/") else src)


_NOT_EPITHET = {"male", "female", "males", "females", "sp", "sp.", "spp", "cf", "cf.", "agg",
                "head", "gen"}


def written_species(fname):
    """The species as written: the first two words when they look like one ('Amara cupreus'),
    else '' -- 'Leiopus 3.vi.18', 'VCB 4', 'P1050002 male' carry no species to replace."""
    words = os.path.splitext(fname)[0].split()
    if len(words) >= 2 and re.fullmatch(r"[A-Z][a-z]+", words[0]) \
            and re.fullmatch(r"[a-z][a-z-]+", words[1]) and words[1] not in _NOT_EPITHET:
        return f"{words[0]} {words[1]}"
    return ""


class Resolver:
    def __init__(self, check_rows, uksi):
        self.folders, self.existing = pc.life_folders(check_rows)
        self.uksi = uksi

    def folder(self, name):
        found = pc.one(self.folders, name)
        return found[0] if len(found) == 1 else None

    def species(self, text, fname):
        """(UKSI name, tvk) for a species Wil wrote, or (None, None)."""
        t = re.sub(r"^(should be|is|=)\s+", "", text.strip(), flags=re.I).strip(" .")
        m = re.match(r"^([A-Z])\.\s*([a-z-]+)$", t)
        if m:                                   # 'E. merdarius': genus from the old name
            old_genus = (os.path.splitext(fname)[0].split() or [""])[0]
            if old_genus[:1].upper() == m.group(1):
                t = f"{old_genus} {m.group(2)}"
        found = self.uksi.species(t)
        if len(found) == 1:
            return t, found[0]
        # 'Contacyphon coarctatus' is held with its subgenus in some groups: allow that form
        rows = self.uksi.conn.execute(
            "SELECT scientific_name, tvk FROM taxa WHERE rank = 'Species' AND scientific_name LIKE ?",
            (t.split()[0] + " %" + t.split()[-1],)).fetchall() if " " in t else []
        rows = [r for r in rows if pc_clean(r[0]) == t]
        return (t, rows[0][1]) if len(rows) == 1 else (None, None)


def pc_clean(n):
    n = re.sub(r"\s*\(=.*?\)", "", n)
    n = re.sub(r"\s+\([A-Z][a-z]+\)", "", n)
    return " ".join(n.split())


def rename_species(fname, old, new):
    """The species written in the name replaced by the new one; with none written, the new
    species goes in front and the whole old name is kept (no date, sex or count is lost)."""
    stem, ext = os.path.splitext(fname)
    if old and stem.startswith(old):
        return new + stem[len(old):] + ext
    return f"{new} {stem}{ext}"


def from_review_row(r, res):
    """(destination or '', reason)."""
    src = r["source"] = r["source"].replace("\\", "/")
    fname = src.rsplit("/", 1)[1]
    answer = (r.get("wil") or "").strip()
    low = answer.lower().rstrip(".!")
    if low in YES:
        if not r.get("destination"):
            return to_review(src), "accepted, but the sheet has no destination"
        dest = r["destination"]
        folder, name = dest.rsplit("/", 1)
        if not r.get("action", "").startswith("archive"):
            name = standard_name(name)
        return posixpath.join(folder, name), f"sheet: {r.get('action') or 'move'}"
    if not answer:
        return to_review(src), "left blank: review folder"
    m = re.match(r"^folder\s+(.+)$", answer, re.I)
    if m:
        f = res.folder(m.group(1).strip())
        return (posixpath.join(f, standard_name(fname)), f"Wil: {answer}") if f else \
            (to_review(src), f"folder '{m.group(1)}' not found in Life")
    m = re.match(r"^move into\s+(.+)$", answer, re.I)
    if m:
        name, tvk = res.species(m.group(1), fname)
        if not tvk:
            return to_review(src), f"species '{m.group(1).strip()}' not found in UKSI"
        dest, status, why = pc.place(name, tvk, "", res.folders, res.uksi)
        if not dest:
            return to_review(src), f"no place for {name}: {why}"
        if dest.endswith("/" + pc.SPECIMEN):
            dest = dest[: -len(pc.SPECIMEN) - 1]       # into the species folder itself
        return posixpath.join(dest, standard_name(fname)), f"Wil: {answer}"
    name, tvk = res.species(answer, fname)
    if not tvk:
        return to_review(src), f"answer not understood or not in UKSI: '{answer}'"
    dest, status, why = pc.place(name, tvk, "", res.folders, res.uksi)
    if not dest:
        return to_review(src), f"no place for {name}: {why}"
    new = standard_name(rename_species(fname, written_species(fname), name))
    return posixpath.join(dest, new), f"Wil: {answer}"


def build(plan_rows, review_rows, check_rows, uksi):
    res = Resolver(check_rows, uksi)
    moves, seen = [], set()
    for p in plan_rows:
        if p["status"] != pc.PLANNED:
            continue
        folder, name = p["destination"].rsplit("/", 1)
        moves.append({"source": p["source"], "destination": posixpath.join(folder, standard_name(name)),
                      "reason": "plan: " + p["reason"]})
        seen.add(p["source"])
    for r in review_rows:
        if r["source"] in seen:
            continue
        dest, why = from_review_row(r, res)
        moves.append({"source": r["source"], "destination": dest, "reason": why})
        seen.add(r["source"])
    # two photos to one name, or a name already in that folder: the next free '(n)'
    taken = set(res.existing)
    for m in moves:
        folder, name = m["destination"].rsplit("/", 1)
        if m["destination"].casefold() in taken:
            name = pc.free_name(folder, name, taken)
            m["destination"] = posixpath.join(folder, name)
            m["reason"] += "; name taken, numbered"
        taken.add(m["destination"].casefold())
        m["renamed"] = "yes" if name != m["source"].rsplit("/", 1)[1] else ""
    return moves


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--plan", default=None)
    ap.add_argument("--review", default=None)
    ap.add_argument("--check-csv", default=None)
    ap.add_argument("--uksi", default=str(paths.UKSI_DB))
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    plan = a.plan or newest("photo_consolidation_plan_*.csv")
    review = a.review or newest("photo_review_*.csv")
    check = a.check_csv or newest("media_library_check_*.csv")
    for label, p in (("plan", plan), ("review sheet", review), ("library check", check)):
        if not p or not os.path.exists(p):
            print(f"No {label} CSV found.")
            print(FINAL)
            return 1
        print(f"{label:<14}{p}")
    moves = build(read(plan), read(review), read(check), pc.Uksi(a.uksi))
    print(f"\nPhotos to move: {len(moves):,}  (renamed: {sum(1 for m in moves if m['renamed']):,})")
    kinds = Counter("review folder" if m["destination"].startswith(REVIEW_DIR) else
                    "duplicates folder" if "/_duplicates_" in m["destination"] else
                    "_New species" if "/_New species/" in m["destination"] else "Life"
                    for m in moves)
    for k, v in kinds.most_common():
        print(f"  {k:<20}{v:>7,}")
    odd = [m for m in moves if m["destination"].startswith(REVIEW_DIR) and "blank" not in m["reason"]]
    if odd:
        print("\nTo the review folder because an answer was not understood:")
        for m in odd:
            print(f"  {m['source'].rsplit('/', 1)[1]}: {m['reason']}")
    out = a.out or os.path.join(ROOT, "scripts", "_oneoff",
                                f"photo_moves_{datetime.date.today():%Y%m%d}.csv")
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["source", "destination", "reason", "renamed"])
        w.writeheader()
        w.writerows(moves)
    print(f"\nMove list written to {out}\nNext: py -3.14 scripts\\move_photos.py  (a dry run)")
    print(FINAL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
