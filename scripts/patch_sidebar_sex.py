"""patch_sidebar_sex.py -- sex breakdown on the Insect Collection sidebar.

    python scripts/patch_sidebar_sex.py

Requires shared/sex_summary.py (already in place for the Data Entry pill).

What changes
------------
Tree nodes gain the breakdown wherever anything has been sexed:

    All Specimens (2,568: \u264215 \u264018 +2535)
    Hymenoptera (332: \u26426 \u26408 +318)
      Apidae (61: \u26421 \u26402 +58)
        Bombus terrestris (13: \u26401 +12)
        Deporaus betulae (2: \u26421 \u26401)

A species with nothing sexed reads as it always did. The `+n` shrinks as the
collection is worked through, so the tree doubles as a progress view.

Two implementation notes
------------------------
**The sex counts are held in a separate lookup**, not folded into the existing
`(count, sort_key)` tuple. That tuple is unpacked in eight places in build_tree;
widening it would mean eight more anchors and eight more chances to get one
wrong.

**`_show_species_detail` no longer parses the count back out of the label.** It
read `int(text.split('(')[-1].rstrip(')'))`, which breaks the moment the label
gains anything else. The count is now carried on the item as data, which is
where it should have been.

Classification comes from shared/sex_summary.py -- imported, not restated, so
the sidebar and the Data Entry pill cannot disagree about what "Male" means.

Safe to re-run. Backs up as .bak_sex alongside each file.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIXIN = os.path.join(_ROOT, "Observatum", "src", "views", "collection",
                     "ic_sidebar_mixin.py")
SIDEBAR = os.path.join(_ROOT, "Observatum", "src", "views", "collection",
                       "taxonomic_sidebar.py")

# ---------------------------------------------------------------- mixin
M_OLD = '''            specimens = [dict(zip(
                ['order_name', 'superfamily', 'family', 'subfamily', 'species_name',
                 'species_tvk', 'taxonomic_sort_key', 'specimen_count'],
                row
            )) for row in cursor.fetchall()]'''

M_NEW = '''            specimens = [dict(zip(
                ['order_name', 'superfamily', 'family', 'subfamily', 'species_name',
                 'species_tvk', 'taxonomic_sort_key', 'specimen_count'],
                row
            )) for row in cursor.fetchall()]

            # Sex breakdown per species, classified in Python rather than SQL:
            # the rule for what counts as male or female lives in
            # shared/sex_summary.py and is imported, not restated, so the
            # sidebar and the Data Entry pill cannot come to disagree.
            try:
                from shared.sex_summary import classify_sex
                sexes = {}
                for name, sex, n in conn.execute(
                        """SELECT species_name, sex, COUNT(*) FROM specimens
                           WHERE taxonomic_sort_key IS NOT NULL
                           GROUP BY species_name, sex"""):
                    m, f, o = sexes.get(name, (0, 0, 0))
                    k = classify_sex(sex)
                    if k == "m":
                        m += n
                    elif k == "f":
                        f += n
                    else:
                        o += n
                    sexes[name] = (m, f, o)
                for sp in specimens:
                    m, f, o = sexes.get(sp.get('species_name'), (0, 0, 0))
                    sp['male_count'], sp['female_count'], sp['other_count'] = m, f, o
            except Exception as e:
                print(f"[SIDEBAR] sex breakdown unavailable: {e}")'''

# ---------------------------------------------------------------- sidebar
S_OLD_INIT = """        self._family_stats = {}  # family -> (specimen_count, species_count, genera)"""

S_NEW_INIT = """        self._family_stats = {}  # family -> (specimen_count, species_count, genera)
        self._sexes = {}         # species_name -> (male, female, other)"""

S_OLD_RESET = """        self.tree.clear()
        self._tree_data = {}
        self._family_stats = {}"""

S_NEW_RESET = """        self.tree.clear()
        self._tree_data = {}
        self._family_stats = {}
        self._sexes = {}"""

S_OLD_PARSE = """            count = int(sp.get('specimen_count', 0) or 0)
            sort_key = int(sp.get('taxonomic_sort_key', 0) or 0)"""

S_NEW_PARSE = """            count = int(sp.get('specimen_count', 0) or 0)
            sort_key = int(sp.get('taxonomic_sort_key', 0) or 0)
            if species:
                self._sexes[species] = (int(sp.get('male_count', 0) or 0),
                                        int(sp.get('female_count', 0) or 0),
                                        int(sp.get('other_count', 0) or 0))"""

S_OLD_ALL = '''        all_item = QTreeWidgetItem(self.tree, [f"All Specimens ({total_all:,})"])'''

S_NEW_ALL = '''        all_item = QTreeWidgetItem(
            self.tree, [self._node_label("All Specimens", total_all,
                                         self._sexes.keys())])'''

S_OLD_ORDER = '''            order_item = QTreeWidgetItem(self.tree, [f"{order} ({order_count:,})"])'''

S_NEW_ORDER = '''            order_species = [s for fams in superfamilies.values()
                             for sd in fams.values() for s in sd]
            order_item = QTreeWidgetItem(
                self.tree, [self._node_label(order, order_count, order_species)])'''

S_OLD_FAMILY = '''                    family_text = f"{family} ({family_count})"'''

S_NEW_FAMILY = '''                    family_text = self._node_label(family, family_count,
                                                   species_dict.keys())'''

S_OLD_SPECIES = '''                    for species, (count, sort_key) in sorted_species:
                        species_text = f"{species} ({count})" if int(count) > 1 else species
                        species_item = QTreeWidgetItem(family_item, [species_text])
                        species_item.setData(0, Qt.ItemDataRole.UserRole, ('species', species))'''

S_NEW_SPECIES = '''                    for species, (count, sort_key) in sorted_species:
                        species_text = self._species_label(species, int(count))
                        species_item = QTreeWidgetItem(family_item, [species_text])
                        species_item.setData(0, Qt.ItemDataRole.UserRole, ('species', species))
                        # The count is carried as data, not parsed back out of
                        # the label -- see _show_species_detail.
                        species_item.setData(0, Qt.ItemDataRole.UserRole + 1, int(count))'''

S_OLD_HELPERS = """    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):"""

S_NEW_HELPERS = '''    # ── Sex summaries ───────────────────────────────────────────────
    # Formatting comes from shared/sex_summary.py so the sidebar, the Data
    # Entry pill and the family detail panel cannot drift apart.

    def _sum_sexes(self, species_names):
        """(male, female, other) totalled across a set of species names."""
        m = f = o = 0
        for name in species_names:
            a, b, c = self._sexes.get(name, (0, 0, 0))
            m += a; f += b; o += c
        return m, f, o

    def _sex_summary(self, species_names):
        """The bracketed breakdown, or '' where nothing has been sexed."""
        try:
            from shared.sex_summary import format_sex_summary
        except ImportError:
            return ""
        return format_sex_summary(*self._sum_sexes(species_names))

    def _node_label(self, name, count, species_names):
        """'Apidae (61)' or 'Apidae (61: \\u26421 \\u26402 +58)'."""
        s = self._sex_summary(species_names)
        return f"{name} ({count:,}: {s})" if s else f"{name} ({count:,})"

    def _species_label(self, species, count):
        """A single unsexed specimen still shows just the name, as before."""
        s = self._sex_summary([species])
        if s:
            return f"{species} ({count}: {s})" if count > 1 else f"{species} ({s})"
        return f"{species} ({count})" if count > 1 else species

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):'''

S_OLD_DETAIL = '''        # Count specimens
        specimen_count = 0
        stats = self._family_stats.get(family, (0, 0, []))
        # Get from tree item text
        text = item.text(0)
        if '(' in text and text.endswith(')'):
            try:
                specimen_count = int(text.split('(')[-1].rstrip(')'))
            except ValueError:
                specimen_count = 1
        else:
            specimen_count = 1'''

S_NEW_DETAIL = '''        # Specimen count, carried as data on the item. It used to be parsed
        # back out of the label text, which breaks as soon as the label gains
        # anything else -- a sex breakdown, for instance.
        specimen_count = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not isinstance(specimen_count, int):
            specimen_count = 1'''


def apply(path, edits, marker):
    name = os.path.basename(path)
    if not os.path.exists(path):
        print(f"  x NOT FOUND: {path}")
        return False
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if marker in text:
        print(f"  = {name}: already patched")
        return True
    ok = True
    for label, old, new in edits:
        n = text.count(old)
        if n == 1:
            text = text.replace(old, new)
            print(f"  + {name}: {label}")
        else:
            print(f"  x {name}: {label}  ({n} matches, expected 1)")
            ok = False
    if not ok:
        print(f"    -> {name} NOT written")
        return False
    backup = path + ".bak_sex"
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return True


def main():
    if not os.path.exists(os.path.join(_ROOT, "shared", "sex_summary.py")):
        print("  x shared/sex_summary.py not found -- save it first")
        return 1

    print("")
    print("Patching -- sex breakdown on the Insect Collection sidebar")
    print("=" * 70)

    ok = apply(MIXIN, [("sex counts on the tree query", M_OLD, M_NEW)],
               "male_count")

    ok &= apply(SIDEBAR,
                [("sex lookup on the view", S_OLD_INIT, S_NEW_INIT),
                 ("reset it per rebuild", S_OLD_RESET, S_NEW_RESET),
                 ("capture per species", S_OLD_PARSE, S_NEW_PARSE),
                 ("label helpers", S_OLD_HELPERS, S_NEW_HELPERS),
                 ("All Specimens node", S_OLD_ALL, S_NEW_ALL),
                 ("order node", S_OLD_ORDER, S_NEW_ORDER),
                 ("family node", S_OLD_FAMILY, S_NEW_FAMILY),
                 ("species node + count as data", S_OLD_SPECIES, S_NEW_SPECIES),
                 ("stop parsing the count from the label",
                  S_OLD_DETAIL, S_NEW_DETAIL)],
                "_sex_summary")

    print("")
    if not ok:
        print("  One or more files unchanged -- review before opening Observatum.")
        return 1

    print("  Checking both files compile, and what the tree will show...")
    try:
        import py_compile
        py_compile.compile(MIXIN, doraise=True)
        py_compile.compile(SIDEBAR, doraise=True)
        sys.path.insert(0, _ROOT)
        import sqlite3
        import paths
        from shared.sex_summary import classify_sex, format_sex_summary

        c = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
        fam = {}
        for family, sex, n in c.execute(
                """SELECT COALESCE(family,'(none)'), sex, COUNT(*)
                   FROM specimens GROUP BY 1, 2"""):
            m, f_, o = fam.get(family, (0, 0, 0))
            k = classify_sex(sex)
            if k == "m":
                m += n
            elif k == "f":
                f_ += n
            else:
                o += n
            fam[family] = (m, f_, o)
        c.close()

        print("  + compiles cleanly")
        print("")
        print("  Families that would show a breakdown today:")
        shown = 0
        for family, (m, f_, o) in sorted(fam.items(),
                                         key=lambda kv: -(kv[1][0] + kv[1][1])):
            s = format_sex_summary(m, f_, o)
            if not s:
                continue
            print(f"    {family[:30]:30} ({m + f_ + o}: {s})")
            shown += 1
            if shown >= 8:
                break
        if not shown:
            print("    none yet")
    except Exception as e:  # noqa: BLE001
        print(f"  x FAILED: {type(e).__name__}: {e}")
        print("    restore: copy *.bak_sex back over each file")
        return 1

    print("")
    print("  NEXT: Observatum -> Insect Collection -> toggle the sidebar.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
