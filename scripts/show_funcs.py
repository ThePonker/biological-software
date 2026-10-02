"""Print named functions / classes from a Python file, in full, with line numbers.
READ ONLY.

  python scripts\\show_funcs.py <file> <name> [<name> ...]
  python scripts\\show_funcs.py <file> --grep <regex>      (matching lines only)
  python scripts\\show_funcs.py <file> --list              (every def/class)

Several files: separate groups with "::"
  python scripts\\show_funcs.py a.py f1 f2 :: b.py g1 :: c.py --grep sqs
"""
import ast, io, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def show(path, args):
    p = path if os.path.isabs(path) else os.path.join(ROOT, path)
    if not os.path.exists(p):
        print(f"\n### {path}: not found")
        return
    src = io.open(p, encoding="utf-8-sig", errors="replace").read()
    lines = src.splitlines()
    print(f"\n### {os.path.relpath(p, ROOT)}  ({len(lines)} lines)")
    if args[:1] == ["--grep"]:
        pat = re.compile(args[1])
        for i, l in enumerate(lines, 1):
            if pat.search(l):
                print(f"{i:5}: {l}")
        return
    tree = ast.parse(src.replace("\r", ""))
    nodes = [n for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    if args[:1] == ["--list"]:
        for n in sorted(nodes, key=lambda n: n.lineno):
            kind = "class" if isinstance(n, ast.ClassDef) else "def"
            print(f"{n.lineno:5}-{n.end_lineno:<5} {kind} {n.name}")
        return
    for name in args:
        hits = [n for n in nodes if n.name == name]
        if not hits:
            print(f"\n--- {name}: not found")
        for n in hits:
            print(f"\n--- {name}  (lines {n.lineno}-{n.end_lineno})")
            start = n.lineno - 1 - len(n.decorator_list)
            for i in range(start, n.end_lineno):
                print(f"{i + 1:5}: {lines[i]}")


groups, cur = [], []
for a in sys.argv[1:]:
    if a == "::":
        groups.append(cur); cur = []
    else:
        cur.append(a)
groups.append(cur)
for g in groups:
    if g:
        show(g[0], g[1:])
print("\nREAD ONLY -- nothing has been changed.")
