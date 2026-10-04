"""Organise status-review files into one folder per review.

  data\\reviews\\<order_group_author_year>\\
      source\\      files exactly as published -- never edited
      extracted\\   standard CSVs the loader reads (created empty here)
  data\\reviews\\_archive\\2026-03_prep\\   the March hand-made CSVs

Each file is COPIED, the copy checked against the original by SHA-256, and only
then is the original removed. Where the same file exists in both Downloads and
data\\reviews, the two are compared: identical -> one kept; different -> both
kept (the Downloads one with a suffix) and flagged.

DRY RUN by default; --apply to move.

Run:  python scripts\\organise_reviews.py
      python scripts\\organise_reviews.py --apply
"""
import hashlib, os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(ROOT, "data", "reviews")
DL = os.path.join(os.path.expanduser("~"), "Downloads")
APPLY = "--apply" in sys.argv

PLAN = {
    "coleoptera_chrysomelidae_necr702_2026": {
        "source": ["NECR702_Chrysomelidae_2026.pdf", "NECR702_Chrysomelidae_2026.xlsx"]},
    "hymenoptera_symphyta_musgrove_2022_phase1": {
        "source": ["Sawfly-Review-Phase-1-FINAL.pdf", "Sawfly-Review-Phase-1-DATA-TABLE-FINAL.xlsx"]},
    "hymenoptera_symphyta_musgrove_2023_phase2": {
        "source": ["Sawfly-Review-Phase-2-FINAL.pdf", "Sawfly-Review-Phase-2-Data-Table-FINAL.xlsx"]},
    "hymenoptera_symphyta_musgrove_2024_phase3": {
        "source": ["Sawfly-Review-Phase-3-FINAL.pdf", "Sawfly-Review-Phase-3-Data-Table-FINAL.xlsx"]},
    "lepidoptera_butterflies_fox_2022": {
        # hand-prepared in March from the paper; not the published source
        "extracted": ["butterfly_red_list_2022.csv"]},
    "lepidoptera_macromoths_fox_2019": {
        "source": ["S19-17 A review of the status of the macro-moths of Great Britain.pdf"]},
    os.path.join("_archive", "2026-03_prep"): {
        "": ["sawfly_all_rarity.csv", "sawfly_all_red_list.csv",
             "sawfly_red_list_2022.csv", "unresolved_species.csv"]},
}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


print("Organise status reviews  --  " + ("APPLY" if APPLY else "DRY RUN"))
print("=" * 78)
moves, problems, notes = [], [], []
for folder, subs in PLAN.items():
    for sub, files in subs.items():
        dest_dir = os.path.join(R, folder, sub)
        for name in files:
            cands = [p for p in (os.path.join(R, name), os.path.join(DL, name)) if os.path.isfile(p)]
            if not cands:
                if not os.path.isfile(os.path.join(dest_dir, name)):
                    problems.append(f"not found anywhere: {name}")
                else:
                    notes.append(f"already in place: {os.path.join(folder, sub, name)}")
                continue
            if len(cands) == 2:
                a, b = sha(cands[0]), sha(cands[1])
                if a == b:
                    notes.append(f"identical in data\\reviews and Downloads: {name} -- one kept")
                    moves.append((cands[0], os.path.join(dest_dir, name), [cands[1]]))
                else:
                    notes.append(f"DIFFERENT copies of {name} -- both kept; Downloads copy suffixed _downloads")
                    root_, ext = os.path.splitext(name)
                    moves.append((cands[0], os.path.join(dest_dir, name), []))
                    moves.append((cands[1], os.path.join(dest_dir, root_ + "_downloads" + ext), []))
            else:
                moves.append((cands[0], os.path.join(dest_dir, name), []))

for folder in PLAN:
    if not folder.startswith("_archive"):
        for sub in ("source", "extracted"):
            d = os.path.join(R, folder, sub)
            if not os.path.isdir(d):
                notes.append(f"create {os.path.relpath(d, ROOT)}")

for src, dst, extra in moves:
    where = "Downloads" if src.startswith(DL) else "data\\reviews"
    print(f"  {where:<13} {os.path.basename(src):<62}")
    print(f"  {'':13} -> {os.path.relpath(dst, ROOT)}")
for n in notes:
    print(f"  note: {n}")
for p in problems:
    print(f"  x {p}")

planned = {os.path.normcase(s) for s, _, _ in moves} | \
          {os.path.normcase(x) for _, _, e in moves for x in e}
left = [f for f in os.listdir(R) if os.path.isfile(os.path.join(R, f))
        and os.path.normcase(os.path.join(R, f)) not in planned]
if left:
    print(f"\n  Loose files in data\\reviews not in the plan (left alone): {left}")

if problems:
    sys.exit("\nABORTED -- fix the items marked x. Nothing moved.")
if not APPLY:
    print("\nDRY RUN -- nothing moved. Re-run with --apply.")
    sys.exit(0)

print()
for folder in PLAN:
    if not folder.startswith("_archive"):
        for sub in ("source", "extracted"):
            os.makedirs(os.path.join(R, folder, sub), exist_ok=True)
done = 0
for src, dst, extra in moves:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        if sha(dst) != sha(src):
            sys.exit(f"  x {dst} exists and differs -- stopped. Moved so far: {done}")
    else:
        shutil.copy2(src, dst)
    if sha(dst) != sha(src):
        sys.exit(f"  x copy of {src} does not verify -- original kept. Moved so far: {done}")
    for p in [src] + extra:
        os.remove(p)
    done += 1
    print(f"  ok {os.path.relpath(dst, ROOT)}  (verified, original removed)")
print(f"\n{done} files moved and verified.")
for folder in sorted(os.listdir(R)):
    d = os.path.join(R, folder)
    if os.path.isdir(d):
        for dp, _, fs in os.walk(d):
            for f in fs:
                print(f"  {os.path.relpath(os.path.join(dp, f), R)}")
