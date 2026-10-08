"""Bundle the committed source code into plain-text files for analysis.

Uses `git ls-files`, so only committed source is included -- never data, databases,
backups, archives or .bak files. Each file is preceded by a marker line
    ===== FILE: <path> | lines <n> | sha1 <hash> =====
so it can be reconstructed exactly.

Writes to your Downloads folder:
    biosoft_app_1.txt, _2 ...       application code (everything except scripts/), ~3 MB per part
    biosoft_scripts_1.txt, ...      the scripts/ folder (one-off patches and checks)
    biosoft_manifest.txt            every file, its line count, hash and part

  python scripts\\make_source_bundle.py
  python scripts\\make_source_bundle.py --out _archive\\_dump_20261008
"""
import hashlib, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(os.path.expanduser("~"), "Downloads")
if "--out" in sys.argv:          # e.g. --out _archive\_dump_20261008 (a folder Claude can read)
    OUT = os.path.abspath(os.path.join(ROOT, sys.argv[sys.argv.index("--out") + 1]))
os.makedirs(OUT, exist_ok=True)
PART_BYTES = 3_000_000
TEXT_EXT = {".py", ".md", ".txt", ".bat", ".ps1", ".json", ".toml", ".cfg", ".ini", ".sql", ".qss", ".yml", ".yaml"}
SKIP_EXT = {".bak"}

files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
groups = {"app": [], "scripts": []}
skipped = []
for f in files:
    ext = os.path.splitext(f)[1].lower()
    if ext in SKIP_EXT or ext not in TEXT_EXT or f.lower().startswith(("data/", "_archive/", "_backups/")):
        skipped.append(f); continue
    groups["scripts" if f.startswith("scripts/") else "app"].append(f)

manifest = ["path\tlines\tbytes\tsha1\tpart"]
for g, fl in groups.items():
    part, size, buf, n = 1, 0, [], 0

    def flush(final=False):
        global part, size, buf
        if buf:
            with open(os.path.join(OUT, f"biosoft_{g}_{part}.txt"), "w", encoding="utf-8", newline="\n") as fh:
                fh.write("".join(buf))
            part += 1; size = 0; buf = []

    for f in sorted(fl):
        try:
            raw = open(os.path.join(ROOT, f), "rb").read()
        except OSError as e:
            skipped.append(f"{f} ({e})"); continue
        txt = raw.decode("utf-8", errors="replace").replace("\r\n", "\n")
        lines = txt.count("\n") + (0 if txt.endswith("\n") or not txt else 1)
        sha = hashlib.sha1(raw).hexdigest()[:12]
        block = f"===== FILE: {f} | lines {lines} | sha1 {sha} =====\n{txt}\n" + ("" if txt.endswith("\n") else "\n")
        if size and size + len(block.encode("utf-8")) > PART_BYTES:
            flush()
        buf.append(block); size += len(block.encode("utf-8"))
        manifest.append(f"{f}\t{lines}\t{len(raw)}\t{sha}\t{g}_{part}")
        n += 1
    flush()
    print(f"  {g}: {n} files -> biosoft_{g}_1..{part - 1}.txt")

with open(os.path.join(OUT, "biosoft_manifest.txt"), "w", encoding="utf-8", newline="\n") as fh:
    fh.write("\n".join(manifest) + "\n")
tot = sum(int(l.split("\t")[1]) for l in manifest[1:])
print(f"  manifest: {len(manifest) - 1} files, {tot:,} lines -> biosoft_manifest.txt")
print(f"  skipped (non-text, .bak, data): {len(skipped)}")
print(f"  all written to {OUT}")
for p in sorted(x for x in os.listdir(OUT) if x.startswith("biosoft_")):
    print(f"      {p:28} {os.path.getsize(os.path.join(OUT, p)) / 1e6:6.2f} MB")
