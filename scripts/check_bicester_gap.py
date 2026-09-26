"""check_bicester_gap.py -- why does Examen see 254 species where the report says 433?

    python scripts/check_bicester_gap.py

Read-only. Writes nothing.

Examen, scoped to 2025, reports 254 species / 19 key for Bicester Graven Hill.
The 2025 report gives 433 species / 34 key. The 2023 report gives 389 / 27;
Examen's figure for 2023 is the second thing to check.

Candidate explanations, each testable:

  1. Records not flagged record_type = 'Commercial'
  2. A different project_name spelling, or records under the site name only
  3. Records still in Data Entry staging, never committed to observations
  4. Species with no TVK -- listed but excluded from every metric
  5. The report's total including desk-study or third-party determinations
     (Bicester's Hymenoptera and Diptera may have been determined by others)
  6. A survey spanning a year boundary, so 2025-scoping clips it

This reports what is actually in the database, by year, by record_type, by
project spelling, and by TVK presence.
"""
import os
import sys
from collections import Counter

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import sqlite3  # noqa: E402
import paths    # noqa: E402

NEEDLE = "bicester"


def main():
    c = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)

    print("")
    print("Bicester -- what is actually in observatum.db?")
    print("=" * 76)

    # ------------------------------------------------------------------
    # 1. Every project / site name containing "bicester", any record_type
    # ------------------------------------------------------------------
    print("  PROJECT AND SITE NAMES MATCHING 'bicester' (any record_type)")
    print("  " + "-" * 72)
    rows = c.execute(
        """SELECT COALESCE(project_name,''), COALESCE(site_name,''),
                  COALESCE(record_type,''), COUNT(1),
                  COUNT(DISTINCT species_name), MIN(date), MAX(date)
           FROM observations
           WHERE LOWER(COALESCE(project_name,'')) LIKE ?
              OR LOWER(COALESCE(site_name,'')) LIKE ?
           GROUP BY 1,2,3 ORDER BY 4 DESC""",
        (f"%{NEEDLE}%", f"%{NEEDLE}%")).fetchall()
    if not rows:
        print("    nothing found -- is the project named differently?")
    print(f"    {'project':28} {'site':22} {'type':11} {'recs':>6} {'spp':>5}  dates")
    for p, s, t, n, spp, d0, d1 in rows:
        print(f"    {p[:28]:28} {s[:22]:22} {t[:11]:11} {n:>6,} {spp:>5}  "
              f"{(d0 or '')[:10]}..{(d1 or '')[:10]}")

    # ------------------------------------------------------------------
    # 2. By survey year -- distinct species, and how many carry a TVK
    # ------------------------------------------------------------------
    print("")
    print("  BY YEAR (records matching 'bicester', any record_type)")
    print("  " + "-" * 72)
    print(f"    {'year':6} {'recs':>7} {'species':>8} {'with TVK':>9} "
          f"{'no TVK':>7} {'visits':>7} {'sites':>6}")
    for yr, n, spp, visits, sites in c.execute(
            """SELECT substr(date,1,4), COUNT(1), COUNT(DISTINCT species_name),
                      COUNT(DISTINCT date), COUNT(DISTINCT site_name)
               FROM observations
               WHERE (LOWER(COALESCE(project_name,'')) LIKE ?
                   OR LOWER(COALESCE(site_name,'')) LIKE ?)
               GROUP BY 1 ORDER BY 1""", (f"%{NEEDLE}%", f"%{NEEDLE}%")):
        with_tvk = c.execute(
            """SELECT COUNT(DISTINCT species_name) FROM observations
               WHERE (LOWER(COALESCE(project_name,'')) LIKE ?
                   OR LOWER(COALESCE(site_name,'')) LIKE ?)
                 AND substr(date,1,4)=?
                 AND species_tvk IS NOT NULL AND species_tvk != ''""",
            (f"%{NEEDLE}%", f"%{NEEDLE}%", yr)).fetchone()[0]
        print(f"    {str(yr):6} {n:>7,} {spp:>8} {with_tvk:>9} "
              f"{spp - with_tvk:>7} {visits:>7} {sites:>6}")

    # ------------------------------------------------------------------
    # 3. Species with no TVK -- listed by Examen but excluded from metrics
    # ------------------------------------------------------------------
    print("")
    print("  SPECIES WITH NO TVK (excluded from every metric)")
    print("  " + "-" * 72)
    notvk = [r[0] for r in c.execute(
        """SELECT DISTINCT species_name FROM observations
           WHERE (LOWER(COALESCE(project_name,'')) LIKE ?
               OR LOWER(COALESCE(site_name,'')) LIKE ?)
             AND (species_tvk IS NULL OR species_tvk = '')
           ORDER BY 1""", (f"%{NEEDLE}%", f"%{NEEDLE}%"))]
    print(f"    {len(notvk)} species")
    for n in notvk[:20]:
        print(f"      {n}")
    if len(notvk) > 20:
        print(f"      ... and {len(notvk) - 20} more")

    # ------------------------------------------------------------------
    # 4. Determiner / recorder split -- third-party determinations
    # ------------------------------------------------------------------
    print("")
    print("  BY DETERMINER (2025 records)")
    print("  " + "-" * 72)
    try:
        det = Counter()
        for d, n in c.execute(
                """SELECT COALESCE(determiner,'(blank)'), COUNT(DISTINCT species_name)
                   FROM observations
                   WHERE (LOWER(COALESCE(project_name,'')) LIKE ?
                       OR LOWER(COALESCE(site_name,'')) LIKE ?)
                     AND substr(date,1,4)='2025'
                   GROUP BY 1 ORDER BY 2 DESC""", (f"%{NEEDLE}%", f"%{NEEDLE}%")):
            det[d] = n
        for d, n in det.most_common(10):
            print(f"    {str(d)[:44]:44} {n:>5} species")
    except sqlite3.Error as e:
        print(f"    determiner column unavailable: {e}")

    # ------------------------------------------------------------------
    # 5. Anything still sitting in Data Entry staging?
    # ------------------------------------------------------------------
    print("")
    print("  DATA ENTRY STAGING")
    print("  " + "-" * 72)
    try:
        jobs = c.execute(
            """SELECT id, name, status, COALESCE(project,''), COALESCE(client,'')
               FROM entry_jobs ORDER BY id""").fetchall()
        hit = False
        for jid, name, status, proj, client in jobs:
            blob = f"{name} {proj} {client}".lower()
            n = c.execute("SELECT COUNT(1) FROM entry_staging WHERE job_id=?",
                          (jid,)).fetchone()[0]
            if NEEDLE in blob:
                hit = True
                print(f"    job {jid}: {name[:40]:40} {status:10} {n:>5} rows")
        if not hit:
            print("    no staging job mentions 'bicester'")
            print(f"    ({len(jobs)} jobs total; "
                  f"{sum(1 for j in jobs if j[2] == 'active')} active)")
    except sqlite3.Error as e:
        print(f"    staging tables unavailable: {e}")

    # ------------------------------------------------------------------
    # 6. What Examen would see, exactly as it queries
    # ------------------------------------------------------------------
    print("")
    print("  WHAT EXAMEN SEES (record_type='Commercial', by year)")
    print("  " + "-" * 72)
    for yr in ("2023", "2024", "2025", "2026"):
        row = c.execute(
            """SELECT COUNT(DISTINCT species_name), COUNT(1), COUNT(DISTINCT date)
               FROM observations
               WHERE record_type='Commercial'
                 AND LOWER(COALESCE(project_name,'')) LIKE ?
                 AND substr(date,1,4)=?""", (f"%{NEEDLE}%", yr)).fetchone()
        if row[1]:
            print(f"    {yr}: {row[0]:>5} species  {row[1]:>6,} records  "
                  f"{row[2]:>3} visits")
    print("")
    print("  Report figures for comparison:")
    print("    2023 (Heeney)  389 species, 27 key (6.9%)")
    print("    2025 (Heeney)  433 species, 34 key (7.8%)")
    print("")
    print("  Nothing has been changed.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
