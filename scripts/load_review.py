"""Load one review's standard CSVs into Codex.

  data\\reviews\\<review folder>\\extracted\\
      review.csv     review_name, author, date_published, citation, licence,
                     source_file, species_count
      statuses.csv   species_name, tvk, iucn_status, qualifying_criteria,
                     rarity (NR / NS / blank), rarity_raw, ...
      accounts.csv   species_name, tvk, account_text, source_columns, sheet_row

Matching, status writing and the Key / Rare Key judgement are IMPORTED from
import_status_review.py (resolve, apply_status, key_tiers, backup), so every
review goes into Codex by the same rules as NECR702.

  * GB IUCN status -> threat_iucn_2001; NR/NS -> rarity_modern (blank clears).
    NE / blank IUCN = not assessed: no status written for that species.
  * Legacy tracks (rarity_legacy, threat_iucn_legacy) are cleared for assessed
    species unless --keep-legacy, as the importer does.
  * Accounts -> codex.db species_profiles under the new review's id.
  * Statuses and accounts in ONE transaction, after a backup.

DRY RUN by default; --apply to write.

Run:  python scripts\\load_review.py data\\reviews\\hymenoptera_symphyta_musgrove_2022_phase1
      python scripts\\load_review.py data\\reviews\\hymenoptera_symphyta_musgrove_2022_phase1 --apply
"""
import argparse, ast, csv, os, sqlite3, sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "scripts")]
import paths

src = open(os.path.join(ROOT, "scripts", "import_status_review.py"), encoding="utf-8-sig").read()
if not any(isinstance(n, ast.If) and "__main__" in ast.dump(n.test) for n in ast.parse(src).body):
    sys.exit("  x import_status_review.py has no __main__ guard -- not importing it. Nothing written.")
from import_status_review import resolve, apply_status, key_tiers, backup, CLEAR   # one rule

IUCN = {"CR", "EN", "VU", "NT", "LC", "DD", "NA", "RE", "EX", "EW"}

ap = argparse.ArgumentParser()
ap.add_argument("folder")
ap.add_argument("--apply", action="store_true")
ap.add_argument("--keep-legacy", action="store_true")
ap.add_argument("--add-statuses", action="store_true",
                help="add statuses to a review already loaded (e.g. as accounts only); accounts untouched")
a = ap.parse_args()

ex = os.path.join(a.folder, "extracted")
read = lambda f: list(csv.DictReader(open(os.path.join(ex, f), encoding="utf-8-sig")))
review = read("review.csv")[0]
statuses, accounts = read("statuses.csv"), read("accounts.csv")
source = f"{review['review_name']} ({review['author']}, {review['date_published'][:4]})"
date = review["date_published"] + ("-01" if len(review["date_published"]) == 7 else "")
now = datetime.now().isoformat()

print("")
print("Review load" + ("" if a.apply else "  --  DRY RUN"))
print("=" * 78)
print(f"  {review['review_name']}")
print(f"  {review['author']}, {review['date_published']}   licence: {review['licence']}")
print(f"  statuses.csv {len(statuses)} rows   accounts.csv {len(accounts)} rows")

uksi = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
codex = sqlite3.connect(str(paths.CODEX_DB))
c = codex.cursor()
existing = c.execute("SELECT id FROM reviews WHERE review_name=?", (review["review_name"],)).fetchone()
if existing and not a.add_statuses:
    sys.exit(f"\n  x already imported: {review['review_name']} -- nothing written "
             "(use --add-statuses to add statuses to it)")
if a.add_statuses:
    if not existing:
        sys.exit(f"\n  x --add-statuses: no review named {review['review_name']!r} -- nothing written")
    if c.execute("SELECT 1 FROM manual_entries WHERE review_id=? AND COALESCE(added_by,'')!='review-withdrawal'",
                 (existing[0],)).fetchone():
        sys.exit(f"\n  x review #{existing[0]} already has statuses -- nothing written")
    print(f"  adding statuses to existing review #{existing[0]}; its accounts are left as they are")

# What the review assessed. A threat-only review (e.g. a Red List with no
# rarity assessment) must not clear rarity statuses held from other sources:
# blank rarity there means "not assessed", not "assessed as none".
assessed = {s.strip() for s in (review.get("tracks_assessed") or "threat,rarity").split(",")}
accounts_only = assessed == {"accounts"}   # statuses already in Codex (e.g. via JNCC)
threat_only = "rarity" not in assessed
tracks = [] if accounts_only else ["threat_iucn_2001"] + ([] if threat_only else ["rarity_modern"])
if not a.keep_legacy and not accounts_only:
    tracks += ["threat_iucn_legacy"] + ([] if threat_only else ["rarity_legacy"])
print(f"  assesses: {', '.join(sorted(assessed))}   tracks written: {', '.join(tracks) or 'none -- accounts only'}")
plan, unresolved, not_assessed, odd = [], [], [], []
for r in ([] if accounts_only else statuses):
    raw = (r["iucn_status"] or "").strip().upper()
    note = ""
    if raw.startswith("CR") and "PE" in raw:
        raw, note = "CR", "CR(PE) -- Possibly Extinct"
    rar_only = raw in ("", "NE") and (r.get("rarity") or "").strip() and not threat_only and not accounts_only
    if raw in ("", "NE") and not rar_only:
        not_assessed.append(r["species_name"]);  continue
    if not rar_only and raw not in IUCN:
        odd.append((r["species_name"], r["iucn_status"]));  continue
    hit = resolve(uksi, r["species_name"].strip(), (r["tvk"] or "").strip() or None)
    if not hit:
        unresolved.append(r);  continue
    tvk, sci, family, order, how = hit
    current = {tr: v for tr, v in c.execute(
        "SELECT status_track, status_value FROM status_summary WHERE tvk=? "
        "AND COALESCE(status_detail,'')=''", (tvk,))}
    # a rarity-only row (e.g. provisional Nationally Scarce) was assessed and judged
    # not threatened: its Red List track is cleared, not left holding an older value
    new = {"threat_iucn_2001": CLEAR if rar_only else raw}
    if not threat_only:
        new["rarity_modern"] = (r.get("rarity") or "").strip() or CLEAR
    for tr in tracks:
        if tr.endswith("_legacy"):
            new[tr] = CLEAR
    plan.append({"row": r, "tvk": tvk, "name": sci, "how": how, "current": current, "new": new,
                 "note": "; ".join(x for x in (note, r.get("qualifying_criteria", "")) if x)})

# Same collapse rule as the importer: a row matched by its own TVK or name wins
# over one that only reached that species through a synonym.
rank = {"tvk": 0, "name": 1, "synonym": 2}
by, collapsed = {}, []
for p in plan:
    by.setdefault(p["tvk"], []).append(p)
plan = []
for g in by.values():
    g.sort(key=lambda p: rank[p["how"]])
    plan.append(g[0])
    collapsed += [(x["row"]["species_name"], x["how"], g[0]["name"]) for x in g[1:]]

print(f"\n  assessed and resolved: {len(plan)}   unresolved: {len(unresolved)}   "
      f"not assessed (NE/blank): {len(not_assessed)}   unrecognised: {len(odd)}")
print(f"  matched by: " + ", ".join(f"{k} {sum(1 for p in plan if p['how'] == k)}" for k in rank))
for r in unresolved[:25]:
    print(f"    unresolved: {r['species_name']}  ({r['tvk'] or 'no TVK'})  {r['iucn_status']}")
if len(unresolved) > 25:
    print(f"    ... and {len(unresolved) - 25} more")
for n, v in odd:
    print(f"    unrecognised IUCN value: {n} -> {v!r}")
for n, how, into in collapsed:
    print(f"    collapsed: {n} reached {into} via {how} -- {into}'s own row is used")

print("\n  CHANGES BY TRACK")
for tr in tracks:
    add = chg = clr = same = 0
    for p in plan:
        old, new = p["current"].get(tr), p["new"][tr]
        if new == CLEAR:
            clr += 1 if old else 0;  same += 0 if old else 1
        elif old is None:
            add += 1
        elif old == new:
            same += 1
        else:
            chg += 1
    print(f"    {tr:20} added {add:>4}   changed {chg:>4}   cleared {clr:>4}   unchanged {same:>4}")


def after(p):
    t = dict(p["current"])
    for tr, v in p["new"].items():
        if v == CLEAR: t.pop(tr, None)
        else: t[tr] = v
    return t


gained = [p for p in plan if key_tiers(after(p))[0] and not key_tiers(p["current"])[0]]
lost = [p for p in plan if key_tiers(p["current"])[0] and not key_tiers(after(p))[0]]
rare = [p for p in plan if key_tiers(after(p))[1] and not key_tiers(p["current"])[1]]
print(f"\n  KEY SPECIES (Telfer): become Key {len(gained)}   cease {len(lost)}   become Rare Key {len(rare)}")

obs = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
hits = []
for p in gained + lost:
    n = obs.execute("SELECT COUNT(1) FROM assessment_records WHERE species_tvk=?", (p["tvk"],)).fetchone()[0]
    s = obs.execute("SELECT COUNT(1) FROM specimens WHERE species_tvk=?", (p["tvk"],)).fetchone()[0]
    if n or s:
        hits.append((p, n, s))
print(f"  Of those, in your records (incl. contributed): {len(hits)}")
for p, n, s in sorted(hits, key=lambda h: -(h[1] + h[2]))[:20]:
    a_ = after(p)
    print(f"      {p['name'][:30]:30} {'KEY' if p in gained else 'no longer key':13} "
          f"{a_.get('threat_iucn_2001', '-')}/{a_.get('rarity_modern', '-')}   {n} records {s} specimens")

# Accounts resolve against UKSI exactly as statuses do -- never written under
# an unchecked spreadsheet TVK.
acc_plan, acc_skip = [], []
for r in ([] if a.add_statuses else accounts):
    if not r["account_text"].strip():
        continue
    hit = resolve(uksi, r["species_name"].strip(), (r.get("tvk") or "").strip() or None)
    if hit:
        acc_plan.append((hit[0], hit[1], r["account_text"]))
    else:
        acc_skip.append(r["species_name"])
seen = set()
acc_plan = [x for x in acc_plan if not (x[0] in seen or seen.add(x[0]))]
print(f"\n  ACCOUNTS -> codex.db species_profiles: {len(acc_plan)}   unmatched {len(acc_skip)}")
for n in acc_skip[:25]:
    print(f"    account not written (no UKSI match): {n}")
uksi.close(); obs.close()

if not a.apply:
    print("\n  DRY RUN -- nothing has been changed. Re-run with --apply to write.\n")
    sys.exit(0)

print(f"\n  backup: {backup(paths.CODEX_DB, 'codex')}")
try:
    if a.add_statuses:
        rid = existing[0]
    else:
        c.execute("""INSERT INTO reviews (review_name, author, taxon_group, status_track, date_published,
                     date_imported, source_file, species_count, supersedes_id, notes, licence)
                     VALUES (?,?,?,?,?,?,?,?,NULL,?,?)""",
                  (review["review_name"], review["author"], review.get("taxon_group") or ("Hymenoptera: Symphyta"
                   if "sawfl" in review["review_name"].lower() else ""),
                   ",".join(tracks), date, now, os.path.basename(os.path.normpath(a.folder)),
                   len(plan), "Loaded from extracted CSVs by load_review.py", review["licence"]))
        rid = c.lastrowid
    for p in plan:
        for tr, v in p["new"].items():
            c.execute("""INSERT INTO manual_entries (tvk, species_name, status_track, status_value,
                         status_detail, source_review, date_added, added_by, notes, review_id)
                         VALUES (?,?,?,?,NULL,?,?,?,?,?)""",
                      (p["tvk"], p["name"], tr, v, source, date, "review-load", p["note"] or None, rid))
            apply_status(c, p["tvk"], tr, v, None, source, date)
    for tvk, name, text in acc_plan:
        c.execute("DELETE FROM species_profiles WHERE tvk=? AND review_id=?", (tvk, rid))
        c.execute("""INSERT INTO species_profiles (tvk, review_id, species_name, profile_text, source,
                     date_added, date_updated, added_by) VALUES (?,?,?,?,?,?,NULL,'review-import')""",
                  (tvk, rid, name, text, source, now))
    codex.commit()
except Exception as e:
    codex.rollback()
    sys.exit(f"  x FAILED, rolled back: {type(e).__name__}: {e}")

n_me = c.execute("SELECT COUNT(1) FROM manual_entries WHERE review_id=?", (rid,)).fetchone()[0]
n_sp = c.execute("SELECT COUNT(1) FROM species_profiles WHERE review_id=?", (rid,)).fetchone()[0]
dup = c.execute("""SELECT COUNT(1) FROM (SELECT tvk, status_track, COALESCE(status_detail,'')
                   FROM status_summary GROUP BY 1,2,3 HAVING COUNT(1) > 1)""").fetchone()[0]
print(f"  review #{rid}: {n_me} status entries, {n_sp} accounts written")
print(f"  verify: duplicated statuses {dup} (should be 0)\n")
codex.close()
