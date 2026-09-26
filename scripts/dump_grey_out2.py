import io, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = os.path.join(ROOT, "grey_out_files2.txt")
with io.open(out, "w", encoding="utf-8") as o:
    p = os.path.join(ROOT, "shared", "repositories", "codex_repository.py")
    lines = io.open(p, encoding="utf-8", errors="replace").read().splitlines()
    o.write("=== codex_repository.py lines 90-175 ===\n")
    for i in range(89, min(175, len(lines))):
        o.write(f"{i+1:5}: {lines[i]}\n")
    o.write("\n=== codex_repository.py lines 225-260 (priority labels) ===\n")
    for i in range(224, min(260, len(lines))):
        o.write(f"{i+1:5}: {lines[i]}\n")
    o.write("\n=== codex_repository.py _classify (880-945) ===\n")
    for i in range(879, min(945, len(lines))):
        o.write(f"{i+1:5}: {lines[i]}\n")
    s = os.path.join(ROOT, "shared", "services", "pantheon_analysis_service.py")
    o.write("\n=== pantheon_analysis_service.py: key-species entry + priority/legal ===\n")
    for i, line in enumerate(io.open(s, encoding="utf-8", errors="replace"), 1):
        if re.search(r"priority|legal|class KeySpeciesEntry|KeySpeciesEntry\(", line):
            o.write(f"{i:5}: {line.rstrip()}\n")
print(f"-> {out}")
