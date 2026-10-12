"""Excerpts, page classification and duplicate grouping for dossier export.

Pure functions over page rows (dicts / sqlite3.Row); no database or network.
    find_excerpts(text, names)  -> list of excerpts, each a list of lines
    classify(row, excerpts)     -> 'main' | 'index' | 'no_match'
    group_duplicates(entries)   -> entries with .copies filled in

Restored from fix2 (7 Oct). Since 12 Oct names are found with Lector.names
(any case, accents, hyphenated line ends: LEC6) and duplicate scans are
grouped on title + volume + page and on the whole page text (LEC2).
"""
import re
from difflib import SequenceMatcher

from .names import find_names, fold, name_regex

LINES_EACH_SIDE = 2                 # 2 + name line + 2 = 5-line excerpt
MAX_EXCERPTS_PER_PAGE = 3
INDEX_PAGE_TYPES = {"index", "table of contents", "list of illustrations"}
SIMILAR = 0.90                      # excerpt similarity that counts as the same text
PAGE_SIMILAR = 0.85                 # whole-page word similarity: another scan of the page
SAME_PAGE_SIMILAR = 0.50            # ...when title, volume and page number agree too
COPYRIGHT_CHECK_FROM = 1930         # pages from this year on get a rights flag


# --- name matching ----------------------------------------------------------
def name_pattern(names):
    """Compiled matcher for the searched names (see Lector.names): 'Lamia
    textor', 'L. textor', 'Lamia\\ntextor', 'tex-\\ntor' or the epithet alone,
    in any case, with or without accents. Use with split_marked()."""
    return name_regex([n.strip() for n in names or [] if n and n.strip()])


def split_marked(text, pattern):
    """Split text into (text, is_name) runs so the name can be set in bold."""
    runs, pos = [], 0
    for start, end in find_names(text, None, pattern) if pattern else []:
        if start > pos:
            runs.append((text[pos:start], False))
        runs.append((text[start:end], True))
        pos = end
    if pos < len(text or ""):
        runs.append((text[pos:], False))
    return runs


def find_excerpts(text, names, pattern=None):
    """Return up to MAX_EXCERPTS_PER_PAGE excerpts (lists of lines) around
    each place a searched name occurs. Overlapping windows are merged; a name
    split over two lines keeps both lines."""
    pattern = pattern or name_pattern(names)
    if not text or not pattern:
        return []
    lines = [ln.rstrip() for ln in text.splitlines()]
    joined = "\n".join(lines)
    windows = []
    for start, end in find_names(joined, None, pattern):
        first, last = joined.count("\n", 0, start), joined.count("\n", 0, end)
        lo, hi = max(0, first - LINES_EACH_SIDE), min(len(lines), last + LINES_EACH_SIDE + 1)
        if windows and lo <= windows[-1][1]:
            windows[-1][1] = max(windows[-1][1], hi)
        else:
            windows.append([lo, hi])
    out = []
    for lo, hi in windows[:MAX_EXCERPTS_PER_PAGE]:
        chunk = [ln for ln in lines[lo:hi] if ln.strip()]
        if chunk:
            out.append(chunk)
    return out


# --- classification ---------------------------------------------------------
def _get(row, key, default=None):
    try:
        return row[key]
    except (KeyError, IndexError):
        return default


def page_types(row):
    raw = _get(row, "page_type")
    return {t.strip().lower() for t in (raw or "").split(";") if t.strip()}


NUMBER_END = re.compile(r"\d+\s*[.,;*]?\s*$")


def looks_like_index(text):
    """Layout test for pages BHL has not typed: most lines end in a page number."""
    lines = [ln for ln in (text or "").splitlines() if len(ln.strip()) > 2]
    if len(lines) < 12:
        return False
    ending = sum(1 for ln in lines if NUMBER_END.search(ln))
    return ending / len(lines) >= 0.45


def classify(row, excerpts):
    """'index' for index/contents pages, 'no_match' when the name was not
    found in the OCR text, otherwise 'main'."""
    if page_types(row) & INDEX_PAGE_TYPES:
        return "index"
    if looks_like_index(_get(row, "ocr_text")):
        return "index"
    if not excerpts:
        return "no_match"
    return "main"


def index_reason(row):
    return "BHL page type" if page_types(row) & INDEX_PAGE_TYPES else "layout"


def copyright_flag(row):
    y = _get(row, "year")
    if y and y >= COPYRIGHT_CHECK_FROM:
        return "May be in copyright - check the rights statement on BHL before reproducing"
    return ""


# --- duplicates -------------------------------------------------------------
def _norm(text):
    return re.sub(r"[^a-z0-9]", "", fold(text or ""))


def volume_key(volume):
    """Volume numbers without the years: 'v.7 (1841)' and '7' both -> '7'."""
    v = re.sub(r"\((?:1[6-9]|20)\d\d(?:\s*-\s*\d{2,4})?\)", " ", volume or "")
    return " ".join(re.findall(r"\d+", v))


def page_key(label):
    """Printed page number: 'Page 145', 'p. 145' -> '145'."""
    return " ".join(re.findall(r"\d+|[ivxlcdm]+(?=\W*$)", fold(label or "")))


def same_printed_page(a, b):
    """Title, volume and printed page number all agree (and are known)."""
    pa, pb = page_key(_get(a, "page_label")), page_key(_get(b, "page_label"))
    return bool(pa) and pa == pb \
        and _norm(_get(a, "title")) == _norm(_get(b, "title")) \
        and volume_key(_get(a, "volume")) == volume_key(_get(b, "volume"))


def _words(text):
    return [w for w in re.findall(r"[a-z0-9]+", fold(text or "")) if len(w) > 1][:1500]


def text_similarity(words_a, words_b):
    """0-1 similarity of two pages' word lists (OCR errors tolerated)."""
    if not words_a or not words_b:
        return 0.0
    sm = SequenceMatcher(None, words_a, words_b, autojunk=False)
    if sm.real_quick_ratio() < SAME_PAGE_SIMILAR or sm.quick_ratio() < SAME_PAGE_SIMILAR:
        return 0.0
    return sm.ratio()


def _excerpt_key(excerpts):
    return _norm(" ".join(" ".join(e) for e in excerpts))[:600]


def _same_text(a, b):
    if not a or not b:
        return False
    if a == b:
        return True
    sm = SequenceMatcher(None, a, b, autojunk=False)
    return sm.real_quick_ratio() >= SIMILAR and sm.quick_ratio() >= SIMILAR \
        and sm.ratio() >= SIMILAR


def is_duplicate(a, b, words_a=None, words_b=None, key_a=None, key_b=None):
    """Are rows a and b scans (or reprints) of the same text?

    Never for two pages of the same scanned item (a repeated advertisement or
    list is not a copy). Otherwise yes for:
    - the same printed page (title + volume + page number) whose texts are at
      least half the same, or either has no text yet;
    - whole-page text at least PAGE_SIMILAR the same, years within one; or
    - the excerpts around the name at least SIMILAR the same (fix2's rule,
      catches a reissue under another title), years within one.
    """
    ia, ib = _get(a, "item_id"), _get(b, "item_id")
    if ia and ia == ib:
        return False        # two pages of one scanned volume: repeated text, not a copy
    ya, yb = _get(a, "year"), _get(b, "year")
    near = ya is None or yb is None or abs(ya - yb) <= 1
    words_a = _words(_get(a, "ocr_text")) if words_a is None else words_a
    words_b = _words(_get(b, "ocr_text")) if words_b is None else words_b
    if same_printed_page(a, b):
        if not words_a or not words_b or text_similarity(words_a, words_b) >= SAME_PAGE_SIMILAR:
            return True
    if not near:
        return False
    if words_a and words_b and text_similarity(words_a, words_b) >= PAGE_SIMILAR:
        return True
    return bool(key_a and key_b and _same_text(key_a, key_b))


SECTION_RANK = {"main": 0, "index": 1, "no_match": 2}


def group_duplicates(entries):
    """Merge entries that are the same text (other libraries' scans, reissues
    under another title). Entries need .row, .excerpts and .copies (and may
    have .section). The first entry in the given order is kept, except that an
    entry where the name was found beats a copy where OCR missed it; the rest
    go in its .copies."""
    kept = []
    for e in entries:
        e.key = _excerpt_key(e.excerpts)
        e.words = _words(_get(e.row, "ocr_text"))
        for k in kept:
            if is_duplicate(e.row, k.row, e.words, k.words, e.key, k.key):
                if SECTION_RANK.get(getattr(e, "section", "main"), 0) < \
                        SECTION_RANK.get(getattr(k, "section", "main"), 0):
                    # the new one found the name: it leads, the old one is the copy
                    k.row, e.row = e.row, k.row
                    k.excerpts, k.section = e.excerpts, e.section
                    k.key, k.words = e.key, e.words
                k.copies.append(e.row)
                break
        else:
            kept.append(e)
    return kept
