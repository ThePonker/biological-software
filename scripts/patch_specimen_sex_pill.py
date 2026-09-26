"""patch_specimen_sex_pill.py -- sex breakdown on the Data Entry specimen pill.

    python scripts/patch_specimen_sex_pill.py

Requires shared/sex_summary.py.

What it does
------------
The species readout's specimen pill reads "Spec. 7". It becomes:

    Spec. 7 (\u26423 \u26404)     all seven sexed
    Spec. 7 (\u26422 \u26401 +4)  three sexed, four not yet
    Spec. 7                       none sexed -- nothing worth saying

So that while working down a trap sample under the scope, "do I need to keep
this male Empis?" is answerable without leaving the grid.

Why the `+n`
------------
35 of 2,568 specimens currently carry a sex. Most species will show no
breakdown at all until the collection has been worked through, and a partly
sexed species must not read as though it holds only the sexed ones. The `+n`
shrinks visibly as the work is done.

Formatting lives in shared/sex_summary.py, not here: the same summary appears
in the Insect Collection sidebar and the collection dashboard, and writing it
three times is how this codebase has produced nine instances of one rule
drifting apart.

Safe to re-run. Backs up as info_panel.py.bak_sex.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "DataEntry", "info_panel.py")
BACKUP = TARGET + ".bak_sex"

OLD_COUNTS = '''        try:
            row = self._main.execute(
                "SELECT COUNT(*) FROM specimens WHERE species_tvk=?", (tvk,)
            ).fetchone()
            specimens = row[0] if row else 0
        except sqlite3.Error:
            pass
        return (personal, commercial, specimens)'''

NEW_COUNTS = '''        try:
            row = self._main.execute(
                "SELECT COUNT(*) FROM specimens WHERE species_tvk=?", (tvk,)
            ).fetchone()
            specimens = row[0] if row else 0
        except sqlite3.Error:
            pass
        return (personal, commercial, specimens)

    def specimen_sexes(self, tvk: str):
        """(male, female, other) specimens held for a TVK.

        `other` is everything not resolvable to male or female -- unsexed,
        blank, and "Unknown" alike. Kept separate from counts() so the existing
        three-tuple contract is untouched.
        """
        if not tvk:
            return (0, 0, 0)
        try:
            rows = self._main.execute(
                "SELECT sex FROM specimens WHERE species_tvk=?", (tvk,)
            ).fetchall()
        except sqlite3.Error:
            return (0, 0, 0)
        try:
            from shared.sex_summary import count_sexes
        except ImportError:
            return (0, 0, len(rows))
        return count_sexes(r[0] for r in rows)'''

OLD_PILLS = '''    def _set_count_pills(self, tvk):
        p, c, s = self._svc.counts(tvk)
        pend = self._pending_for(tvk)
        pp, pc = pend["personal"], pend["commercial"]
        pt = f"Pers. {p}" + (f" (+{pp})" if pp else "")
        ct = f"Comm. {c}" + (f" (+{pc})" if pc else "")
        tip = ("Committed records in Observatum. Any bracketed figure is rows still "
               "in Data Entry staging, across every open workbook.")
        pills = [self._pill(pt), self._pill(ct), self._pill(f"Spec. {s}")]
        for w in pills:
            w.setToolTip(tip)
        self._pills_row.set_items(pills)'''

NEW_PILLS = '''    def _set_count_pills(self, tvk):
        p, c, s = self._svc.counts(tvk)
        pend = self._pending_for(tvk)
        pp, pc = pend["personal"], pend["commercial"]
        pt = f"Pers. {p}" + (f" (+{pp})" if pp else "")
        ct = f"Comm. {c}" + (f" (+{pc})" if pc else "")
        tip = ("Committed records in Observatum. Any bracketed figure is rows still "
               "in Data Entry staging, across every open workbook.")

        # Specimens held, with the sex breakdown where any has been recorded.
        # The bracket is omitted entirely when nothing is sexed -- saying
        # "7 unsexed" adds nothing the total does not already give.
        male = female = other = 0
        st = f"Spec. {s}"
        try:
            from shared.sex_summary import format_sex_summary
            male, female, other = self._svc.specimen_sexes(tvk)
            summary = format_sex_summary(male, female, other)
            if summary:
                st = f"Spec. {s} ({summary})"
        except (ImportError, AttributeError):
            pass

        spec_pill = self._pill(st)
        if male or female:
            spec_pill.setToolTip(
                f"{s} specimen(s) held \\u2014 {male} male, {female} female"
                + (f", {other} not yet sexed" if other else "")
                + ".\\nFrom the Insect Collection.")
        else:
            spec_pill.setToolTip(
                f"{s} specimen(s) held in the Insect Collection."
                + (" None sexed yet." if s else ""))

        pills = [self._pill(pt), self._pill(ct)]
        for w in pills:
            w.setToolTip(tip)
        pills.append(spec_pill)
        self._pills_row.set_items(pills)'''


def main():
    shared = os.path.join(_ROOT, "shared", "sex_summary.py")
    if not os.path.exists(shared):
        print(f"  x shared/sex_summary.py not found -- save it first")
        return 1
    if not os.path.exists(TARGET):
        print(f"NOT FOUND: {TARGET}")
        return 1
    with open(TARGET, "r", encoding="utf-8") as f:
        text = f.read()

    print("")
    print("Patching DataEntry/info_panel.py -- specimen sex breakdown")
    print("=" * 70)

    if "specimen_sexes" in text:
        print("  = already patched -- nothing to do")
        return 0

    failed = 0
    for label, old, new in [("InfoService.specimen_sexes", OLD_COUNTS, NEW_COUNTS),
                            ("specimen pill", OLD_PILLS, NEW_PILLS)]:
        n = text.count(old)
        if n == 1:
            text = text.replace(old, new)
            print(f"  + {label}")
        else:
            print(f"  x {label}  ({n} matches, expected 1)")
            failed += 1

    print("")
    if failed:
        print(f"  {failed} edit(s) failed -- NOTHING WRITTEN.")
        return 1

    shutil.copy2(TARGET, BACKUP)
    print(f"  backup written: {os.path.basename(BACKUP)}")
    with open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(text)

    print("")
    print("  Checking the formatter and a live lookup...")
    try:
        import py_compile
        py_compile.compile(TARGET, doraise=True)
        py_compile.compile(shared, doraise=True)
        sys.path.insert(0, _ROOT)
        from shared.sex_summary import format_sex_summary, classify_sex

        cases = [((3, 4, 0), "\u26423 \u26404"),
                 ((2, 1, 4), "\u26422 \u26401 +4"),
                 ((0, 0, 7), ""),
                 ((0, 0, 0), ""),
                 ((1, 0, 0), "\u26421"),
                 ((0, 2, 1), "\u26402 +1")]
        bad = 0
        for args, expect in cases:
            got = format_sex_summary(*args)
            if got != expect:
                bad += 1
                print(f"    x {args} -> {got!r}, expected {expect!r}")
        for v, expect in [("Male", "m"), ("male", "m"), ("M", "m"),
                          ("Female", "f"), ("F", "f"), ("Unknown", None),
                          ("", None), (None, None)]:
            if classify_sex(v) != expect:
                bad += 1
                print(f"    x classify_sex({v!r}) -> {classify_sex(v)!r}, "
                      f"expected {expect!r}")
        if bad:
            print(f"  x {bad} case(s) wrong -- restore from the backup")
            return 1
        print(f"  + formatter and classifier correct")

        import sqlite3
        import paths
        c = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
        from shared.sex_summary import count_sexes, label_with_sexes
        rows = c.execute(
            """SELECT species_tvk, species_name FROM specimens
               WHERE TRIM(COALESCE(sex,'')) != '' AND species_tvk IS NOT NULL
               GROUP BY 1 ORDER BY COUNT(1) DESC LIMIT 5""").fetchall()
        print("")
        print("  Species that would show a breakdown today:")
        for tvk, name in rows:
            sexes = [r[0] for r in c.execute(
                "SELECT sex FROM specimens WHERE species_tvk=?", (tvk,))]
            m, f_, o = count_sexes(sexes)
            print(f"    {name[:34]:34} {label_with_sexes('Spec.', m, f_, o)}")
        c.close()
    except Exception as e:  # noqa: BLE001
        print(f"  x FAILED: {type(e).__name__}: {e}")
        print(f"    restore: copy {os.path.basename(BACKUP)} info_panel.py")
        return 1

    print("")
    print("  NEXT: open Observatum -> Data Entry and select one of those rows.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
