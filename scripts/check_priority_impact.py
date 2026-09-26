"""check_priority_impact.py -- what changes when the priority collapse is fixed.

    python scripts/check_priority_impact.py

Read-only. Writes nothing.

Background
----------
build_codex_db.py maps all five priority jurisdictions to status_detail=None, so
they collide on the key (track, detail) at line ~607 and only one survives per
species. The fix puts the jurisdiction in status_detail so each gets its own row.

This script answers three questions before the rebuild:

  1. Does the key-species COUNT change?  Expected: no. The collapse drops extra
     priority rows but always leaves one, and _classify only asks whether the
     priority list is non-empty. If that expectation is wrong, this reports it.

  2. Which SPECIES-JURISDICTION facts are currently missing? That is what the
     fix restores, and what report figures like "12 S41 species" depend on.

  3. Does pantheon.db carry the S41 research-only distinction? codex_repository
     line 703 maps a category "Section 41 Priority Species - research only", so
     the data should be there.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

import sqlite3   # noqa: E402
import paths     # noqa: E402
from build_codex_db import DESIG_TO_TRACK  # noqa: E402

PRIORITY_ABBRS = {a: v for a, (t, v, _d) in DESIG_TO_TRACK.items() if t == "priority"}


def main():
    cx = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)

    print("")
    print("Priority-track fix -- impact assessment")
    print("=" * 74)

    # ------------------------------------------------------------------
    # 1. Who loses priority rows, and does anyone lose the track entirely?
    # ------------------------------------------------------------------
    truth = {}      # tvk -> set of jurisdictions it should have
    for abbr, value in PRIORITY_ABBRS.items():
        for (tvk,) in cx.execute(
                "SELECT DISTINCT tvk FROM designations "
                "WHERE designation_abbreviation=?", (abbr,)):
            truth.setdefault(tvk, set()).add(value)

    have = {}       # tvk -> set currently in status_summary
    for tvk, value in cx.execute(
            "SELECT tvk, status_value FROM status_summary "
            "WHERE status_track='priority'"):
        have.setdefault(tvk, set()).add(value)

    losing = {t: v for t, v in truth.items() if len(v) > len(have.get(t, set()))}
    lost_track_entirely = [t for t in truth if not have.get(t)]

    print(f"  species with any priority designation:   {len(truth):,}")
    print(f"  species currently showing all of them:   {len(truth) - len(losing):,}")
    print(f"  species missing at least one:            {len(losing):,}")
    print(f"  species missing the track ENTIRELY:      {len(lost_track_entirely):,}")

    # ------------------------------------------------------------------
    # 2. Does key-species status change for anyone?
    # ------------------------------------------------------------------
    print("")
    print("  KEY SPECIES IMPACT")
    print("  " + "-" * 70)
    if lost_track_entirely:
        print(f"  {len(lost_track_entirely)} species have priority designations but NO")
        print(f"  priority row at all. These MAY gain key-species status.")
        print(f"  Checking each against the other qualifying tracks...")

        gain = []
        for tvk in lost_track_entirely:
            other = cx.execute(
                """SELECT COUNT(*) FROM status_summary WHERE tvk=? AND (
                       status_track IN ('rarity_modern','rarity_legacy',
                                        'specialist_panel','legal_protection')
                    OR (status_track='threat_iucn_2001'
                        AND status_value IN ('CR','EN','VU','NT'))
                    OR (status_track='threat_iucn_legacy'
                        AND status_value IN ('RDB1','RDB2','RDB3','RDBK')))""",
                (tvk,)).fetchone()[0]
            invert = cx.execute(
                "SELECT 1 FROM designations WHERE tvk=? AND category='Invertebrate' "
                "LIMIT 1", (tvk,)).fetchone()
            if invert and not other:
                gain.append(tvk)
        print(f"  invertebrates that would newly become key species: {len(gain):,}")
        for tvk in gain[:20]:
            nm = cx.execute("SELECT species_name FROM designations WHERE tvk=? LIMIT 1",
                            (tvk,)).fetchone()
            print(f"      {nm[0] if nm else tvk}")
    else:
        print("  Every species with a priority designation still has at least one")
        print("  priority row, so _classify already returns PRIORITY for all of them.")
        print("  => KEY SPECIES COUNTS DO NOT CHANGE. Only which jurisdictions")
        print("     are reported changes.")

    # ------------------------------------------------------------------
    # 3. Missing facts per jurisdiction
    # ------------------------------------------------------------------
    print("")
    print("  FACTS RESTORED BY THE FIX")
    print("  " + "-" * 70)
    print(f"    {'jurisdiction':32} {'true':>8} {'now':>8} {'restored':>10}")
    for value in sorted(set(PRIORITY_ABBRS.values())):
        t_n = sum(1 for v in truth.values() if value in v)
        h_n = sum(1 for v in have.values() if value in v)
        print(f"    {value:32} {t_n:>8,} {h_n:>8,} {t_n - h_n:>10,}")

    # ------------------------------------------------------------------
    # 4. Research-only in pantheon.db
    # ------------------------------------------------------------------
    print("")
    print("  RESEARCH-ONLY IN PANTHEON")
    print("  " + "-" * 70)
    try:
        pn = sqlite3.connect(f"file:{paths.PANTHEON_DB}?mode=ro", uri=True)
        cats = pn.execute(
            "SELECT category, COUNT(*) FROM conservation_status "
            "GROUP BY category ORDER BY 2 DESC").fetchall()
        for cat, n in cats:
            mark = "   <-- research-only flag" if "research" in str(cat).lower() else ""
            print(f"    {str(cat)[:52]:52} {n:>6,}{mark}")
        pn.close()
    except sqlite3.Error as e:
        print(f"    could not read pantheon.db conservation_status: {e}")
        print("    (table or column may be named differently -- worth a look)")

    print("")
    print("  Nothing has been changed.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
