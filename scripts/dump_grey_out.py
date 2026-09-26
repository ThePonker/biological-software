import io, os, glob, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = os.path.join(ROOT, "grey_out_files.txt")
files = []
for pat in ["Examen/conservation_tab.py", "**/workbook_export.py"]:
    for f in glob.glob(os.path.join(ROOT, pat), recursive=True):
        if "_archive" not in f and ".bak" not in f and f not in files:
            files.append(f)
with io.open(out, "w", encoding="utf-8") as o:
    o.write("=== lines mentioning jurisdiction (Examen/, shared/) ===\n")
    for d in ("Examen", "shared"):
        for f in glob.glob(os.path.join(ROOT, d, "**", "*.py"), recursive=True):
            if ".bak" in f:
                continue
            for i, line in enumerate(io.open(f, encoding="utf-8", errors="replace"), 1):
                if re.search(r"jurisdiction|JURISDICTION", line):
                    o.write(f"{os.path.relpath(f, ROOT)}:{i}: {line.rstrip()}\n")
    for f in files:
        t = io.open(f, encoding="utf-8", errors="replace").read()
        o.write(f"\n{'='*70}\n# {os.path.relpath(f, ROOT)}  ({len(t.splitlines())} lines)\n{'='*70}\n{t}")
        print(f"{len(t.splitlines()):>5}  {os.path.relpath(f, ROOT)}")
print(f"-> {out}")
