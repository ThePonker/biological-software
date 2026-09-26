"""Grid-reference detective -- READ ONLY. Nothing is written.

For each grid reference the VC lookup could not place:
  - the full record
  - its siblings (same site + same date, then same site any date)
  - near-matching grid refs anywhere in the data
Then: the Kent Deadwood records that land in VC18 South Essex,
and the Kent Deadwood record dated 2026.

Run:  python scripts\\check_bad_gridrefs.py 2>&1 | Out-File -FilePath gridref_check.txt -Encoding utf8
"""
import os, sys, re, sqlite3, difflib
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "Observatum"))
import paths

BAD = ["SV111428", "SP55906", "TQ688684`", "SK55955639687", "SP16623", "18/05/2024"]

con = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
cols = [r[1] for r in con.execute("PRAGMA table_info(observations)")]


def pick(*cands):
    for c in cands:
        if c in cols:
            return c
    for c in cands:
        for col in cols:
            if c in col:
                return col
    return None


GR = pick("grid_reference", "grid_ref", "gridref")
SITE = pick("site_name", "location", "site")
DATE = pick("date", "observation_date", "obs_date", "record_date")
PROJ = pick("project_name", "project", "commercial_project")
SPEC = pick("species_name", "scientific_name", "taxon_name")
ID = pick("id", "observation_id") or "rowid"

print("Grid-reference check  --  READ ONLY")
print("=" * 76)
print(f"  columns used: id={ID} grid={GR} site={SITE} date={DATE} project={PROJ} species={SPEC}")
if not GR:
    print("  No grid-ref column found. Columns are:", cols)
    sys.exit(1)


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def split(s):
    m = re.match(r"^([A-Z]{1,2})(\d*)$", norm(s))
    return (m.group(1), m.group(2)) if m else (None, None)


all_refs = Counter()
for r in con.execute(f"SELECT {GR} g, COUNT(*) n FROM observations "
                     f"WHERE {GR} IS NOT NULL AND {GR}!='' GROUP BY {GR}"):
    all_refs[r["g"]] = r["n"]


def show_row(r):
    d = dict(r)
    rid = d.get(ID, "?")
    print(f"    record {ID}={rid}")
    for k, v in d.items():
        if v not in (None, "") and k != ID:
            v = str(v).replace("\n", " ")
            print(f"      {k:<24} {v[:70]}")


def top(sql, args, n=10):
    return con.execute(sql, args).fetchall()[:n]


def near(bad, n=8):
    b = norm(bad)
    bsq, bdig = split(bad)
    out = []
    for ref, cnt in all_refs.items():
        if ref == bad:
            continue
        r = norm(ref)
        score = difflib.SequenceMatcher(None, b, r).ratio()
        sq, dig = split(ref)
        note = ""
        if bdig and dig == bdig and sq != bsq:
            score, note = max(score, 0.95), "same digits, different square"
        elif bdig and dig and sq == bsq and len(bdig) % 2 == 1 and \
                any(bdig == dig[:i] + dig[i + 1:] for i in range(len(dig))):
            score, note = max(score, 0.95), "one digit dropped"
        if score >= 0.7:
            out.append((score, ref, cnt, note))
    out.sort(reverse=True)
    return out[:n]


select_all = f"SELECT {ID if ID != 'rowid' else 'rowid AS rowid'}, * FROM observations"

for bad in BAD:
    print()
    print("-" * 76)
    print(f"  {bad!r}")
    print("-" * 76)
    rows = con.execute(f"{select_all} WHERE {GR}=? OR TRIM({GR})=?", (bad, bad)).fetchall()
    if not rows:
        print("    (no observation carries this exact value any more)")
        continue
    for r in rows:
        show_row(r)
        site = r[SITE] if SITE else None
        date = r[DATE] if DATE else None
        if site and date:
            sib = top(f"SELECT {GR} g, COUNT(*) n FROM observations WHERE {SITE}=? AND {DATE}=? "
                      f"AND {GR}!=? GROUP BY {GR} ORDER BY n DESC", (site, date, bad))
            print(f"    same site + same date: " +
                  (", ".join(f"{s['g']} x{s['n']}" for s in sib) or "none"))
        if site:
            sib = top(f"SELECT {GR} g, COUNT(*) n FROM observations WHERE {SITE}=? "
                      f"AND {GR}!=? GROUP BY {GR} ORDER BY n DESC", (site, bad))
            print(f"    same site, any date:  " +
                  (", ".join(f"{s['g']} x{s['n']}" for s in sib) or "none"))
    nm = near(bad)
    print("    near matches anywhere:")
    for score, ref, cnt, note in nm:
        print(f"      {ref:<16} x{cnt:<5} {score:.2f}  {note}")
    if not nm:
        print("      none")


# ---------------------------------------------------------------- Kent Deadwood
print()
print("=" * 76)
print("  KENT DEADWOOD -- records resolving to VC18 South Essex")
print("=" * 76)


def load_vc():
    try:
        from DataEntry.bootstrap import get_vc_service_safe
        svc = get_vc_service_safe()
        for name in ("get_vc_from_grid_ref", "lookup", "get_vc"):
            f = getattr(svc, name, None)
            if f:
                return f
        print("    VC service has no known lookup method:", [m for m in dir(svc) if not m.startswith("_")])
    except Exception as e:
        print(f"    (VC service unavailable: {type(e).__name__}: {e})")
    return None


kcol = PROJ or SITE
krefs = con.execute(f"SELECT {GR} g, COUNT(*) n FROM observations WHERE {kcol} LIKE '%Kent Deadwood%' "
                    f"AND {GR} IS NOT NULL AND {GR}!='' GROUP BY {GR} ORDER BY n DESC").fetchall()
vc = load_vc()
essex = []
if vc:
    for k in krefs:
        try:
            res = vc(k["g"])
        except Exception as e:
            res = f"error {e}"
        s = str(res)
        if "Essex" in s or re.search(r"\b18\b", s):
            essex.append((k["g"], k["n"], s))
if essex:
    for g, n, s in essex:
        print(f"  {g}  x{n}   lookup: {s[:60]}")
        for r in con.execute(f"{select_all} WHERE {kcol} LIKE '%Kent Deadwood%' AND {GR}=?", (g,)):
            show_row(r)
        print("    near matches in Kent Deadwood:")
        g_n = norm(g)
        cands = sorted(((difflib.SequenceMatcher(None, g_n, norm(k["g"])).ratio(), k["g"], k["n"])
                        for k in krefs if k["g"] != g), reverse=True)[:6]
        for sc, ref, cnt in cands:
            print(f"      {ref:<16} x{cnt:<5} {sc:.2f}")
else:
    print("  Could not isolate them by lookup. All Kent Deadwood grid refs, most-used first:")
    for k in krefs:
        print(f"    {k['g']:<16} x{k['n']}")

# ---------------------------------------------------------------- 2026 record
if DATE:
    print()
    print("=" * 76)
    print("  KENT DEADWOOD -- record dated 2026 (suspected typo)")
    print("=" * 76)
    for r in con.execute(f"{select_all} WHERE {kcol} LIKE '%Kent Deadwood%' AND {DATE} LIKE '2026%'"):
        show_row(r)
        sib = top(f"SELECT {DATE} d, COUNT(*) n FROM observations WHERE {kcol} LIKE '%Kent Deadwood%' "
                  f"AND {GR}=? AND {DATE} NOT LIKE '2026%' GROUP BY {DATE} ORDER BY n DESC",
                  (r[GR],), 5)
        print("    other dates at the same grid ref: " +
              (", ".join(f"{s['d']} x{s['n']}" for s in sib) or "none"))

print()
print("READ ONLY -- nothing has been changed.")
