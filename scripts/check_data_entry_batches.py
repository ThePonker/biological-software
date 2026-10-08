"""Data Entry commits: anything missing or doubled?  READ ONLY.

Run after committing a job. For every committed batch (import_notes
'DataEntry batch ...'), counts records with:
    no site name / no grid ref / no vice-county / no TVK / no date
    commercial with no active embargo (iRecord export would include them)
    commercial with no project name
    a likely double entry: same species, date, grid ref, method, trap, sex and
        stage as another record in the batch -- often a sex split with the sex
        left "Not recorded"
then lists the ids behind every non-zero count.

Found on 8 October 2026: 59 blank site names, 31 pitfall records with no trap or
grid ref, one common name typed as a species, three doubled entries.

  py -3.14 scripts\\check_data_entry_batches.py              every batch
  py -3.14 scripts\\check_data_entry_batches.py --since 2026-10-08
"""
import os
import sqlite3
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths  # noqa: E402

SINCE = sys.argv[sys.argv.index("--since") + 1] if "--since" in sys.argv else ""
BLANK = lambda c: f"COALESCE(TRIM(CAST({c} AS TEXT)),'')=''"   # noqa: E731

CHECKS = [   # label, SQL condition
    ("no site", BLANK("site_name")),
    ("no grid ref", BLANK("grid_ref")),
    ("no VC", BLANK("vc_number")),
    ("no TVK", BLANK("species_tvk")),
    ("no date", BLANK("date")),
    ("no embargo", "record_type='Commercial' AND NOT (embargo_status='Active' "
                   "AND COALESCE(embargo_until,'') > date('now'))"),
    ("no project", "record_type='Commercial' AND " + BLANK("project_name")),
]
from DataEntry.commit_service import DOUBLE_KEY as DUP_KEY  # noqa: E402 -- one definition, shared with the pre-commit warning


def main():
    db = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
    batches = db.execute(
        """SELECT import_notes, COUNT(1), MIN(date), MAX(date),
                  GROUP_CONCAT(DISTINCT site_name), MAX(record_type)
           FROM observations
           WHERE import_notes LIKE 'DataEntry batch %' AND substr(import_notes, 17) >= ?
           GROUP BY import_notes ORDER BY import_notes""", (SINCE,)).fetchall()

    print("Data Entry batches -- gaps and doubles   READ ONLY")
    print("=" * 110)
    labels = [c[0] for c in CHECKS] + ["doubles"]
    print(f"{'batch':20} {'site(s)':24} {'type':10} {'rows':>5} " + " ".join(f"{l:>11}" for l in labels))
    detail, total = [], defaultdict(int)
    for batch, n, d0, d1, sites, rtype in batches:
        counts = []
        for label, cond in CHECKS:
            ids = [r for (r,) in db.execute(
                f"SELECT id FROM observations WHERE import_notes=? AND {cond} ORDER BY id", (batch,))]
            counts.append(len(ids))
            total[label] += len(ids)
            if ids:
                detail.append((batch, label, ids if len(ids) < n else [f"all {n} rows"]))
        groups = defaultdict(list)
        for row in db.execute(f"SELECT id, {', '.join(DUP_KEY)} FROM observations "
                              "WHERE import_notes=? ORDER BY id", (batch,)):
            groups[tuple((v or "") if not isinstance(v, str) else v.strip() for v in row[1:])].append(row[0])
        dups = [(k, ids) for k, ids in groups.items() if len(ids) > 1]
        counts.append(len(dups))
        total["doubles"] += len(dups)
        for k, ids in dups:
            qty = [str(q) for (q,) in db.execute(
                f"SELECT quantity FROM observations WHERE id IN ({','.join('?' * len(ids))}) ORDER BY id", ids)]
            detail.append((batch, "double", [f"{k[0]} {k[1]} {k[3] or ''}: ids {', '.join(map(str, ids))} "
                                             f"(qty {' + '.join(qty)}; sex {k[5] or '-'})"]))
        site_txt = ", ".join(s for s in (sites or "").split(",") if s.strip())[:24]
        print(f"{batch[16:]:20} {site_txt:24} {(rtype or '')[:10]:10} {n:>5} "
              + " ".join(f"{c:>11}" for c in counts))

    print("\n" + ("Nothing missing or doubled." if not detail else "Details:"))
    for batch, label, ids in detail:
        shown = ", ".join(map(str, ids[:40])) + (f" ... (+{len(ids) - 40})" if len(ids) > 40 else "")
        print(f"  {batch[16:]}  {label:11} {shown}")
    # Staging: placeholder TVKs waiting to be committed as if they were keys (backlog B3)
    junk = ("?", "??", "-", "0", "n/a", "na", "#n/a", "#ref!", "#value!", "#name?", "none", "tbc")
    try:
        rows = db.execute(
            f"""SELECT j.name, s.id, s.species_name, s.species_tvk FROM entry_staging s
                JOIN entry_jobs j ON j.id = s.job_id
                WHERE LOWER(TRIM(COALESCE(s.species_tvk,''))) IN ({','.join('?' * len(junk))})""",
            junk).fetchall()
        print(f"\nStaging rows holding a placeholder TVK ('?', '#N/A' ...): {len(rows)}")
        for r in rows[:20]:
            print(f"  job {r[0]!r}  row {r[1]}  {r[2]}  TVK {r[3]!r}")
    except sqlite3.Error as e:
        print(f"\nStaging not checked: {e}")

    print("\nNo embargo is reported, not judged: some commercial jobs are released deliberately.")
    print("READ ONLY -- nothing has been changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
