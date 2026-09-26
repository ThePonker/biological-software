"""patch_detail_panel_sex.py -- sex breakdown on the taxon detail panel.

    python scripts/patch_detail_panel_sex.py

The fourth and last place a specimen count is shown alongside the tree:

    British species: 88  |  Your specimens: 55 (\u26425 \u26402 +48)  |  Your species: 31
    Specimens: 13 (\u26401 +12)  |  Nationally Scarce (Nb)

Formatting comes from shared/sex_summary.py, as it does for the Data Entry pill
and the tree nodes. Four places, one formatter.

How the counts reach the panel
------------------------------
The panel is handed a specimen count and knows nothing about species, so it
cannot look the sexes up itself. Each `show_*` method gains an optional
`sexes=(male, female, other)` argument, and the sidebar -- which already holds
`self._sexes` -- supplies it.

The sidebar gathers the species names from the tree item's own children rather
than re-querying: the order and superfamily handlers already walk them to count
species, and the family handler has the item to hand. That also means the panel
and the node above it are computed from the same set and cannot disagree.

The argument is optional and defaults to nothing, so any other caller keeps
working unchanged.

Safe to re-run. Backs up as .bak_sex alongside each file.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL = os.path.join(_ROOT, "Observatum", "src", "views", "collection",
                     "family_detail_panel.py")
SIDEBAR = os.path.join(_ROOT, "Observatum", "src", "views", "collection",
                       "taxonomic_sidebar.py")

# ---------------------------------------------------------------- panel
P_HELPER_ANCHOR = """    def show_order(self, order_name: str, specimen_count: int,
                   species_count: int, families: list):
        \"\"\"Show order-level detail.\"\"\""""

P_HELPER = '''    @staticmethod
    def _specimens_text(specimen_count, sexes=None):
        """'55' or '55 (\\u26425 \\u26402 +48)'.

        The bracket appears only where something has been sexed -- 55 unsexed
        specimens are adequately described by 55. Shared with the tree nodes
        and the Data Entry pill via shared/sex_summary.py.
        """
        if not sexes:
            return str(specimen_count)
        try:
            from shared.sex_summary import format_sex_summary
        except ImportError:
            return str(specimen_count)
        s = format_sex_summary(*sexes)
        return f"{specimen_count} ({s})" if s else str(specimen_count)

    def show_order(self, order_name: str, specimen_count: int,
                   species_count: int, families: list, sexes=None):
        """Show order-level detail."""'''

P_ORDER = '''        british = self._count_british("order", order_name)
        self.stats_label.setText(
            f"British species: {british}  |  "
            f"Your specimens: {specimen_count}  |  Your species: {species_count}")'''

P_ORDER_NEW = '''        british = self._count_british("order", order_name)
        self.stats_label.setText(
            f"British species: {british}  |  "
            f"Your specimens: {self._specimens_text(specimen_count, sexes)}"
            f"  |  Your species: {species_count}")'''

P_SF_SIG = """    def show_superfamily(self, order_name: str, superfamily: str,
                         specimen_count: int, species_count: int, families: list):"""

P_SF_SIG_NEW = """    def show_superfamily(self, order_name: str, superfamily: str,
                         specimen_count: int, species_count: int, families: list,
                         sexes=None):"""

P_SF = '''        british = self._count_british("superfamily", superfamily)
        self.stats_label.setText(
            f"British species: {british}  |  "
            f"Your specimens: {specimen_count}  |  Your species: {species_count}")'''

P_SF_NEW = '''        british = self._count_british("superfamily", superfamily)
        self.stats_label.setText(
            f"British species: {british}  |  "
            f"Your specimens: {self._specimens_text(specimen_count, sexes)}"
            f"  |  Your species: {species_count}")'''

P_FAM_SIG = """    def show_family(self, order_name: str, family: str,
                    specimen_count: int, species_count: int, genera: list):"""

P_FAM_SIG_NEW = """    def show_family(self, order_name: str, family: str,
                    specimen_count: int, species_count: int, genera: list,
                    sexes=None):"""

P_FAM = '''        british = self._count_british("family", family)
        self.stats_label.setText(
            f"British species: {british}  |  "
            f"Your specimens: {specimen_count}  |  Your species: {species_count}")'''

P_FAM_NEW = '''        british = self._count_british("family", family)
        self.stats_label.setText(
            f"British species: {british}  |  "
            f"Your specimens: {self._specimens_text(specimen_count, sexes)}"
            f"  |  Your species: {species_count}")'''

P_SP_SIG = """    def show_species(self, species_name: str, tvk: str, common_name: str,
                     family: str, order_name: str, specimen_count: int,
                     conservation: str):"""

P_SP_SIG_NEW = """    def show_species(self, species_name: str, tvk: str, common_name: str,
                     family: str, order_name: str, specimen_count: int,
                     conservation: str, sexes=None):"""

P_SP = '''        stats_parts = [f"Specimens: {specimen_count}"]'''
P_SP_NEW = '''        stats_parts = [f"Specimens: {self._specimens_text(specimen_count, sexes)}"]'''

# ---------------------------------------------------------------- sidebar
S_ORDER = """        self.detail_panel.show_order(order_name, total_specimens, 
                                      len(total_species), families)"""

S_ORDER_NEW = """        self.detail_panel.show_order(order_name, total_specimens,
                                     len(total_species), families,
                                     self._sum_sexes(total_species))"""

S_SF = """        self.detail_panel.show_superfamily(order_name, sf_name, total_specimens,
                                            len(total_species), families)"""

S_SF_NEW = """        self.detail_panel.show_superfamily(order_name, sf_name, total_specimens,
                                           len(total_species), families,
                                           self._sum_sexes(total_species))"""

S_FAM = """        stats = self._family_stats.get(family, (0, 0, []))
        specimen_count, species_count, genera = stats
        self.detail_panel.show_family(
            order_name, family, specimen_count, species_count, genera)"""

S_FAM_NEW = """        stats = self._family_stats.get(family, (0, 0, []))
        specimen_count, species_count, genera = stats
        # Species names from the item's own children, so the panel and the node
        # above it are computed from the same set.
        fam_species = set()
        for i in range(item.childCount()):
            d = item.child(i).data(0, Qt.ItemDataRole.UserRole)
            if d and d[0] == 'species':
                fam_species.add(d[1])
        self.detail_panel.show_family(
            order_name, family, specimen_count, species_count, genera,
            self._sum_sexes(fam_species))"""

S_SP = """        self.detail_panel.show_species(
            species_name, tvk, common_name, family, order_name,
            specimen_count, conservation)"""

S_SP_NEW = """        self.detail_panel.show_species(
            species_name, tvk, common_name, family, order_name,
            specimen_count, conservation, self._sum_sexes([species_name]))"""


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
    print("")
    print("Patching -- sex breakdown on the taxon detail panel")
    print("=" * 70)

    ok = apply(PANEL,
               [("helper + show_order signature", P_HELPER_ANCHOR, P_HELPER),
                ("order stats", P_ORDER, P_ORDER_NEW),
                ("show_superfamily signature", P_SF_SIG, P_SF_SIG_NEW),
                ("superfamily stats", P_SF, P_SF_NEW),
                ("show_family signature", P_FAM_SIG, P_FAM_SIG_NEW),
                ("family stats", P_FAM, P_FAM_NEW),
                ("show_species signature", P_SP_SIG, P_SP_SIG_NEW),
                ("species stats", P_SP, P_SP_NEW)],
               "_specimens_text")

    ok &= apply(SIDEBAR,
                [("pass sexes to show_order", S_ORDER, S_ORDER_NEW),
                 ("pass sexes to show_superfamily", S_SF, S_SF_NEW),
                 ("pass sexes to show_family", S_FAM, S_FAM_NEW),
                 ("pass sexes to show_species", S_SP, S_SP_NEW)],
                "_sum_sexes(total_species)")

    print("")
    if not ok:
        print("  One or more files unchanged.")
        return 1

    print("  Checking...")
    try:
        import py_compile
        py_compile.compile(PANEL, doraise=True)
        py_compile.compile(SIDEBAR, doraise=True)
        sys.path.insert(0, _ROOT)
        import importlib
        m = importlib.import_module(
            "Observatum.src.views.collection.family_detail_panel")
        importlib.reload(m)
        P = m.FamilyDetailPanel
        cases = [((55, (5, 2, 48)), "55 (\u26425 \u26402 +48)"),
                 ((13, (0, 1, 12)), "13 (\u26401 +12)"),
                 ((7, (0, 0, 7)), "7"),
                 ((7, None), "7"),
                 ((2, (1, 1, 0)), "2 (\u26421 \u26401)")]
        bad = 0
        for (n, sexes), expect in cases:
            got = P._specimens_text(n, sexes)
            if got != expect:
                bad += 1
                print(f"    x ({n}, {sexes}) -> {got!r}, expected {expect!r}")
        if bad:
            print(f"  x {bad} case(s) wrong -- restore from the backups")
            return 1
        print(f"  + compiles, and all {len(cases)} formatting cases correct")
    except Exception as e:  # noqa: BLE001
        print(f"  x FAILED: {type(e).__name__}: {e}")
        print("    restore: copy *.bak_sex back over each file")
        return 1

    print("")
    print("  NEXT: restart Observatum, open the sidebar, click Halictidae.")
    print("  The panel below should read 'Your specimens: 55 (\u26425 \u26402 +48)'.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
