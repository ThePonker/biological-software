"""Harvest: name -> BHL pages -> filter. Pure functions over BHL responses.

extract_pages() walks the GetNameMetadata response by key rather than by a
fixed path, so it tolerates BHL nesting pages under titles, items or parts.
Use `python -m Lector probe <name>` to inspect a raw response if in doubt.

Storing pages, downloading text and runs live in Lector.engine; the old
harvest_species() entry point is kept below and hands over to it.
"""
import re
from dataclasses import dataclass, field
from datetime import date

from . import config
from .excerpts import INDEX_PAGE_TYPES, _norm, page_key, volume_key

FIRST_YEAR = 1600                   # earliest year a volume/date string can give


def title_has(words, title):
    """True if any word/phrase occurs in title as a whole word (an English
    plural is allowed): 'Naturalist' matches "Naturalists' Society" but not
    'naturalistes' or 'Naturalista'. Case-insensitive."""
    return any(re.search(r"\b" + re.escape(w.strip()) + r"s?(?![^\W\d_])",
                         title or "", re.I)
               for w in words if w.strip())


@dataclass
class HarvestOptions:
    from_year: int = None
    to_year: int = None
    max_pages: int = config.DEFAULT_MAX_PAGES
    include_titles: list = field(default_factory=list)
    exclude_titles: list = field(default_factory=list)
    count_only: bool = False
    refresh: bool = False
    skip_index: bool = False        # drop pages BHL types as index / contents
    skip_duplicates: bool = True    # drop other libraries' scans of a printed page


# --- years (LEC4) -----------------------------------------------------------
# A number, optionally after 'no.', 'nr.', 'p.', 'pl.', 'fig.' (then it is never
# a year), optionally followed by a range ('1841-1842', '3-4').
_NUMBER = re.compile(
    r"(?P<pre>(?<![^\W\d_])(?:nos?|nr|nro|pp?|pls?|figs?|n°|№)\.?\s*)?"
    r"(?P<num>\d+)(?P<range>(?:\s*[-–/]\s*\d+)*)", re.I)


def first_year(value, latest=None):
    """First plausible year (1600 to this year) in a volume or date string.

    '1841-1842' -> 1841; 'v.18-20 (1887-1890)' -> 1887; 't.32:no.1-2 (1859)'
    -> 1859; 'no.1545' -> None (an issue number, not a year).
    """
    latest = latest or date.today().year
    for m in _NUMBER.finditer(str(value or "")):
        if m.group("pre"):
            continue
        num = m.group("num")
        if len(num) == 4 and FIRST_YEAR <= int(num) <= latest:
            return int(num)
    return None


def parse_year(*values):
    """First plausible year from the values, in the order given."""
    for v in values:
        y = first_year(v)
        if y:
            return y
    return None


# --- BHL response -----------------------------------------------------------
def _page_label(page):
    parts = []
    for pn in page.get("PageNumbers") or []:
        label = f"{pn.get('Prefix') or ''} {pn.get('Number') or ''}".strip()
        if label:
            parts.append(label)
    return "; ".join(parts) or None


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _authors(node):
    """'; '-joined author names from a BHL Authors list (dicts or strings)."""
    names = []
    for a in (node or {}).get("Authors") or []:
        n = (a.get("Name") or a.get("FullName") or "") if isinstance(a, dict) else str(a)
        n = n.strip().rstrip(",")
        if n and n not in names:
            names.append(n)
    return "; ".join(names) or None


def _page_record(page, title, item, part=None):
    part = part or {}
    return {
        "page_id": int(page["PageID"]),
        "item_id": _int(page.get("ItemID") or item.get("ItemID")),
        "title_id": _int(title.get("TitleID") or item.get("TitleID")),
        "title": title.get("FullTitle") or title.get("ShortTitle")
                 or part.get("ContainerTitle") or item.get("ContainerTitle")
                 or item.get("Title"),
        "volume": page.get("Volume") or item.get("Volume") or part.get("Volume"),
        "year": parse_year(page.get("Year"), item.get("Year"), item.get("Date"),
                           part.get("Date"), item.get("Volume"),
                           title.get("PublicationDate")),
        "page_label": _page_label(page),
        "page_url": page.get("PageUrl")
                    or f"https://www.biodiversitylibrary.org/page/{page['PageID']}",
        "ocr_url": page.get("OcrUrl"),
        "page_type": "; ".join(pt.get("PageTypeName") or ""
                               for pt in page.get("PageTypes") or []) or None,
        "part_id": _int(part.get("PartID")),
        "article_title": (part.get("Title") or "").strip() or None,
        "authors": _authors(part) or _authors(title),
    }


def extract_pages(result):
    """Flatten a GetNameMetadata Result into unique page records."""
    pages = {}

    def walk(node, title, item, part):
        if isinstance(node, list):
            for child in node:
                walk(child, title, item, part)
            return
        if not isinstance(node, dict):
            return
        if "PageID" in node:
            pid = _int(node["PageID"])
            if pid is not None and pid not in pages:
                pages[pid] = _page_record(node, title, item, part)
            return
        if "PartID" in node:
            part = node
        elif "ItemID" in node:
            item = {**item, **node}
        elif "TitleID" in node:
            title = node
        for value in node.values():
            if isinstance(value, (list, dict)):
                walk(value, title, item, part)

    walk(result, {}, {}, None)
    return list(pages.values())


# --- filters ----------------------------------------------------------------
def scan_key(p):
    """(title, volume, printed page) or None when the page number is unknown.
    Volume strings are compared by their numbers ('7' = 'v.7 (1841)'); with
    no volume number the year stands in, so different volumes never merge."""
    page = page_key(p["page_label"])
    if not page:
        return None
    vol = volume_key(p["volume"]) or _norm(p["volume"]) or f"y{p['year']}"
    return (_norm(p["title"]), vol, page)


def drop_duplicate_scans(pages):
    """Keep one copy where several libraries scanned the same page.

    Pages count as duplicates when title, volume and printed page number all
    match. Pages without a printed page number are always kept here; the
    dossier and review list compare their text once it is downloaded.
    """
    seen, kept = set(), []
    for p in pages:
        key = scan_key(p)
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
        kept.append(p)
    return kept


def is_index_type(p):
    types = {t.strip().lower() for t in (p.get("page_type") or "").split(";")}
    return bool(types & INDEX_PAGE_TYPES)


def apply_filters(pages, opts):
    kept = []
    for p in pages:
        y, t = p["year"], p["title"] or ""
        if opts.from_year and (y is None or y < opts.from_year):
            continue
        if opts.to_year and (y is None or y > opts.to_year):
            continue
        if opts.include_titles and not title_has(opts.include_titles, t):
            continue
        if title_has(opts.exclude_titles, t):
            continue
        if opts.skip_index and is_index_type(p):
            continue
        kept.append(p)
    kept.sort(key=lambda p: (p["year"] is None, p["year"] or 0, p["page_id"]))
    if opts.skip_duplicates:
        kept = drop_duplicate_scans(kept)
    return kept[:opts.max_pages] if opts.max_pages else kept


def harvest_species(client, store, entry, opts, log=print, keep_filters=False):
    """Search all names for one species, store hits, fetch missing OCR.
    Kept for older callers: runs the species' saved search (Lector.engine)."""
    from .engine import harvest_entry
    return harvest_entry(client, store, entry, opts, log=log, keep_filters=keep_filters)
