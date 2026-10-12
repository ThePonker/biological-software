"""checklist_parsers -- read published checklists into ordered name rows. READ ONLY.

Used by scripts/build_checklists.py. Each parser returns rows in the checklist's own
sequence:  {"family", "genus", "epithet", "subgenus", "listed"}  where `listed` is the name
as printed ("Genus epithet") and `family` is the checklist's family (resolved to UKSI later).

The PDFs are read with pdfplumber, word by word WITH the font, because the font is what
tells an accepted name from a synonym in these lists (Duff: accepted species in bold
italic, synonyms in plain italic; Diptera: bold at the margin; Agassiz: bold italic beside
the checklist code). Each parser works on Line objects, so the tests can feed it a few
synthetic lines instead of a PDF:

    Line(page, col, x0, size, words)      words = [(text, fontname), ...] left to right

The britishbugs pages are plain text (one field per line) and are parsed as text.
"""
from __future__ import annotations

import re
from collections import namedtuple
from typing import Iterable, List, Optional

Line = namedtuple("Line", "page col x0 size words")

_EPITHET = re.compile(r"^[a-z][a-z\-]+$")
_CAPS = re.compile(r"^[A-Z][A-Z\-]{2,}$")
_AUTHORISH = re.compile(r"^(\(|\[|[A-Z]|d'|de\b|des\b|van\b|von\b|du\b|le\b|la\b)")
_HAS_YEAR = re.compile(r"\b1[6-9]\d\d|\b20[0-2]\d")
_GENUS_NAME = re.compile(r"^[A-Z][a-z]+$")
_FAMILY = re.compile(r"^[A-Z][a-z]+idae$")


def text(line: Line) -> str:
    return " ".join(w for w, _ in line.words)


def _bold(font: str) -> bool:
    return "bold" in font.lower() or "black" in font.lower()


def _italic(font: str) -> bool:
    f = font.lower()
    return "italic" in f or "oblique" in f


def _species_like(words, i: int = 0) -> bool:
    """words[i] is an epithet followed by an author (or a year somewhere on the line)."""
    if i >= len(words) or not _EPITHET.match(words[i][0]):
        return False
    rest = " ".join(w for w, _ in words[i + 1:])
    return bool(rest) and (bool(_AUTHORISH.match(rest)) or bool(_HAS_YEAR.search(rest)))


def _row(family, genus, epithet, subgenus="") -> dict:
    return {"family": family, "genus": genus, "epithet": epithet, "subgenus": subgenus,
            "listed": f"{genus} {epithet}"}


# ---------------------------------------------------------------- PDF -> lines

def pdf_lines(path: str, columns: int = 1, min_size: float = 0.0, first_page: int = 0,
              last_page: Optional[int] = None, x_tolerance: float = 3) -> List[Line]:
    """Every text line of the PDF, page by page, left column then right column.
    x_tolerance: the gap (points) that still joins letters into one word -- the BDJ paper
    sets 'Astata boops' so tight that the default 3 reads it as one word."""
    import pdfplumber
    out: List[Line] = []
    with pdfplumber.open(path) as pdf:
        pages = pdf.pages[first_page:last_page]
        for pno, page in enumerate(pages, start=first_page):
            words = page.extract_words(extra_attrs=["fontname", "size"], x_tolerance=x_tolerance)
            mid = page.width / 2
            cols = {}
            for w in words:
                if w["size"] < min_size:
                    continue
                c = 0 if columns == 1 or w["x0"] < mid - 5 else 1
                cols.setdefault(c, []).append(w)
            for c in sorted(cols):
                ws = sorted(cols[c], key=lambda w: (w["top"], w["x0"]))
                group: list = []
                for w in ws:
                    if group and w["top"] - group[0]["top"] > 2.5:
                        out.append(_mk(pno, c, group))
                        group = []
                    group.append(w)
                if group:
                    out.append(_mk(pno, c, group))
    return out


def _mk(pno, col, group) -> Line:
    group = sorted(group, key=lambda w: w["x0"])
    words, x1 = [], None
    for w in group:
        font = str(w["fontname"]).split("+")[-1]
        if words and x1 is not None and -1 < w["x0"] - x1 < 0.5 \
                and not (w["text"].startswith("(") and words[-1][0][-1:].isalpha()):
            # touching: one word split by a font change, e.g. the 'ffi' ligature of
            # 'affinis' set in an 'Expert' font, or '( Andrena )' in the BDJ paper -- but
            # not 'argentimaculella(Stainton,' (an author's bracket set without a space)
            words[-1] = (words[-1][0] + w["text"], words[-1][1])
        else:
            words.append((w["text"], font))
        x1 = w["x1"]
    return Line(pno, col, round(group[0]["x0"], 1), round(max(w["size"] for w in group), 1),
                words)


# ---------------------------------------------------------------- Duff 2008 (Coleoptera)

_DUFF_FAMILY = re.compile(r"^\d+\.\s+Family\s+([A-Z]+)\b")


def parse_duff(lines: Iterable[Line]) -> List[dict]:
    """Families '19. Family SILPHIDAE ...' (bold); genera in bold CAPITALS; subgenera
    'Subgenus XXX' (plain); accepted species: the line's first word in BOLD ITALIC, an
    epithet followed by its author. Synonyms (plain italic, indented) and prose are skipped."""
    rows, family, genus, sub = [], "", "", ""
    for ln in lines:
        if not ln.words:
            continue
        t = text(ln)
        first, font = ln.words[0]
        m = _DUFF_FAMILY.match(t)
        if m and _bold(font):
            family, genus, sub = m.group(1).capitalize(), "", ""
            continue
        if not family:
            continue
        if first == "Subgenus" and len(ln.words) > 1 and _CAPS.match(ln.words[1][0]):
            sub = ln.words[1][0].capitalize()
            continue
        if _bold(font) and not _italic(font) and _CAPS.match(first) and len(ln.words) > 1:
            genus, sub = first.capitalize(), ""
            continue
        if genus and _bold(font) and _italic(font) and _species_like(ln.words):
            rows.append(_row(family, genus, first, sub))
    return rows


# ---------------------------------------------------------------- Diptera 2025

_DIP_FAMILY = re.compile(r"^([A-Z]+IDAE)\b")
_DIP_SKIP = {"References", "Notes", "Nomina dubia", "Excluded species", "Imported species"}


def parse_diptera(lines: Iterable[Line]) -> List[dict]:
    """Family headings 'TIPULIDAE (1998 87, no change)' (bold, larger); genera in bold
    CAPITALS at the margin; accepted species: bold epithet + author at the margin.
    'Nomina dubia', 'Excluded species', 'Imported species', 'Notes', 'References' blocks
    are skipped until the next family."""
    rows, family, genus, skip = [], "", "", True
    for ln in lines:
        if not ln.words:
            continue
        t = text(ln)
        first, font = ln.words[0]
        m = _DIP_FAMILY.match(t)
        if m and _dip_bold(font) and ln.size >= 10 and "(" in t:
            family, genus, skip = m.group(1).capitalize(), "", False
            continue
        if t.strip() in _DIP_SKIP:
            skip = True
            continue
        if skip or not family:
            continue
        if _dip_bold(font) and _CAPS.match(first) and len(ln.words) > 1 \
                and not first.endswith("INAE") and not first.endswith("INI"):
            genus = first.capitalize()
            continue
        if genus and _dip_bold(font) and _species_like(ln.words):
            rows.append(_row(family, genus, first))
    return rows


def _dip_bold(font: str) -> bool:
    # the Diptera PDF's fonts are unnamed: F1 regular, F2 bold, F3 italic
    return _bold(font) or font.endswith("F2")


# ---------------------------------------------------------------- Merrett & Murphy 2000

def parse_spiders(lines: Iterable[Line]) -> List[dict]:
    """'Family LINYPHIIDAE' headings; species lines in italic at full size: 'Genus epithet
    Author, year'. Old names [in brackets] and notes are smaller and skipped. Stops at the
    Channel Islands appendix / index."""
    rows, family = [], ""
    for ln in lines:
        if not ln.words:
            continue
        t = text(ln)
        first, font = ln.words[0]
        if t.startswith(("Appendix", "APPENDIX", "Index to genera")):
            break
        if ln.size < 9.5:
            continue
        if first == "Family" and len(ln.words) > 1 and _CAPS.match(ln.words[1][0]):
            family = ln.words[1][0].capitalize()
            continue
        if family and _italic(font) and _GENUS_NAME.match(first) and len(ln.words) > 2 \
                and _italic(ln.words[1][1]) and _species_like(ln.words, 1):
            rows.append(_row(family, first, ln.words[1][0]))
    return rows


# ---------------------------------------------------------------- Agassiz et al. 2024

_LEP_CODE = re.compile(r"^\d{1,3}\.\d{3,4}[a-z]?$")       # 12.0047: added later
_LEP_FAMILY = re.compile(r"^[A-Z]+IDAE$")


def parse_lepidoptera(lines: Iterable[Line]) -> List[dict]:
    """Families in large bold CAPITALS ('GEOMETRIDAE'); genera bold CAPITALS (subgenera are
    bold italic CAPITALS); species: checklist code ('70.001') then the epithet in bold
    italic. Stops at APPENDIX A. Rows carry the code in 'code'."""
    rows, family, genus = [], "", ""
    for ln in lines:
        if not ln.words:
            continue
        t = text(ln)
        if t.startswith("APPENDIX"):
            break
        words = [w for w in ln.words if re.search(r"\w", w[0])]     # drop the • / ○ marks
        if not words:
            continue
        ln = ln._replace(words=words)
        first, font = words[0]
        if _bold(font) and ln.size >= 12 and _LEP_FAMILY.match(first):
            family, genus = first.capitalize(), ""
            continue
        if _bold(font) and not _italic(font) and _CAPS.match(first) and len(ln.words) > 1 \
                and ln.size < 12:
            genus = first.capitalize()
            continue
        code = next((i for i, (w, _) in enumerate(ln.words[:3]) if _LEP_CODE.match(w)), None)
        if code is None or not genus:
            continue
        ep = next(((w, f) for w, f in ln.words[code + 1:code + 3]
                   if _EPITHET.match(w) and _bold(f) and _italic(f)), None)
        if ep:
            r = _row(family, genus, ep[0])
            r["code"] = ln.words[code][0]
            rows.append(r)
    return rows


# ---------------------------------------------------------------- Else, Bolton & Broad 2016

def parse_aculeates(lines: Iterable[Line]) -> List[dict]:
    """'Family Crabronidae Latreille, 1802'; 'Genus Astata ...'; accepted species in bold
    italic at the margin: 'Genus (Subgenus) epithet Author'. Synonyms under 'Nomenclature:'
    are plain italic. Stops at Acknowledgements / References."""
    rows, family = [], ""
    for ln in lines:
        if not ln.words:
            continue
        t = text(ln)
        first, font = ln.words[0]
        if t.strip() in ("Acknowledgements", "References"):
            break
        if first == "Family" and _bold(font) and len(ln.words) > 1 \
                and _FAMILY.match(ln.words[1][0]):
            family = ln.words[1][0]
            continue
        if not family or not (_bold(font) and _italic(font)) or not _GENUS_NAME.match(first):
            continue
        ws, sub = ln.words[1:], ""
        if ws and re.match(r"^\([A-Z][a-z]+\)$", ws[0][0]):
            sub, ws = ws[0][0][1:-1], ws[1:]
        elif len(ws) > 2 and ws[0][0] == "(" and ws[2][0] == ")":      # "( Andrena )"
            sub, ws = ws[1][0], ws[3:]
        if ws and _bold(ws[0][1]) and _italic(ws[0][1]) and _species_like(ws):
            rows.append(_row(family, first, ws[0][0], sub))
    return rows


# ---------------------------------------------------------------- britishbugs.org.uk pages

_BINOMIAL = re.compile(r"^[A-Z][a-z]+ (\([A-Z][a-z]+\) )?[a-z][a-z\-]+( [a-z][a-z\-]+)?$")
_AUTHORITY = re.compile(r"\d{4}|^\(")


def parse_heteroptera_text(src: str) -> List[dict]:
    """Blocks start with a group code line (S, P, W, ...): current name, [previous name],
    authority, [common name], family, status. Families are alphabetical within groups."""
    lines = [s.strip() for s in src.splitlines() if s.strip()]
    rows, i = [], 0
    while i < len(lines):
        if re.fullmatch(r"[A-Z]{1,2}", lines[i]) and i + 1 < len(lines) \
                and _BINOMIAL.match(lines[i + 1]):
            block = [lines[i + 1]]
            j = i + 2
            while j < len(lines) and not (re.fullmatch(r"[A-Z]{1,2}", lines[j])
                                          and j + 1 < len(lines)
                                          and _BINOMIAL.match(lines[j + 1])):
                block.append(lines[j])
                j += 1
            fam = next((b for b in block if _FAMILY.match(b)), "")
            if fam:
                rows.append(_bug_row(block[0], fam, lines[i]))
            i = j
        else:
            i += 1
    return rows


def parse_auchenorrhyncha_text(src: str) -> List[dict]:
    """Blocks: current name, [previous name], authority, family, subfamily, status --
    families in systematic order. A block ends at its family line (+ subfamily, status)."""
    lines = [s.strip() for s in src.splitlines() if s.strip()]
    rows, i = [], 0
    while i < len(lines):
        if not _BINOMIAL.match(lines[i]) or _STATUS.match(lines[i]):
            i += 1
            continue
        name, j = lines[i], i + 1
        while j < len(lines) and not _FAMILY.match(lines[j]) and j - i <= 4:
            j += 1
        if j >= len(lines) or not _FAMILY.match(lines[j]):
            i += 1
            continue
        rows.append(_bug_row(name, lines[j], ""))
        i = j + 1
        while i < len(lines) and (re.fullmatch(r"[A-Z][a-z]+(inae|ini)", lines[i])
                                  or _STATUS.match(lines[i])):
            i += 1                                 # subfamily / tribe, status
    return rows


_STATUS = re.compile(r"^(Common|Local|Notable|p?RDB|Unknown|Ireland|Naturalised|Nationally|"
                     r"Not |Introduced|Extinct|Vagrant|Rare|Scarce|Data|"
                     r"National status|Current name|Previous name)")     # + the column headers


def _bug_row(name: str, family: str, group: str) -> dict:
    words = [w for w in name.split() if not w.startswith("(")]
    r = _row(family, words[0], words[1])
    if len(words) > 2:
        r["listed"] = " ".join(words)
    r["group"] = group
    return r
