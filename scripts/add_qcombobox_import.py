import io, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(ROOT, "Examen", "site_analysis_view.py")
t = io.open(p, encoding="utf-8").read()

head = t.split("class ")[0]
if "QComboBox" in head:
    print("already imported"); sys.exit(0)

OLD = "QInputDialog, QCheckBox,"
n = t.count(OLD)
print("anchor matches:", n)
if n != 1:
    print("NOTHING WRITTEN -- paste the PySide6.QtWidgets import block")
    sys.exit(1)
io.open(p, "w", encoding="utf-8", newline="").write(
    t.replace(OLD, "QInputDialog, QCheckBox, QComboBox,", 1))
print("QComboBox added to the imports")
