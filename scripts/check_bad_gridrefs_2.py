"""Grid-reference detective, pass 2 -- READ ONLY. Nothing is written.

1. The 6 unplaceable grid refs, looked for in the SPECIMENS table
2. The two Kent Deadwood TQ678990 records: grid refs used on the same visit
3. The Kent Deadwood record dated 2026-07-10: which visits exist in July 2024/2025

Run:  python scripts\\check_bad_gridrefs_2.py 2>&1 | Out-File -FilePath gridref_check2.txt -Encoding utf8
"""
import os, sys, re, sqlite3, difflib
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths

BAD = ["SV111428", "SP55906", "TQ688684`", "SK55955639687", "SP16623", "18/05/2024"]

con = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row


def columns(table):
    return [r[1] for r in con.execute(f"PRAGMA table_info({table})")]


def pick(cols, *cands):
    for c in cands:
        if c in cols:
            return c
    for c in cands:
        for col in cols:
            if c in col:
                return col
    return None


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def show_row(r, skip=()):
    d = dict(r)
    print(f"    record id={d.get('id', '?')}")
    for k, v in d.items():
        if v not in (None, "") and k != "id" and k not in skip:
            print(f"      {k:<24} {str(v).replace(chr(10), ' ')[:70]}")


SC = columns("specimens")
S_GR = pick(SC, "grid_ref", "grid_reference", "gridref")
S_SITE = pick(SC, "site_name", "location", "site")
S_DATE = pick(SC, "date", "collection_date", "date_collected")

print("Grid-reference check, pass 2  --  READ ONLY")
print("=" * 76)
print(f"  specimens columns used: grid={S_GR} site={S_SITE} date={S_DATE}")

# every grid ref in both tables, for near-matching
refs = Counter()
for tbl, col in (("observations", "grid_ref"), ("specimens", S_GR)):
    if col:
        for r in con.execute(f"SELECT {col} g, COUNT(*) n FROM {tbl} "
                             f"WHERE {col} IS NOT NULL AND {col}!='' GROUP BY {col}"):
            refs[r["g"]] += r["n"]


def near(bad, n=6):
    b = norm(bad)
    m = re.match(r"^([A-Z]{2})(\d+)$", b)
    out = []
    for ref, cnt in refs.items():
        if ref == bad:
            continue
        r = norm(ref)
        score = difflib.SequenceMatcher(None, b, r).ratio()
        note = ""
        m2 = re.match(r"^([A-Z]{2})(\d+)$", r)
        if m and m2:
            if m.group(2) == m2.group(2) and m.group(1) != m2.group(1):
                score, note = max(score, 0.95), "same digits, different square"
            elif m.group(1) == m2.group(1) and len(m.group(2)) % 2 == 1 and any(
                    m.group(2) == m2.group(2)[:i] + m2.group(2)[i + 1:]
                    for i in range(len(m2.group(2)))):
                score, note = max(score, 0.95), "one digit dropped"
        if score >= 0.7:
            out.append((score, ref, cnt, note))
    return sorted(out, reverse=True)[:n]


# ------------------------------------------------------------------ 1
print()
print("=" * 76)
print("  1. UNPLACEABLE GRID REFS -- specimens table")
print("=" * 76)
if not S_GR:
    print("  No grid-ref column in specimens. Columns:", SC)
else:
    for bad in BAD:
        print()
        print(f"  {bad!r}")
        print("  " + "-" * 60)
        rows = con.execute(f"SELECT * FROM specimens WHERE {S_GR}=? OR TRIM({S_GR})=?",
                           (bad, bad)).fetchall()
        if not rows:
            print("    (not in specimens either)")
            continue
        for r in rows:
            show_row(r, skip=("created_at", "updated_at"))
            site = r[S_SITE] if S_SITE else None
            date = r[S_DATE] if S_DATE else None
            for label, tbl, gcol, scol, dcol in (
                    ("specimens", "specimens", S_GR, S_SITE, S_DATE),
                    ("observations", "observations", "grid_ref", "site_name", "date")):
                if site and date and scol and dcol:
                    sib = con.execute(
                        f"SELECT {gcol} g, COUNT(*) n FROM {tbl} WHERE {scol}=? AND {dcol}=? "
                        f"AND {gcol}!=? AND {gcol}!='' GROUP BY {gcol} ORDER BY n DESC LIMIT 8",
                        (site, date, bad)).fetchall()
                    print(f"    {label}, same site + date: " +
                          (", ".join(f"{s['g']} x{s['n']}" for s in sib) or "none"))
                if site and scol:
                    sib = con.execute(
                        f"SELECT {gcol} g, COUNT(*) n FROM {tbl} WHERE {scol}=? "
                        f"AND {gcol}!=? AND {gcol}!='' GROUP BY {gcol} ORDER BY n DESC LIMIT 8",
                        (site, bad)).fetchall()
                    print(f"    {label}, same site any date: " +
                          (", ".join(f"{s['g']} x{s['n']}" for s in sib) or "none"))
        print("    near matches (both tables):")
        for score, ref, cnt, note in near(bad):
            print(f"      {ref:<16} x{cnt:<5} {score:.2f}  {note}")

# ------------------------------------------------------------------ 2
print()
print("=" * 76)
print("  2. TQ678990 -- grid refs used on the same visit")
print("=" * 76)
for r in con.execute("SELECT id, site_name, date, species_name FROM observations "
                     "WHERE grid_ref='TQ678990' AND project_name LIKE '%Kent Deadwood%'"):
    print(f"\n  id={r['id']}  {r['date']}  {r['site_name']}  ({r['species_name']})")
    for label, where, args in (
            ("same site + same date", "site_name=? AND date=?", (r["site_name"], r["date"])),
            ("same site, any date  ", "site_name=?", (r["site_name"],)),
            ("any site, same date  ", "date=? AND project_name LIKE '%Kent Deadwood%'", (r["date"],))):
        sib = con.execute(f"SELECT grid_ref g, grid_precision p, COUNT(*) n FROM observations "
                          f"WHERE {where} AND grid_ref!='TQ678990' "
                          f"GROUP BY grid_ref ORDER BY n DESC LIMIT 8", args).fetchall()
        print(f"    {label}: " +
              (", ".join(f"{s['g']} x{s['n']}" for s in sib) or "none"))

# ------------------------------------------------------------------ 3
print()
print("=" * 76)
print("  3. KENT DEADWOOD visit dates, June-August 2024 and 2025")
print("=" * 76)
print("  date         site                           records  at TQ6886068489")
for r in con.execute(
        "SELECT date, site_name, COUNT(*) n, "
        "SUM(CASE WHEN grid_ref='TQ6886068489' THEN 1 ELSE 0 END) m "
        "FROM observations WHERE project_name LIKE '%Kent Deadwood%' "
        "AND (date BETWEEN '2024-06-01' AND '2024-08-31' "
        "  OR date BETWEEN '2025-06-01' AND '2025-08-31') "
        "GROUP BY date, site_name ORDER BY date"):
    print(f"  {r['date']}   {(r['site_name'] or '')[:30]:<30} {r['n']:>6}  {r['m']:>6}")

print()
print("  Other 'Collected' fungus records in Kent Deadwood (the Melanotus's companions):")
for r in con.execute(
        "SELECT date, site_name, grid_ref, species_name FROM observations "
        "WHERE project_name LIKE '%Kent Deadwood%' AND recorder='Collected' "
        "AND kingdom='Fungi' ORDER BY date LIMIT 20"):
    print(f"    {r['date']}  {(r['site_name'] or '')[:22]:<22} {r['grid_ref']:<14} {r['species_name']}")

print()
print("READ ONLY -- nothing has been changed.")
