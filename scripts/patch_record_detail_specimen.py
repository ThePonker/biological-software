"""patch_record_detail_specimen.py -- show specimen fields on the detail dialog.

    python scripts/patch_record_detail_specimen.py

Two gaps, and the first is larger than it looks.

1. A SPECIMEN'S OWN FIELDS ARE NOT SHOWN
----------------------------------------
`_add_details_section` gives Date, Grid Ref, Location and Vice County, and that
is all. Sex, collector, determiner and every curatorial field are absent --
sex appears only in `_add_observation_fields`, which a specimen never reaches.

So the dialog for a specimen has been showing four fields out of a dozen
recorded, including the four curatorial ones added in August specifically so
they could be captured.

Now shown, for specimens only, and only where the record holds a value:
Sex, Collector, Determiner, Preparation, Condition, Storage, Drawer.

2. THE COLLECTION COUNT CARRIES NO BREAKDOWN
--------------------------------------------
"Collection ... 13" becomes "Collection ... \u26401 +12   13" -- how many of
this species are held, and what is known of their sex. The same summary as the
Data Entry pill, the tree nodes and the detail panel, from the same formatter.

The breakdown sits as a smaller muted label beside the count rather than inside
it, so the large figure stays the thing the eye lands on.

Safe to re-run. Backs up as record_detail_dialog.py.bak_sex.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "Observatum", "src", "views", "dialogs",
                      "record_detail_dialog.py")
BACKUP = TARGET + ".bak_sex"

# ---- 1. count the sexes alongside the specimen count ----------------
OLD_COUNTS = """            self._specimen_count = result[0][0] if result else 0
            
        except Exception as e:
            print(f"[RecordDetailDialog] Error loading counts: {e}")"""

NEW_COUNTS = '''            self._specimen_count = result[0][0] if result else 0

            # Sex breakdown across the held specimens of this species, for the
            # Collection row. Classification is imported from
            # shared/sex_summary.py so this cannot disagree with the tree, the
            # detail panel or the Data Entry pill.
            try:
                from shared.sex_summary import count_sexes
                if species_tvk:
                    rows = db.execute_main(
                        "SELECT sex FROM specimens WHERE species_tvk = ?",
                        (species_tvk,))
                else:
                    rows = db.execute_main(
                        "SELECT sex FROM specimens WHERE species_name = ?",
                        (species_name,))
                self._specimen_sexes = count_sexes(r[0] for r in (rows or []))
            except Exception:
                self._specimen_sexes = (0, 0, 0)

        except Exception as e:
            print(f"[RecordDetailDialog] Error loading counts: {e}")'''

OLD_INIT = """        self._observation_count = 0
        self._specimen_count = 0
        self._load_counts()"""

NEW_INIT = """        self._observation_count = 0
        self._specimen_count = 0
        self._specimen_sexes = (0, 0, 0)   # male, female, not-yet-sexed
        self._load_counts()"""

# ---- 2. show it on the Collection row --------------------------------
OLD_COLLECTION = """            collection_row.addStretch()
            
            collection_count = QLabel(str(self._specimen_count))"""

NEW_COLLECTION = '''            collection_row.addStretch()

            # Sex breakdown beside the count, smaller and muted, so the large
            # figure stays the thing the eye lands on.
            try:
                from shared.sex_summary import format_sex_summary
                summary = format_sex_summary(*self._specimen_sexes)
            except ImportError:
                summary = ""
            if summary:
                sex_label = QLabel(summary)
                sex_label.setStyleSheet(
                    f"font-size: 12px; color: {t.get('text_secondary')};"
                    " padding-right: 6px;")
                sex_label.setToolTip(
                    f"{self._specimen_sexes[0]} male, {self._specimen_sexes[1]} "
                    f"female"
                    + (f", {self._specimen_sexes[2]} not yet sexed"
                       if self._specimen_sexes[2] else ""))
                collection_row.addWidget(sex_label)

            collection_count = QLabel(str(self._specimen_count))'''

# ---- 3. the specimen's own fields ------------------------------------
OLD_DETAILS = """        # Vice County
        vc = self.record.get('vice_county', '')
        vc_num = self.record.get('vc_number') or self.record.get('vc', '')
        if vc or vc_num:
            vc_display = f"{vc} (VC{vc_num})" if vc and vc_num else vc or f"VC{vc_num}"
            self._add_label_value_row(layout, "Vice County", vc_display)"""

NEW_DETAILS = '''        # Vice County
        vc = self.record.get('vice_county', '')
        vc_num = self.record.get('vc_number') or self.record.get('vc', '')
        if vc or vc_num:
            vc_display = f"{vc} (VC{vc_num})" if vc and vc_num else vc or f"VC{vc_num}"
            self._add_label_value_row(layout, "Vice County", vc_display)

        if self.record_type == 'specimen':
            self._add_specimen_fields(layout)

    def _add_specimen_fields(self, layout):
        """Fields belonging to the specimen itself.

        These were absent entirely: the dialog showed date, grid ref, location
        and vice county, while sex, collector, determiner and all four
        curatorial fields went unshown -- including the ones added in August
        specifically so they could be recorded.

        Only fields the record actually holds are displayed, so a specimen with
        no curatorial data looks as it did before.
        """
        for label, key in (("Sex", "sex"),
                           ("Collector", "collector"),
                           ("Determiner", "determiner"),
                           ("Preparation", "preparation_type"),
                           ("Condition", "condition"),
                           ("Storage", "storage_location"),
                           ("Drawer", "drawer_unit")):
            raw = self.record.get(key)
            value = raw.strip() if isinstance(raw, str) else raw
            if value:
                self._add_label_value_row(layout, label, str(value))'''


def main():
    if not os.path.exists(TARGET):
        print(f"NOT FOUND: {TARGET}")
        return 1
    with open(TARGET, "r", encoding="utf-8") as f:
        text = f.read()

    print("")
    print("Patching record_detail_dialog.py -- specimen fields and sex")
    print("=" * 70)

    if "_add_specimen_fields" in text:
        print("  = already patched -- nothing to do")
        return 0

    failed = 0
    for label, old, new in [
            ("sex state on the dialog", OLD_INIT, NEW_INIT),
            ("count the sexes", OLD_COUNTS, NEW_COUNTS),
            ("breakdown on the Collection row", OLD_COLLECTION, NEW_COLLECTION),
            ("the specimen's own fields", OLD_DETAILS, NEW_DETAILS)]:
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
    try:
        import py_compile
        py_compile.compile(TARGET, doraise=True)
        print("  + compiles cleanly")
    except Exception as e:  # noqa: BLE001
        print(f"  x COMPILE FAILED: {e}")
        print(f"    restore: copy {os.path.basename(BACKUP)} record_detail_dialog.py")
        return 1

    # Which specimens would now show something they did not before.
    try:
        sys.path.insert(0, _ROOT)
        import sqlite3
        import paths
        c = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
        print("")
        print("  Fields now shown that were not, across the collection:")
        for label, col in (("Sex", "sex"), ("Collector", "collector"),
                           ("Determiner", "determiner"),
                           ("Preparation", "preparation_type"),
                           ("Condition", "condition"),
                           ("Storage", "storage_location"),
                           ("Drawer", "drawer_unit")):
            n = c.execute(
                f"SELECT COUNT(1) FROM specimens "
                f"WHERE TRIM(COALESCE({col},'')) != ''").fetchone()[0]
            print(f"    {label:14} {n:>5} specimen(s) hold a value")
        c.close()
    except Exception as e:  # noqa: BLE001
        print(f"  (could not sample the database: {e})")

    print("")
    print("  NEXT: Insect Collection -> double-click a specimen.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
