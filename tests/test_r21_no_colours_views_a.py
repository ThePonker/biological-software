"""Round 21 step 1 (builder A): no colour is written into the views' UI code; it comes from theme().

Scans the Python files of given folders for colours written directly in the code:
  * hex literals (#rgb, #rrggbb, #aarrggbb) in strings,
  * named colours (white, black, gray ...) and rgb()/rgba() in stylesheet strings,
  * QColor("...") / QColor(r, g, b) built from literals,
  * Qt.GlobalColor.<name> / Qt.<name> colours (transparent is not a colour).
Not counted: comments, docstrings, the fallback argument of a .get(key, fallback) call, and any
line marked `# fixed: export colour (R21)` (a colour that goes into an exported file and stays
the same in every theme).

`find_colour_literals(folders, allow)` is written to be widened to other folders later:
`allow` is a list of "relative/path.py" (whole file) or "relative/path.py:LINE" entries,
relative to `root` (the repository root by default).
"""
import ast
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "Observatum" / "src"

# Builder A's folders (R21 step 1)
FOLDERS_A = [
    SRC / "views" / "stats",
    SRC / "views" / "dialogs",
    SRC / "views" / "observations",
    SRC / "views" / "collection",
    SRC / "views" / "scheme",
]

MARKER = "# fixed: export colour (R21)"

_HEX = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-zA-Z_])")
_NAMES = (r"white|black|gr[ae]y|darkgr[ae]y|lightgr[ae]y|red|green|blue|orange|yellow|purple|pink|"
          r"brown|cyan|magenta|navy|teal|maroon|silver|gold|crimson")
_PROPS = (r"(?:color|background|background-color|border|border-color|border-top|border-bottom|"
          r"border-left|border-right|outline|selection-color|selection-background-color|"
          r"gridline-color|alternate-background-color)")
_NAMED = re.compile(r"(?<![\w-])" + _PROPS + r"\s*:[^;{}\"]*?(?<![\w#-])(" + _NAMES + r")(?![\w-])")
_RGB = re.compile(r"\brgba?\s*\(")
_GLOBAL = re.compile(r"^(?:Qt|QtCore\.Qt)\.(?:GlobalColor\.)?([A-Za-z]+)$")
_QT_COLOUR_NAMES = {"white", "black", "red", "green", "blue", "gray", "lightGray", "darkGray",
                    "yellow", "cyan", "magenta", "darkRed", "darkGreen", "darkBlue", "darkCyan",
                    "darkMagenta", "darkYellow"}


def _docstring_nodes(tree):
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                out.add(id(body[0].value))
    return out


def _fallback_nodes(tree):
    """Everything inside the 2nd+ argument of a `.get(key, fallback)` call."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "get" and len(node.args) >= 2:
            for a in node.args[1:]:
                for sub in ast.walk(a):
                    out.add(id(sub))
    return out


def _is_qcolor_call(node):
    f = node.func
    return (isinstance(f, ast.Name) and f.id == "QColor") or \
           (isinstance(f, ast.Attribute) and f.attr == "QColor")


def _scan_file(path: Path):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [(1, "could not parse")]
    skip = _docstring_nodes(tree) | _fallback_nodes(tree)
    found = []

    def marked(lo, hi):
        return any(MARKER in lines[i - 1] for i in range(lo, min(hi, len(lines)) + 1))

    for node in ast.walk(tree):
        if id(node) in skip:
            continue
        lo = getattr(node, "lineno", 0)
        hi = getattr(node, "end_lineno", lo)
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            s = node.value
            hits = [(m.start(), m.group(0)) for m in _HEX.finditer(s)]
            hits += [(m.start(), m.group(1)) for m in _NAMED.finditer(s)]
            hits += [(m.start(), m.group(0)) for m in _RGB.finditer(s)]
            for off, what in hits:
                line = lo + s.count("\n", 0, off)
                if not marked(line, line) and not marked(lo, lo):
                    found.append((line, what))
        elif isinstance(node, ast.Call) and _is_qcolor_call(node) and node.args:
            a0 = node.args[0]
            literal = isinstance(a0, ast.Constant) and isinstance(a0.value, (str, int)) \
                and not isinstance(a0.value, bool)
            if literal and not marked(lo, hi):
                found.append((lo, "QColor(literal)"))
        elif isinstance(node, ast.Attribute):
            try:
                dotted = ast.unparse(node)
            except Exception:
                continue
            m = _GLOBAL.match(dotted)
            if m and m.group(1) in _QT_COLOUR_NAMES and not marked(lo, hi):
                found.append((lo, dotted))
    return sorted(set(found))


def find_colour_literals(folders, allow=(), root=ROOT):
    """['relative/path.py:LINE: what', ...] for every written-in colour left in `folders`."""
    allow = set(allow)
    root = Path(root)
    out = []
    for folder in folders:
        for dirpath, dirnames, filenames in os.walk(folder):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for fn in sorted(filenames):
                if not fn.endswith(".py"):
                    continue
                p = Path(dirpath) / fn
                rel = p.relative_to(root).as_posix()
                if rel in allow:
                    continue
                for line, what in _scan_file(p):
                    if f"{rel}:{line}" not in allow:
                        out.append(f"{rel}:{line}: {what}")
    return out


def test_views_a_have_no_written_in_colours():
    left = find_colour_literals(FOLDERS_A)
    assert not left, "colours written into the code (use theme()):\n" + "\n".join(left)


def test_scanner_finds_what_it_should(tmp_path):
    """The scanner itself: catches hex, named, rgba and QColor("..."); passes fallbacks,
    comments, docstrings and marked export colours."""
    bad = tmp_path / "bad"
    good = tmp_path / "good"
    bad.mkdir()
    good.mkdir()
    (bad / "bad.py").write_text(
        '"""doc #ffffff"""\n'
        "from PySide6.QtGui import QColor\n"
        "a = 'color: #4a7c59;'\n"
        "b = f'''\nQFrame {{ color: white; }}\n'''\n"
        "c = QColor('#e8f0ea')\n"
        "d = 'x: rgba(255, 255, 255, 0.8)'\n"
        "e = Qt.GlobalColor.darkGreen\n"
        "f = QColor(1, 2, 3)\n", encoding="utf-8")
    (good / "good.py").write_text(
        '"""doc #ffffff"""\n'
        "t = {}\n"
        "# a comment #4a7c59\n"
        "a = t.get('primary', '#4a7c59')\n"
        "b = 'background: transparent;'\n"
        "c = '#c0ffee'  # fixed: export colour (R21)\n"
        "d = QColor(t.get('primary'))\n"
        "e = 'Record number 5, row 12'\n", encoding="utf-8")
    joined = "\n".join(find_colour_literals([bad], root=tmp_path))
    for line in (3, 5, 7, 8, 9, 10):
        assert f"bad.py:{line}:" in joined, joined
    assert find_colour_literals([good], root=tmp_path) == []
    # an allow list silences one line or a whole file
    assert "bad/bad.py:3:" not in "\n".join(
        find_colour_literals([bad], allow=["bad/bad.py:3"], root=tmp_path))
    assert find_colour_literals([bad], allow=["bad/bad.py"], root=tmp_path) == []
