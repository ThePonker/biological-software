"""Examen: order, family and common name in every export -- from ONE lookup.

Fault: SiteSpecies had no order/family/common-name fields, so the workbook's
appendix sheet (and order/common on its key-species sheet) came out blank. The
same UKSI lookup was written separately in the Species tab and appendix_export.

  examen_data.py         + load_taxonomy(tvks) -- the one lookup
                         + SiteSpecies.order_name / family / common_name,
                           filled in _build_species_list
  site_analysis_view.py  _load_taxonomy() delegates to load_taxonomy
  appendix_export.py     its lookup function delegates to load_taxonomy
  workbook_export.py     key-species sheet takes order/family/common from it

Functions are located by parsing. All four files are planned first; NOTHING is
written unless every anchor is found exactly once. Backups: *.bak_tax. If any
file fails to compile or import, all four are restored. Then a real project's
species list is printed to show the fields filled.

Run:  python scripts\\patch_examen_taxonomy.py
"""
import ast, importlib, io, os, py_compile, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "Observatum"))
EX = os.path.join(ROOT, "Examen")

print("Examen -- one taxonomy lookup; order/family/common in every export")
print("=" * 76)


class F:
    def __init__(self, name):
        self.path = os.path.join(EX, name)
        raw = io.open(self.path, "rb").read()
        self.bom = raw.startswith(b"\xef\xbb\xbf")
        self.lines = raw.decode("utf-8-sig").split("\n")
        self.tree = ast.parse("\n".join(l.rstrip("\r") for l in self.lines))
        self.edits = []                     # (start, end_inclusive, new_lines)

    def eol(self, i):
        return "\r" if self.lines[i].endswith("\r") else ""

    def ind(self, i):
        s = self.lines[i].rstrip("\r")
        return s[:len(s) - len(s.lstrip())]

    def blk(self, i, body, ind=None):
        ind = self.ind(i) if ind is None else ind
        return [(ind + b if b else "") + self.eol(i) for b in body.split("\n")]

    def func(self, name):
        hits = [n for n in ast.walk(self.tree)
                if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == name]
        return hits[0] if len(hits) == 1 else None

    def find(self, node, s):
        return [i for i in range(node.lineno - 1, node.end_lineno)
                if self.lines[i].strip().rstrip("\r") == s]

    def write(self):
        for s, e, new in sorted(self.edits, key=lambda t: -t[0]):
            self.lines[s:e + 1] = new
        shutil.copy2(self.path, self.path + ".bak_tax")
        io.open(self.path, "w", encoding="utf-8-sig" if self.bom else "utf-8",
                newline="").write("\n".join(self.lines))

    def restore(self):
        if os.path.exists(self.path + ".bak_tax"):
            shutil.copy2(self.path + ".bak_tax", self.path)


problems = []


def need(cond, msg):
    if not cond:
        problems.append(msg)
    return cond


# ------------------------------------------------------------------ examen_data
ed = F("examen_data.py")
src = "\n".join(ed.lines)
need("def load_taxonomy" not in src, "examen_data already has load_taxonomy -- patched?")
cls, bsl = ed.func("SiteSpecies"), ed.func("_build_species_list")
if need(cls is not None, "class SiteSpecies not found") and \
        need(bsl is not None, "_build_species_list not found"):
    last = cls.end_lineno - 1                       # last field line of the dataclass
    need("habitat" in ed.lines[last], f"SiteSpecies does not end with habitat: {ed.lines[last]!r}")
    ed.edits.append((last, last, [ed.lines[last]] + ed.blk(last,
        'order_name: str = ""\nfamily: str = ""\ncommon_name: str = ""')))

    a = ed.find(bsl, "ecology = _load_pantheon_ecology(tvks)")
    b = ed.find(bsl, 'pd = ecology.get(tvk, {})')
    c = ed.find(bsl, 'broad_biotope=pd.get("biotope", ""), habitat=pd.get("habitat", "")))')
    if need(len(a) == 1 and len(b) == 1 and len(c) == 1,
            f"_build_species_list anchors: ecology x{len(a)}, pd x{len(b)}, SiteSpecies( close x{len(c)}"):
        ed.edits.append((a[0], a[0], [ed.lines[a[0]]] + ed.blk(a[0], "taxonomy = load_taxonomy(tvks)")))
        ed.edits.append((b[0], b[0], [ed.lines[b[0]]] + ed.blk(b[0], "tx = taxonomy.get(tvk, {})")))
        ed.edits.append((c[0], c[0], ed.blk(c[0],
            'broad_biotope=pd.get("biotope", ""), habitat=pd.get("habitat", ""),\n'
            'order_name=tx.get("order", ""), family=tx.get("family", ""),\n'
            'common_name=tx.get("common", "")))')))
    i = bsl.lineno - 1
    ed.edits.append((i, i, ed.blk(i, '''def load_taxonomy(tvks):
    """{tvk: {'common', 'family', 'order'}} from UKSI.

    The one lookup: the species list, the Species tab and every export use it.
    """
    import paths
    tvks = [t for t in dict.fromkeys(tvks) if t]
    if not tvks or not paths.UKSI_DB.exists():
        return {}
    out = {}
    conn = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
    try:
        for i in range(0, len(tvks), 500):
            batch = tvks[i:i + 500]
            ph = ",".join("?" * len(batch))
            for t, cn, fam, order in conn.execute(
                    "SELECT t.tvk, COALESCE(cn.common_name, ''), COALESCE(t.family, ''), "
                    'COALESCE(t."order", \\'\\') FROM taxa t LEFT JOIN common_names cn '
                    f"ON t.tvk = cn.tvk AND cn.preferred = 1 WHERE t.tvk IN ({ph})", batch):
                out[t] = {"common": cn, "family": fam, "order": order}
    finally:
        conn.close()
    return out

''', ind="") + [ed.lines[i]]))

# ------------------------------------------------------------------ site_analysis_view
sv = F("site_analysis_view.py")
lt = sv.func("_load_taxonomy")
if need(lt is not None, "_load_taxonomy not found in site_analysis_view"):
    s, e = lt.lineno - 1, lt.end_lineno - 1
    sv.edits.append((s, e, sv.blk(s, '''def _load_taxonomy(self, tvks):
    """Delegates to examen_data.load_taxonomy -- one lookup for tab and exports."""
    from .examen_data import load_taxonomy
    return load_taxonomy(tvks)''')))

# ------------------------------------------------------------------ appendix_export
ax = F("appendix_export.py")
afn = [n for n in ast.walk(ax.tree) if isinstance(n, ast.FunctionDef)
       and (ast.get_docstring(n) or "").startswith("Look up common_name, family, order")]
if need(len(afn) == 1, f"appendix_export lookup function found {len(afn)} times"):
    n = afn[0]
    params = [x.arg for x in n.args.args if x.arg != "self"]
    if need(len(params) == 1, f"appendix_export lookup has params {params}; expected one"):
        s, e = n.lineno - 1, n.end_lineno - 1
        defline = ax.lines[s].rstrip("\r").strip()
        ax.edits.append((s, e, ax.blk(s, f'''{defline}
    """Look up common_name, family, order for each TVK -- via examen_data.load_taxonomy."""
    from .examen_data import load_taxonomy
    return load_taxonomy(list({params[0]} or []))''')))

# ------------------------------------------------------------------ workbook_export
wb = F("workbook_export.py")
wsrc = "\n".join(wb.lines)
REPL = [('getattr(k, "order_name", "") or ""', 'getattr(k, "order_name", "") or _taxon(k).get("order", "")'),
        ('k.family or ""', 'k.family or _taxon(k).get("family", "")'),
        ('getattr(k, "common_name", "") or ""', 'getattr(k, "common_name", "") or _taxon(k).get("common", "")')]
for old, new in REPL:
    hits = [i for i, l in enumerate(wb.lines) if old in l]
    if need(len(hits) == 1, f"workbook_export: {old!r} found {len(hits)} times"):
        i = hits[0]
        wb.edits.append((i, i, [wb.lines[i].replace(old, new)]))
first_def = min((n.lineno for n in wb.tree.body if isinstance(n, ast.FunctionDef)), default=None)
if need(first_def is not None, "workbook_export: no top-level function"):
    i = first_def - 1
    wb.edits.append((i, i, wb.blk(i, '''_TAX_CACHE = {}


def _taxon(k):
    """Order/family/common for a key-species entry, from examen_data.load_taxonomy."""
    tvk = getattr(k, "tvk", "") or ""
    if tvk and tvk not in _TAX_CACHE:
        try:
            from Examen.examen_data import load_taxonomy
        except ImportError:
            from examen_data import load_taxonomy
        _TAX_CACHE.update(load_taxonomy([tvk]))
    return _TAX_CACHE.get(tvk, {})

''', ind="") + [wb.lines[i]]))

# ------------------------------------------------------------------ guard / write
for f in (ed, sv, ax, wb):
    print(f"  {os.path.basename(f.path):<24} edits planned: {len(f.edits)}")
if problems:
    print()
    for p in problems:
        print(f"  x {p}")
    sys.exit("\nABORTED -- nothing written.")

files = (ed, sv, ax, wb)
for f in files:
    f.write()
print("  + written (backups: *.bak_tax)")

try:
    for f in files:
        py_compile.compile(f.path, doraise=True)
    for m in ("Examen.examen_data", "Examen.appendix_export", "Examen.workbook_export"):
        importlib.import_module(m)
    print("  ok all four compile; examen_data, appendix_export, workbook_export import")
except Exception as e:
    for f in files:
        f.restore()
    sys.exit(f"  x FAILED ({type(e).__name__}: {e}) -- all four restored")

# ------------------------------------------------------------------ proof
from Examen import examen_data as exd
d = exd.load_project_detail("Birmingham - Wheels Park", "", survey_year="2026")
if d:
    sl = d.species_list
    filled = sum(1 for s in sl if s.tvk and s.order_name and s.family)
    common = sum(1 for s in sl if s.tvk and s.common_name)
    print(f"\n  Birmingham - Wheels Park 2026: {len(sl)} species; "
          f"order+family filled {filled}, common name {common}")
    for s in sl[:6]:
        print(f"    {s.name[:30]:30} {s.order_name[:14]:14} {s.family[:18]:18} {s.common_name[:26]}")
print("\nDone. Export Workbook and Export Appendix for Birmingham to check.")
