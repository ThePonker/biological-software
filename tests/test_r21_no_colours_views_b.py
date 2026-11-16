"""Round 21 (theme round, step 1), builder B: no colour is written into the UI code of these files.

Every colour the Observatum views (except stats, dialogs, observations, collection, scheme),
Data Entry, shared/*.py, core/config.py and main.py draw comes from the theme (or from
shared.theme_lookup.value(key, fallback)), so a second theme can recolour the program.

Scans the string constants and Qt colour calls of those files for hex colours, rgb()/rgba(),
named colours in style sheets, QColor("...") / QColor(r, g, b) and Qt.GlobalColor colours.
Allowed: theme fallback arguments (`get('key', '#...')`, `value('key', '#...')`), comments and
docstrings, QColor(0, 0, 0, 0) (a fully transparent colour), Qt.GlobalColor.transparent, the map
palette module, the theme_lookup missing-key marker, and lines marked
`# fixed: export colour (R21)` or `# fixed: map colour (R21)`.
"""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIEWS = ROOT / "Observatum" / "src" / "views"
NOT_MINE = [VIEWS / d for d in ("stats", "dialogs", "observations", "collection", "scheme")]
# map colours stay fixed in every theme; the theme_lookup marker is not a UI colour
ALLOWED_FILES = {"Observatum/src/views/mapping/square_style.py"}
ALLOWED_TEXT = {"shared/theme_lookup.py": ("#ff00ff",)}
MARKERS = ("# fixed: export colour (R21)", "# fixed: map colour (R21)")

HEX = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
FUNC = re.compile(r"\brgba?\s*\(|\bhsla?\s*\(")
NAMED = re.compile(r"(?:color|background(?:-color)?|border(?:-[a-z]+)*|outline)\s*:[^;{}]*?"
                   r"\b(white|black|gray|grey|red|green|blue|yellow|orange|purple|pink|brown"
                   r"|cyan|magenta|silver|navy|maroon)\b")
GLOBAL_COLOURS = {"white", "black", "gray", "darkGray", "lightGray", "red", "green", "blue",
                  "cyan", "magenta", "yellow", "darkRed", "darkGreen", "darkBlue", "color0",
                  "color1"}


def _files():
    out = []
    for base in (VIEWS, ROOT / "DataEntry"):
        out += list(base.rglob("*.py"))
    out += list((ROOT / "shared").glob("*.py"))
    out += [ROOT / "Observatum" / "src" / "core" / "config.py",
            ROOT / "Observatum" / "src" / "main.py"]
    keep = []
    for p in out:
        rel = p.relative_to(ROOT).as_posix()
        if {"__pycache__", "_archive"} & set(p.parts) or rel in ALLOWED_FILES:
            continue
        if any(n in p.parents for n in NOT_MINE):
            continue
        keep.append(p)
    return sorted(keep)


def _docstring_nodes(tree):
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                ids.add(id(body[0].value))
    return ids


def _fallback_nodes(tree):
    """String constants that are the fallback of a look-up: f('key', '#colour')."""
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and len(node.args) >= 2:
            a0, a1 = node.args[0], node.args[1]
            if isinstance(a0, ast.Constant) and isinstance(a0.value, str) \
                    and isinstance(a1, ast.Constant) and isinstance(a1.value, str):
                ids.add(id(a1))
    return ids


def _is_number(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, (int, float))


def find_colours(path, root=ROOT):
    rel = path.relative_to(root).as_posix()
    src = path.read_text(encoding="utf-8", errors="replace")
    lines = src.split("\n")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return [f"{rel}:1 does not parse"]
    skip = _docstring_nodes(tree) | _fallback_nodes(tree)
    found = []

    def report(node, what):
        line = lines[node.lineno - 1]
        end = lines[getattr(node, "end_lineno", node.lineno) - 1]
        if any(m in line or m in end for m in MARKERS):
            return
        found.append(f"{rel}:{node.lineno} {what}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            text = node.value
            for allowed in ALLOWED_TEXT.get(rel, ()):
                text = text.replace(allowed, "")
            m = HEX.search(text) or FUNC.search(text) or NAMED.search(text)
            if m:
                report(node, f"colour in a string: {m.group(0)!r}")
        elif isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if name == "QColor" and node.args:
                if all(_is_number(a) for a in node.args):
                    if len(node.args) == 4 and node.args[3].value == 0:
                        continue                                  # fully transparent
                    report(node, "QColor(r, g, b)")
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Attribute) and node.value.attr == "GlobalColor" \
                    and node.attr in GLOBAL_COLOURS:
                report(node, f"Qt.GlobalColor.{node.attr}")
            elif isinstance(node.value, ast.Name) and node.value.id == "Qt" and node.attr in GLOBAL_COLOURS:
                report(node, f"Qt.{node.attr}")
    return found


def test_no_colours_written_into_these_views():
    left = []
    for p in _files():
        left += find_colours(p)
    assert not left, "colours written into the code (use theme()):\n" + "\n".join(left)


def test_the_scan_sees_what_it_should(tmp_path):
    """The scan finds a literal, and passes a fallback, a docstring and a marked line."""
    bad = tmp_path / "bad.py"
    bad.write_text(
        '"""A docstring with #123456."""\n'
        "from PySide6.QtGui import QColor\n"
        "a = 'color: #abcdef;'\n"
        "b = 'color: white;'\n"
        "c = QColor(1, 2, 3)\n"
        "d = t.get('key', '#abcdef')\n"
        "e = '#abcdef'   # fixed: export colour (R21)\n"
        "f = 'background: rgba(1, 2, 3, 0.5)'\n", encoding="utf-8")
    found = find_colours(bad, tmp_path)
    assert [f.split(" ")[0] for f in found] == ["bad.py:3", "bad.py:4", "bad.py:5", "bad.py:8"]
