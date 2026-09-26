"""import_status_review.py -- import a Natural England Species Status review.

    python scripts/import_status_review.py REVIEW.xlsx \
        --name "A Review of the Status of the Leaf Beetles and allies of Great Britain (NECR702)" \
        --author "Lane, 2026" --date 2026-06-29 \
        --group "Chrysomelidae, Megalopodidae, Orsodacnidae"

    Add --apply to write. Without it, nothing is changed: a dry run is the
    default, and it reports exactly what would change.

What it reads
-------------
The supplementary spreadsheet published with each review in the series. The
format follows Musgrove's template, which the NECR702 author notes is being used
"for this and future Coleoptera IUCN Reviews", so this importer is built to be
reused. Columns are found by their headings, not their positions:

    Recommended Taxon Version Key     the TVK
    Recommended Taxon Name
    GB IUCN Status (YYYY)             the latest year is taken
    British Rarity Status (YYYY)      not the "AOO hectads" column
    Qualifying Criteria               kept as a note
    Ecology & Distribution            the species account

What it writes
--------------
For every species the review assessed, under ONE review record:

    threat_iucn_2001    the new IUCN category
    rarity_modern       NR / NS -- or cleared, where the review gives "none"
    rarity_legacy       cleared  } superseded by the modern review; see below
    threat_iucn_legacy  cleared  }

Every write, including every clear, goes into manual_entries, so a Codex
rebuild re-applies the lot. build_codex_db.py must carry the matching fix
(patch_codex_manual_apply.py) or a rebuild would reintroduce duplicates.

Species accounts go to codex.db.species_profiles, one per species per review,
keyed (tvk, review_id), with the review's citation. An import never touches
observatum.db.species_profiles, which holds Wil's own accounts only.

Why the legacy tracks are cleared
---------------------------------
Telfer's Key Species framework draws on three "versions" of status because
different groups were reviewed at different times: a group with no modern
review has only its Shirt or Hyman categories. For a group WITH a modern
review, the modern assessment replaces the older ones rather than adding to
them -- Hubble (2014) superseded Hyman (1992) for leaf beetles, and Lane (2026)
supersedes Hubble. Left in place, a species the 2026 review calls LC with no
rarity would still count as a Key Species on a 1992 Nb. Only species the review
assessed are cleared. --keep-legacy turns this off.

Why not the older import_codex_review.py
----------------------------------------
Five reasons, all confirmed rather than assumed:
  * INSERT OR REPLACE with a NULL status_detail does not replace -- SQLite
    treats NULL as distinct inside a composite primary key, so it ADDS a row
    beside the JNCC one. Old and new status both survive.
  * It can only write values, never clear one, so downgrades silently fail.
  * One track per run; these reviews give two.
  * Profiles go to codex.db, not observatum.db.
  * 'CR(PE)' is not normalised to 'CR', so a Possibly Extinct species would
    fall out of the Rare Key tier.
"""
import argparse
import os
import re
import sqlite3
import sys
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import paths  # noqa: E402

try:
    from openpyxl import load_workbook
except ImportError:
    print("openpyxl is required")
    sys.exit(1)

CLEAR = "none"      # a manual entry recording that the review REMOVED a status
IUCN_VALID = {"CR", "EN", "VU", "NT", "LC", "DD", "NE", "NA", "RE", "EX", "EW"}

KEY_THREAT = {"CR", "EN", "VU", "NT", "DD"}
RARE_THREAT = {"CR", "EN", "VU", "DD"}
KEY_RARITY = {"NR", "NS"}
LEGACY_RDB = {"RDB1", "RDB2", "RDB3", "RDBK", "RDBI", "RDB 1", "RDB 2",
              "RDB 3", "RDB K", "RDB I"}
LEGACY_NOTABLE = {"NA", "NB", "NOTABLE", "N"}


# ---------------------------------------------------------------- reading

def find_columns(header):
    """Locate the columns by heading. Returns {role: index}."""
    col = {}

    def latest(prefix, exclude=None):
        best, best_year = None, -1
        for i, h in enumerate(header):
            h = (h or "").strip()
            if not h.startswith(prefix):
                continue
            if exclude and exclude in h:
                continue
            m = re.search(r"\((\d{4})", h)
            year = int(m.group(1)) if m else 0
            if year > best_year:
                best, best_year = i, year
        return best, best_year

    for i, h in enumerate(header):
        h = (h or "").strip()
        if h == "Recommended Taxon Version Key":
            col["tvk"] = i
        elif h == "Recommended Taxon Name":
            col["name"] = i
        elif h == "Qualifying Criteria":
            col["criteria"] = i
        elif h.startswith("Ecology"):
            col["ecology"] = i
    col["iucn"], col["iucn_year"] = latest("GB IUCN Status (")
    col["rarity"], col["rarity_year"] = latest("British Rarity Status (", "AOO")
    return col


def normalise_iucn(raw):
    """('CR', 'Possibly Extinct') from 'CR(PE)', or (None, None)."""
    s = (raw or "").strip()
    if not s or s.lower() == "not included":
        return None, None
    note = "Possibly Extinct" if "(PE)" in s.upper() else None
    token = re.split(r"[\s(]", s, maxsplit=1)[0].upper()
    return (token, note) if token in IUCN_VALID else (None, f"unrecognised: {s}")


def normalise_rarity(raw):
    """'NR' | 'NS' | CLEAR | None (unrecognised), with the original kept."""
    s = (raw or "").strip().lower()
    if s.startswith("nationally scarce"):
        return "NS"
    if s.startswith("nationally rare"):
        return "NR"
    if s.startswith("none") or s == "extinct" or not s:
        return CLEAR          # extinct species carry RE on the IUCN track
    return None


def read_review(path):
    wb = load_workbook(path, read_only=True, data_only=True)
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        if rows and "Recommended Taxon Version Key" in [str(h or "").strip()
                                                         for h in rows[0]]:
            header = [str(h or "") for h in rows[0]]
            col = find_columns(header)
            missing = [k for k in ("tvk", "name", "iucn", "rarity")
                       if col.get(k) is None]
            if missing:
                raise SystemExit(f"columns not found: {missing}")
            out = []
            for r in rows[1:]:
                if not r or not r[col["name"]]:
                    continue
                get = lambda k: r[col[k]] if col.get(k) is not None else None
                out.append({
                    "name": str(get("name")).strip(),
                    "tvk": str(get("tvk") or "").strip(),
                    "iucn_raw": get("iucn"),
                    "rarity_raw": get("rarity"),
                    "criteria": str(get("criteria") or "").strip(),
                    "ecology": str(get("ecology") or "").strip(),
                })
            return ws.title, col, out
    raise SystemExit("no sheet with a 'Recommended Taxon Version Key' column")


# ---------------------------------------------------------------- resolving

def resolve(uksi, name, tvk):
    """(tvk, scientific_name, family, order) against current UKSI."""
    if tvk:
        r = uksi.execute('SELECT tvk, scientific_name, family, "order" '
                         "FROM taxa WHERE tvk=?", (tvk,)).fetchone()
        if r:
            return tuple(r) + ("tvk",)
    r = uksi.execute('SELECT tvk, scientific_name, family, "order" FROM taxa '
                     "WHERE scientific_name=? AND rank='Species' LIMIT 1",
                     (name,)).fetchone()
    if r:
        return tuple(r) + ("name",)
    try:
        s = uksi.execute("SELECT tvk FROM synonyms WHERE synonym=? LIMIT 1",
                         (name,)).fetchone()
        if s:
            r = uksi.execute('SELECT tvk, scientific_name, family, "order" '
                             "FROM taxa WHERE tvk=?", (s[0],)).fetchone()
            if r:
                return tuple(r) + ("synonym",)
    except sqlite3.Error:
        pass
    return None


# ---------------------------------------------------------------- key status

def key_tiers(tracks):
    """(is_key, is_rare_key) from a {track: value} dict, after Telfer."""
    t = (tracks.get("threat_iucn_2001") or "").upper()
    r = (tracks.get("rarity_modern") or "").upper()
    tl = (tracks.get("threat_iucn_legacy") or "").upper()
    rl = (tracks.get("rarity_legacy") or "").upper()
    if t == "NA":           # not an established native: never Key
        return False, False  # (same rule as CodexRepository._classify)
    rare = t in RARE_THREAT or r == "NR" or tl in LEGACY_RDB
    key = rare or t in KEY_THREAT or r in KEY_RARITY or rl in LEGACY_NOTABLE
    return key, rare


# ---------------------------------------------------------------- applying

def apply_status(c, tvk, track, value, detail, source, date):
    """DELETE then INSERT -- never INSERT OR REPLACE (NULL detail duplicates)."""
    c.execute("""DELETE FROM status_summary WHERE tvk=? AND status_track=?
                 AND COALESCE(status_detail,'') = COALESCE(?,'')""",
              (tvk, track, detail))
    if value == CLEAR:
        return
    c.execute("""INSERT INTO status_summary
                 (tvk, status_track, status_value, status_detail, source,
                  iucn_version, date_designated, origin)
                 VALUES (?,?,?,?,?,?,?,'manual')""",
              (tvk, track, value, detail, source,
               "2001" if track == "threat_iucn_2001" else None, date))


def backup(db_path, label):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(r"C:\BiologicalSoftware_Backups", "reference",
                        f"{label}_pre_review_{stamp}.db")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    src = sqlite3.connect(str(db_path))
    d = sqlite3.connect(dest)
    src.backup(d)
    d.close()
    src.close()
    return dest


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("xlsx")
    ap.add_argument("--name", required=True)
    ap.add_argument("--author", required=True)
    ap.add_argument("--date", required=True, help="publication date YYYY-MM-DD")
    ap.add_argument("--group", required=True)
    ap.add_argument("--apply", action="store_true", help="write (default: dry run)")
    ap.add_argument("--profiles-only", action="store_true",
                    help="write only the species accounts; the review must "
                         "already be imported")
    ap.add_argument("--keep-legacy", action="store_true",
                    help="do not clear legacy tracks for assessed species")
    a = ap.parse_args()

    source = f"{a.name} ({a.author})"
    year = int(a.date[:4])
    now = datetime.now().isoformat()

    print("")
    print("Species Status review import" + ("" if a.apply else "  --  DRY RUN"))
    print("=" * 76)

    sheet, col, rows = read_review(a.xlsx)
    print(f"  sheet: {sheet}   species rows: {len(rows)}")
    print(f"  IUCN column: {col['iucn_year']}   rarity column: {col['rarity_year']}")

    uksi = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
    codex = sqlite3.connect(str(paths.CODEX_DB))
    c = codex.cursor()

    already = c.execute("SELECT 1 FROM reviews WHERE review_name=?",
                        (a.name,)).fetchone()
    if already and not a.profiles_only:
        print(f"\n  x a review named '{a.name}' is already imported -- stopping")
        print("    (use --profiles-only to write just the species accounts)")
        return 1
    if a.profiles_only and not already:
        print(f"\n  x --profiles-only needs the review imported first -- stopping")
        return 1

    tracks_written = ["threat_iucn_2001", "rarity_modern"]
    if not a.keep_legacy:
        tracks_written += ["rarity_legacy", "threat_iucn_legacy"]

    plan, unresolved, bad_values = [], [], []
    for row in rows:
        iucn, iucn_note = normalise_iucn(row["iucn_raw"])
        if iucn is None:
            if iucn_note:
                bad_values.append((row["name"], "IUCN", row["iucn_raw"]))
            continue                       # not assessed by this review
        rarity = normalise_rarity(row["rarity_raw"])
        if rarity is None:
            bad_values.append((row["name"], "rarity", row["rarity_raw"]))
            continue
        hit = resolve(uksi, row["name"], row["tvk"])
        if not hit:
            unresolved.append(row)
            continue
        tvk, sci, family, order, how = hit
        current = {tr: v for tr, v in c.execute(
            "SELECT status_track, status_value FROM status_summary WHERE tvk=? "
            "AND COALESCE(status_detail,'')=''", (tvk,))}
        new = {"threat_iucn_2001": iucn, "rarity_modern": rarity}
        if not a.keep_legacy:
            new["rarity_legacy"] = CLEAR
            new["threat_iucn_legacy"] = CLEAR
        plan.append({"row": row, "tvk": tvk, "name": sci, "family": family,
                     "order": order, "how": how, "current": current, "new": new,
                     "note": "; ".join(x for x in (iucn_note, row["criteria"]) if x)})

    uksi.close()

    # Two review rows can land on ONE UKSI species -- the review treats them as
    # separate taxa, UKSI lumps them. A row that matched by its own TVK or name
    # is the authority; one that only arrived via the synonym table must not
    # compete with it (NECR702: Bruchus affinis, NA, reached B. rufimanus, LC,
    # through a synonym, and which survived depended on row order).
    by_tvk, collapsed = {}, []
    for p in plan:
        by_tvk.setdefault(p["tvk"], []).append(p)
    rank = {"tvk": 0, "name": 1, "synonym": 2}
    kept = []
    for tvk, group in by_tvk.items():
        group.sort(key=lambda p: rank[p["how"]])
        kept.append(group[0])
        for loser in group[1:]:
            collapsed.append((loser["row"]["name"], loser["how"], group[0]["name"]))
    plan = kept

    print(f"  assessed and resolved: {len(plan)}   unresolved: {len(unresolved)}"
          f"   unrecognised values: {len(bad_values)}")
    for r in unresolved[:10]:
        print(f"    unresolved: {r['name']}  ({r['tvk']})")
    for n, what, raw in bad_values[:10]:
        print(f"    unrecognised {what}: {n}  -> {str(raw)[:60]}")
    for n, how, into in collapsed:
        print(f"    collapsed: {n} reached {into} via {how} -- skipped;"
              f" {into}'s own row is used")
    if unresolved or bad_values or collapsed:
        print("  (these are skipped; nothing is written for them)")

    # ------------------------------------------------------------ changes
    print("")
    print("  CHANGES BY TRACK")
    for tr in tracks_written:
        changed = cleared = added = same = 0
        for p in plan:
            old = p["current"].get(tr)
            new = p["new"][tr]
            if new == CLEAR:
                cleared += 1 if old else 0
                same += 0 if old else 1
            elif old is None:
                added += 1
            elif old == new:
                same += 1
            else:
                changed += 1
        print(f"    {tr:20} added {added:>4}   changed {changed:>4}   "
              f"cleared {cleared:>4}   unchanged {same:>4}")

    # ------------------------------------------------------------ key status
    def after(p):
        t = dict(p["current"])
        for tr, v in p["new"].items():
            if v == CLEAR:
                t.pop(tr, None)
            else:
                t[tr] = v
        return t

    gained, lost, rare_gained, rare_lost = [], [], [], []
    for p in plan:
        k0, r0 = key_tiers(p["current"])
        k1, r1 = key_tiers(after(p))
        if k1 and not k0:
            gained.append(p)
        if k0 and not k1:
            lost.append(p)
        if r1 and not r0:
            rare_gained.append(p)
        if r0 and not r1:
            rare_lost.append(p)

    def fmt(p):
        o, n = p["current"], after(p)
        show = lambda t: ", ".join(v for v in (t.get("threat_iucn_2001"),
                                               t.get("rarity_modern"),
                                               t.get("threat_iucn_legacy"),
                                               t.get("rarity_legacy")) if v) or "-"
        return f"{p['name'][:32]:32} {show(o)[:24]:24} -> {show(n)}"

    print("")
    print("  KEY SPECIES STATUS (Telfer), before -> after")
    for label, lst in (("become Key", gained), ("cease to be Key", lost),
                       ("become Rare Key", rare_gained),
                       ("cease to be Rare Key", rare_lost)):
        print(f"    {label:20} {len(lst)}")
        for p in lst[:12]:
            print(f"      {fmt(p)}")
        if len(lst) > 12:
            print(f"      ... and {len(lst) - 12} more")

    # ------------------------------------------------------------ your records
    try:
        obs = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
        moved = {p["tvk"] for p in gained + lost + rare_gained + rare_lost}
        hits = []
        for p in plan:
            if p["tvk"] not in moved:
                continue
            n_obs = obs.execute("SELECT COUNT(1) FROM observations WHERE "
                                "species_tvk=?", (p["tvk"],)).fetchone()[0]
            n_spc = obs.execute("SELECT COUNT(1) FROM specimens WHERE "
                                "species_tvk=?", (p["tvk"],)).fetchone()[0]
            if n_obs or n_spc:
                hits.append((p["name"], n_obs, n_spc))
        obs.close()
        print("")
        print(f"  Of those, species in your own records: {len(hits)}")
        for name, o, s in sorted(hits, key=lambda h: -(h[1] + h[2]))[:15]:
            print(f"      {name[:34]:34} {o:>4} records  {s:>3} specimens")
    except sqlite3.Error as e:
        print(f"  (could not read observatum.db: {e})")

    # ------------------------------------------------------------ profiles
    # Review accounts go to codex.db.species_profiles, one per species per
    # review. Wil's own accounts live in observatum.db; an import never touches them.
    obs_path = str(paths.OBSERVATUM_DB)
    ob = sqlite3.connect(obs_path)        # kept open for verify()
    existing_rid = find_review_id(c, a.name)
    if existing_rid is not None and not a.profiles_only:
        print("")
        print(f"  NOTE: a review named {a.name!r} is already registered (id {existing_rid});")
        print("        importing again registers a second review. Use --profiles-only")
        print("        to refresh accounts under the existing one.")
    have = set()
    if a.profiles_only and existing_rid is not None:
        have = {r[0] for r in c.execute(
            "SELECT tvk FROM species_profiles WHERE review_id=?", (existing_rid,))}
    new_prof = upd_prof = 0
    prof_plan = []
    seen_tvk = set()
    for p in plan:
        if not p["row"]["ecology"] or p["tvk"] in seen_tvk:
            continue                      # one account per TVK
        seen_tvk.add(p["tvk"])
        if p["tvk"] in have:
            upd_prof += 1
        else:
            new_prof += 1
        prof_plan.append(p)
    target = existing_rid if a.profiles_only else "new"
    print("")
    print(f"  SPECIES ACCOUNTS -> codex.db (review {target})")
    print(f"    new {new_prof}   replacing this review's earlier text {upd_prof}")
    print("    (your own accounts are in observatum.db and are never touched)")
    if a.profiles_only and existing_rid is None:
        print("")
        print(f"  x --profiles-only needs the review registered; none named {a.name!r}")
        codex.close()
        ob.close()
        return 1

    if not a.apply:
        print("")
        print("  DRY RUN -- nothing has been changed.")
        print("  Re-run with --apply to write. Apply patch_codex_manual_apply.py")
        print("  first, or the next Codex rebuild would duplicate these statuses.")
        print("")
        codex.close()
        ob.close()
        return 0

    # ------------------------------------------------------------ write
    # Statuses and accounts land in codex.db in ONE transaction: all or nothing.
    print("")
    print(f"  backup: {backup(paths.CODEX_DB, 'codex')}")

    if a.profiles_only:
        rid = existing_rid
    else:
        rid = write_statuses(c, a, plan, tracks_written, source, now)
    write_profiles(c, prof_plan, rid, source, now)
    codex.commit()
    return verify(c, codex, ob)


def write_statuses(c, a, plan, tracks_written, source, now):
    c.execute("""INSERT INTO reviews (review_name, author, taxon_group,
                 status_track, date_published, date_imported, source_file,
                 species_count, supersedes_id, notes)
                 VALUES (?,?,?,?,?,?,?,?,?,?)""",
              (a.name, a.author, a.group, ",".join(tracks_written), a.date,
               now, os.path.basename(a.xlsx), len(plan), None,
               "Species Status review; modern tracks written, legacy "
               + ("kept" if a.keep_legacy else "cleared")
               + " for assessed species"))
    rid = c.lastrowid

    writes = 0
    for p in plan:
        for tr, v in p["new"].items():
            c.execute("""INSERT INTO manual_entries
                 (tvk, species_name, status_track, status_value, status_detail,
                  source_review, date_added, added_by, notes, review_id)
                 VALUES (?,?,?,?,NULL,?,?,?,?,?)""",
                      (p["tvk"], p["name"], tr, v, source, a.date,
                       "status-review-import", p["note"] or None, rid))
            apply_status(c, p["tvk"], tr, v, None, source, a.date)
            writes += 1
    print(f"  review #{rid} registered; {writes} status entries written")
    return rid


def find_review_id(c, name):
    """Id of the registered review with this name; the latest if several."""
    rows = c.execute("SELECT id FROM reviews WHERE review_name=? ORDER BY id",
                     (name,)).fetchall()
    if len(rows) > 1:
        print(f"  NOTE: {len(rows)} reviews share the name {name!r}; using id {rows[-1][0]}")
    return rows[-1][0] if rows else None


def write_profiles(c, prof_plan, rid, source, now):
    """Review accounts into codex.db, under the review they came from.

    DELETE then INSERT, never INSERT OR REPLACE -- the same rule as statuses.
    """
    for p in prof_plan:
        c.execute("DELETE FROM species_profiles WHERE tvk=? AND review_id=?",
                  (p["tvk"], rid))
        c.execute("""INSERT INTO species_profiles
            (tvk, review_id, species_name, profile_text, source,
             date_added, date_updated, added_by)
            VALUES (?,?,?,?,?,?,NULL,'review-import')""",
            (p["tvk"], rid, p["name"], p["row"]["ecology"], source, now))
    print(f"  {len(prof_plan)} species accounts written to codex.db (review {rid})")


def verify(c, codex, ob):
    dup = c.execute("""SELECT COUNT(1) FROM (SELECT tvk, status_track,
                       COALESCE(status_detail,'') d, COUNT(1) n
                       FROM status_summary GROUP BY 1,2,3 HAVING n > 1)""").fetchone()[0]
    print("")
    print(f"  verify: duplicated (tvk, track, detail) rows in status_summary: {dup}"
          + ("   <-- should be 0" if dup else ""))
    codex.close()
    ob.close()
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
