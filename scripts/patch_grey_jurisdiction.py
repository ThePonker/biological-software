"""Grey out other jurisdictions' designations -- Conservation tab + workbook.

  Examen/conservation_tab.py   full replacement (guarded: aborts if the file on
                               disk is not the version reviewed)
  Examen/workbook_export.py    six anchored edits

Both files backed up as *.bak_grey first. Nothing is written unless every
guard and anchor passes.

Run:  python scripts\\patch_grey_jurisdiction.py
Undo: copy each *.bak_grey back over its file.
"""
import hashlib, io, os, py_compile, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CT = os.path.join(ROOT, "Examen", "conservation_tab.py")
WB = os.path.join(ROOT, "Examen", "workbook_export.py")

CT_EXPECTED_SHA = "5f2a575ec761a0a1b7fd1a553976fa1472ff837ed4d44094de11edd9c043e954"

CT_NEW = '"""\nExamen — Conservation Tab\n\nConservation status breakdown by category. Shows counts for each\nstatus level (NR, NS, Na, Nb, CR, EN, VU, NT, S41, etc.) with\nvisual bars.\n"""\n\nfrom PySide6.QtWidgets import (\n    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,\n    QGridLayout,\n)\nfrom PySide6.QtCore import Qt\nfrom PySide6.QtGui import QFont\n\n# Which designations count in which jurisdiction is decided in ONE place --\n# CodexRepository, the same functions _classify uses for the key-species count.\n# The tab calls them rather than keeping its own list, so the display can never\n# disagree with the number above it.\ntry:\n    from shared.repositories.codex_repository import (\n        _priority_applies, _legal_applies, StatusEntry)\nexcept ImportError:  # pragma: no cover -- degrade to "everything applies"\n    _priority_applies = None\n    _legal_applies = None\n    StatusEntry = None\n\n\ndef _priority_ok(value, jurisdiction):\n    if _priority_applies is None:\n        return True\n    return _priority_applies(value, jurisdiction)\n\n\ndef _legal_ok(text, jurisdiction):\n    # KeySpeciesEntry.legal holds (detail or value); rebuild a StatusEntry so\n    # _legal_applies sees exactly what _classify saw.\n    if _legal_applies is None or StatusEntry is None:\n        return True\n    return _legal_applies(StatusEntry(value=text, detail=text), jurisdiction)\n\nBG = "#f5f5f4"; SURFACE = "#ffffff"; TEXT_PRIMARY = "#1f2937"; TEXT_HEADING = "#4b5563"\nTEXT_SECONDARY = "#6b7280"; TEXT_MUTED = "#9ca3af"; BORDER = "#d1d5db"; SEPARATOR = "#e5e7eb"\nMOSS_GREEN = "#4a7c59"; ACCENT_DARK = "#5a4d78"; RED_STATUS = "#a63d40"; AMBER = "#c2956e"\n# Designations from another jurisdiction: shown for completeness, greyed because\n# they do not count towards key species here.\nNA_TEXT = TEXT_MUTED; NA_BAR = "#d9dce1"\n\n# Status categories in display order.\n# Threat and rarity codes are fixed vocabularies. Priority jurisdictions and\n# legal instruments are open sets -- whatever Codex holds is shown -- so they\n# are handled separately below rather than listed here.\nCATEGORIES = [\n    ("Threat status (GB, 2001 IUCN)", [\n        ("CR", "Critically Endangered", RED_STATUS),\n        ("EN", "Endangered", RED_STATUS),\n        ("VU", "Vulnerable", "#d97706"),\n        ("NT", "Near Threatened", AMBER),\n        ("DD", "Data Deficient", AMBER),\n    ]),\n    ("Threat status (pre-2001)", [\n        ("RDB1", "Red Data Book 1", RED_STATUS),\n        ("RDB2", "Red Data Book 2", RED_STATUS),\n        ("RDB3", "Red Data Book 3", AMBER),\n        ("RDBK", "Red Data Book K", AMBER),\n    ]),\n    ("Rarity (current)", [\n        ("NR", "Nationally Rare", RED_STATUS),\n        ("NS", "Nationally Scarce", AMBER),\n    ]),\n    ("Rarity (legacy)", [\n        ("Na", "Notable A", AMBER),\n        ("Nb", "Notable B", "#92774e"),\n        ("Notable", "Notable", "#92774e"),\n    ]),\n]\n\nPRIORITY_GROUP = "Priority listings"\nLEGAL_GROUP = "Legal protection"\n\nclass ConservationTab(QWidget):\n\n    def __init__(self, parent=None):\n        super().__init__(parent)\n        self._layout = QVBoxLayout(self)\n        self._layout.setContentsMargins(8, 12, 8, 8)\n        self._layout.setSpacing(12)\n        self._widgets = []\n        self._juris = "England"\n\n    def set_result(self, result, detail=None):\n        for w in self._widgets:\n            w.deleteLater()\n        self._widgets.clear()\n\n        # Counts come from the structured tracks on each key species, not from\n        # parsing a display string. Priority jurisdictions and legal instruments\n        # are counted under their own names.\n        status_counts = {}\n        priority_counts = {}\n        legal_counts = {}\n        for k in result.key_species:\n            for code in (getattr(k, "rarity", ""), getattr(k, "threat", ""),\n                         getattr(k, "threat_legacy", "")):\n                if code:\n                    status_counts[code] = status_counts.get(code, 0) + 1\n            for j in getattr(k, "priority", None) or []:\n                priority_counts[j] = priority_counts.get(j, 0) + 1\n            for inst in getattr(k, "legal", None) or []:\n                legal_counts[inst] = legal_counts.get(inst, 0) + 1\n\n        juris = getattr(result, "jurisdiction", None) or "England"\n        self._juris = juris\n\n        total_key = result.key_species_count\n        total_species = result.total_species\n\n        hdr = QLabel(f"{total_key} key species of {total_species} total "\n                      f"({result.key_species_pct}%)")\n        hdr.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))\n        hdr.setStyleSheet("color: " + ACCENT_DARK + ";")\n        self._layout.insertWidget(self._layout.count(), hdr)\n        self._widgets.append(hdr)\n\n        for group_name, statuses in CATEGORIES:\n            rows = [(code, label, colour, status_counts.get(code, 0))\n                    for code, label, colour in statuses]\n            rows = [r for r in rows if r[3] > 0]\n            if rows:\n                self._add_group(group_name, rows)\n\n        # Open-set groups. Designations that apply in this jurisdiction first,\n        # most frequent first; other jurisdictions\' designations after, greyed.\n        if priority_counts:\n            rows = [(self._abbrev(j), j, MOSS_GREEN, n, _priority_ok(j, juris))\n                    for j, n in priority_counts.items()]\n            rows.sort(key=lambda r: (not r[4], -r[3]))\n            self._add_group(PRIORITY_GROUP, rows)\n        if legal_counts:\n            rows = [("", inst, ACCENT_DARK, n, _legal_ok(inst, juris))\n                    for inst, n in legal_counts.items()]\n            rows.sort(key=lambda r: (not r[4], -r[3]))\n            self._add_group(LEGAL_GROUP, rows)\n\n        self._add_guilds(result)\n\n    @staticmethod\n    def _abbrev(jurisdiction):\n        """Short code for a priority jurisdiction, for the left-hand column."""\n        j = (jurisdiction or "").lower()\n        if "s.41" in j or "s41" in j or "section 41" in j:\n            return "S41"\n        if "wales" in j or "s7" in j:\n            return "S7"\n        if "scottish" in j:\n            return "SBL"\n        if "northern ireland" in j or j.startswith("ni "):\n            return "NI"\n        if "bap" in j:\n            return "BAP"\n        return ""\n\n    def _add_group(self, group_name, rows):\n        grp = QFrame()\n        grp.setStyleSheet("QFrame { background: " + SURFACE + "; border: 1px solid "\n                           + BORDER + "; border-radius: 6px; }")\n        gl = QVBoxLayout(grp); gl.setContentsMargins(12, 10, 12, 10); gl.setSpacing(6)\n\n        title = QLabel(group_name)\n        title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))\n        title.setStyleSheet("color: " + TEXT_HEADING + "; border: none;")\n        gl.addWidget(title)\n\n        # Bars are scaled against the largest count in this group, so the\n        # lengths mean something. Previously count * 40 capped at 200, which\n        # filled the bar for anything over five species.\n        peak = max(r[3] for r in rows) or 1\n\n        any_na = False\n        for r in rows:\n            code, label, colour, count = r[:4]\n            applies = r[4] if len(r) > 4 else True\n            bar_colour = colour\n            if not applies:\n                any_na = True\n                colour, bar_colour = NA_TEXT, NA_BAR\n                label = f"{label} \\u2014 not applicable in {self._juris}"\n            row = QHBoxLayout(); row.setSpacing(8)\n\n            code_lbl = QLabel(code)\n            code_lbl.setFixedWidth(50)\n            code_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))\n            code_lbl.setStyleSheet(f"color: {colour}; border: none;")\n            row.addWidget(code_lbl)\n\n            desc_lbl = QLabel(label)\n            desc_lbl.setFixedWidth(200)\n            desc_lbl.setWordWrap(True)\n            desc_lbl.setStyleSheet("color: " + (TEXT_SECONDARY if applies else NA_TEXT)\n                                   + "; font-size: 11px; border: none;"\n                                   + ("" if applies else " font-style: italic;"))\n            row.addWidget(desc_lbl)\n\n            bar_container = QFrame()\n            bar_container.setFixedHeight(18)\n            bar_container.setStyleSheet("background: " + BG + "; border-radius: 3px; border: none;")\n            bar = QFrame(bar_container)\n            bar.setFixedSize(max(6, int(200 * count / peak)), 18)\n            bar.setStyleSheet(f"background: {bar_colour}; border-radius: 3px;")\n            row.addWidget(bar_container, 1)\n\n            count_lbl = QLabel(str(count))\n            count_lbl.setFixedWidth(30)\n            count_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))\n            count_lbl.setStyleSheet(f"color: {colour}; border: none;")\n            count_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)\n            row.addWidget(count_lbl)\n\n            gl.addLayout(row)\n\n        if any_na:\n            note = QLabel("Greyed designations apply in another jurisdiction. "\n                          "They are shown for completeness and do not count "\n                          f"towards key species under {self._juris}.")\n            note.setWordWrap(True)\n            note.setStyleSheet("color: " + NA_TEXT + "; font-size: 10px; "\n                               "font-style: italic; border: none;")\n            gl.addWidget(note)\n\n        self._layout.insertWidget(self._layout.count(), grp)\n        self._widgets.append(grp)\n\n    def _add_guilds(self, result):\n        if not (result.larval_guild_counts or result.adult_guild_counts):\n            return\n        guild_frame = QFrame()\n        guild_frame.setStyleSheet("QFrame { background: " + SURFACE + "; border: 1px solid "\n                                   + BORDER + "; border-radius: 6px; }")\n        gfl = QVBoxLayout(guild_frame); gfl.setContentsMargins(12, 10, 12, 10); gfl.setSpacing(4)\n        gt = QLabel("Feeding guilds")\n        gt.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))\n        gt.setStyleSheet("color: " + TEXT_HEADING + "; border: none;")\n        gfl.addWidget(gt)\n\n        for label, counts in [("Larval", result.larval_guild_counts),\n                               ("Adult", result.adult_guild_counts)]:\n            if counts:\n                top = sorted(counts.items(), key=lambda x: -x[1])[:6]\n                text = f"{label}: " + ", ".join(f"{k} ({v})" for k, v in top)\n                gl_lbl = QLabel(text)\n                gl_lbl.setWordWrap(True)\n                gl_lbl.setStyleSheet("color: " + TEXT_SECONDARY + "; font-size: 11px; border: none;")\n                gfl.addWidget(gl_lbl)\n\n        self._layout.insertWidget(self._layout.count(), guild_frame)\n        self._widgets.append(guild_frame)'

WB_EDITS = [
("import", """    raise ImportError("openpyxl is required for workbook export")
""", """    raise ImportError("openpyxl is required for workbook export")

try:
    from openpyxl.cell.rich_text import CellRichText, TextBlock
    from openpyxl.cell.text import InlineFont
    _RICH = True
except ImportError:  # openpyxl < 3.1: greyed parts fall back to an (n/a) suffix
    _RICH = False

# Which designations count where is decided in ONE place -- CodexRepository,
# the same functions _classify uses. The workbook calls them rather than keeping
# its own list, so the report can never disagree with the key-species count.
try:
    from shared.repositories.codex_repository import (
        _priority_applies, _legal_applies, StatusEntry)
except ImportError:  # pragma: no cover -- degrade to "everything applies"
    _priority_applies = None
    _legal_applies = None
    StatusEntry = None
"""),

("helpers", """    return value or ""
""", """    return value or ""


# ---- jurisdiction-aware status cells --------------------------------------

NA_GREY = "9CA3AF"

# Appendix labels (CodexRepository._priority_label output) back to a substring
# _priority_applies recognises. "SBL" in particular carries no "scottish".
_LABEL_KEYS = (("S41", "s41"), ("Wales S7", "wales"), ("SBL", "scottish"),
               ("NI Priority", "ni priority"), ("UK BAP", "bap"))


def _priority_ok(value, jurisdiction):
    if _priority_applies is None:
        return True
    return _priority_applies(value, jurisdiction)


def _legal_ok(text, jurisdiction):
    if _legal_applies is None or StatusEntry is None:
        return True
    return _legal_applies(StatusEntry(value=text, detail=text), jurisdiction)


def _label_ok(token, jurisdiction):
    for prefix, key in _LABEL_KEYS:
        if token.startswith(prefix):
            return _priority_ok(key, jurisdiction)
    return True      # threat / rarity codes and anything unrecognised: GB-wide


def status_parts(entry, jurisdiction):
    \"\"\"[(text, applies), ...] for a KeySpeciesEntry.\"\"\"
    parts = []
    for v in (getattr(entry, "threat", ""), getattr(entry, "threat_legacy", ""),
              getattr(entry, "rarity", "")):
        if v and (v, True) not in parts:
            parts.append((v, True))
    for j in getattr(entry, "priority", None) or []:
        parts.append((_short_jurisdiction(j), _priority_ok(j, jurisdiction)))
    legal = getattr(entry, "legal", None) or []
    ok = sum(1 for x in legal if _legal_ok(x, jurisdiction))
    if ok:
        parts.append((f"Legal ({ok})", True))
    if len(legal) - ok:
        parts.append((f"Legal, other jurisdiction ({len(legal) - ok})", False))
    return parts


def _parts_from_string(s, jurisdiction):
    \"\"\"Same, for a non-key species' Codex display string.\"\"\"
    return [(t, _label_ok(t, jurisdiction))
            for t in (x.strip() for x in (s or "").split(",")) if t]


def status_cell(parts, jurisdiction):
    \"\"\"Cell value: plain text, with other jurisdictions' designations in grey.\"\"\"
    if not parts:
        return ""
    if all(a for _, a in parts):
        return ", ".join(t for t, _ in parts)
    if _RICH:
        blocks = []
        for i, (t, a) in enumerate(parts):
            if i:
                blocks.append(", ")
            blocks.append(t if a else TextBlock(InlineFont(color=NA_GREY, i=True), t))
        return CellRichText(*blocks)
    return ", ".join(t if a else f"{t} (n/a {jurisdiction})" for t, a in parts)
"""),

("key sheet", """                   status_string(k),
""", """                   status_cell(status_parts(k, stamp["jurisdiction"]),
                               stamp["jurisdiction"]),
"""),

("appendix", """        status = status_string(k) if k else (sp.status or "")
""", """        juris = stamp["jurisdiction"]
        status = status_cell(status_parts(k, juris) if k
                             else _parts_from_string(sp.status, juris), juris)
"""),

("stamp", """        "survey_year": year or None,
""", """        "survey_year": year or None,
        "jurisdiction": jurisdiction,
"""),

("definitions", """    ("p prefix (pNS, pNT)", "A provisional status from an unpublished review."),
""", """    ("p prefix (pNS, pNT)", "A provisional status from an unpublished review."),
    ("Grey italic",
     "A designation that applies in another jurisdiction. Shown for "
     "completeness; it does not count towards Key Species under the "
     "jurisdiction this assessment was made for (see Summary)."),
"""),
]


def read(p):
    raw = io.open(p, "rb").read()
    crlf = b"\r\n" in raw
    t = raw.decode("utf-8-sig").replace("\r\n", "\n")
    return t, crlf


def write(p, text, crlf):
    if crlf:
        text = text.replace("\n", "\r\n")
    io.open(p, "w", encoding="utf-8", newline="").write(text)


print("Patching -- grey out other jurisdictions' designations")
print("=" * 70)

ct_text, ct_crlf = read(CT)
if hashlib.sha256(ct_text.rstrip().encode()).hexdigest() != CT_EXPECTED_SHA:
    print("  x conservation_tab.py differs from the reviewed version -- ABORTED")
    print("    nothing written")
    sys.exit(1)
print("  ok conservation_tab.py matches the reviewed version")

wb_text, wb_crlf = read(WB)
for name, old, new in WB_EDITS:
    n = wb_text.count(old)
    if n != 1:
        print(f"  x workbook_export.py anchor '{name}' found {n} times -- ABORTED")
        print("    nothing written")
        sys.exit(1)
    wb_text = wb_text.replace(old, new)
    print(f"  ok workbook_export.py: {name}")

for p in (CT, WB):
    shutil.copy2(p, p + ".bak_grey")
write(CT, CT_NEW, ct_crlf)
write(WB, wb_text, wb_crlf)
print("  + both files written (backups: *.bak_grey)")

print("\n  Checking...")
bad = False
for p in (CT, WB):
    try:
        py_compile.compile(p, doraise=True)
        print(f"  ok compiles: {os.path.relpath(p, ROOT)}")
    except py_compile.PyCompileError as e:
        bad = True
        print(f"  x COMPILE FAILED: {os.path.relpath(p, ROOT)}\n{e}")

# Functional check on the workbook helpers, against Codex's own rule.
try:
    sys.path.insert(0, ROOT)
    import importlib
    wbm = importlib.import_module("Examen.workbook_export")
    class E: pass
    e = E()
    e.threat, e.threat_legacy, e.rarity = "", "", "NS"
    e.priority = ["NI Priority Species", "NERC S.41 England",
                  "Env (Wales) Act S7", "UK BAP"]
    e.legal = ["NI Wildlife Order 1985 Sch5"]
    for j in ("Wales", "England"):
        parts = wbm.status_parts(e, j)
        grey = [t for t, a in parts if not a]
        print(f"  {j:<8} greyed: {', '.join(grey) or 'none'}")
    print(f"  rich text available: {wbm._RICH}")
except Exception as ex:
    print(f"  (functional check skipped: {type(ex).__name__}: {ex})")

if bad:
    print("\nRESTORE: copy each *.bak_grey back over its file.")
else:
    print("\nDone. Reopen Examen, select Machen, open the Conservation tab.")
