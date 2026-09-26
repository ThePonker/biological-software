import io, os, shutil, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(ROOT, "Observatum", "src", "views", "collection",
                 "taxonomic_sidebar.py")

OLD = '''                    sf_item = QTreeWidgetItem(order_item, [f"{sf_name} ({sf_count})"])'''
NEW = '''                    sf_species = {s for fam in families.values() for s in fam}
                    sf_item = QTreeWidgetItem(
                        order_item,
                        [self._node_label(sf_name, sf_count, sf_species)])'''

t = io.open(p, encoding="utf-8").read()
if "sf_species" in t:
    print("already patched"); sys.exit(0)
n = t.count(OLD)
print("anchor matches:", n)
if n != 1:
    print("NOTHING WRITTEN"); sys.exit(1)
shutil.copy2(p, p + ".bak_sfsex")
io.open(p, "w", encoding="utf-8", newline="").write(t.replace(OLD, NEW))
import py_compile; py_compile.compile(p, doraise=True)
print("superfamily nodes now carry the breakdown; compiles cleanly")
