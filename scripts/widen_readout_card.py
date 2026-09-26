import io, os, shutil, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(ROOT, "DataEntry", "info_panel.py")

OLD = "readout_w.setFixedWidth(272)"
NEW = ("readout_w.setFixedWidth(316)   # 272 was too narrow once the specimen\n"
       "        # pill gained its sex breakdown -- 'Spec. 12 (F1 +11)' clipped.")

t = io.open(p, encoding="utf-8").read()
if "316" in t and OLD not in t:
    print("already widened"); sys.exit(0)
n = t.count(OLD)
print("anchor matches:", n)
if n != 1:
    print("NOTHING WRITTEN"); sys.exit(1)
shutil.copy2(p, p + ".bak_width")
io.open(p, "w", encoding="utf-8", newline="").write(t.replace(OLD, NEW))
import py_compile; py_compile.compile(p, doraise=True)
print("widened to 316 and compiles cleanly")
