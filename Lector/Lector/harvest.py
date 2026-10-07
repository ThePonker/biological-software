"""Harvest: name -> BHL pages -> filter -> store metadata -> fetch OCR text.

extract_pages() walks the GetNameMetadata response by key rather than by a
fixed path, so it tolerates BHL nesting pages under titles, items or parts.
Use `python -m Lector probe <name>` to inspect a raw response if in doubt.
"""
import re
from dataclasses import dataclass, field

from . import config
from .bhl_client import BHLError

YEAR_RE = re.compile(r"(1[5-9]\d\d|20\d\d)")


@dataclass
class HarvestOptions:
    from_year: int = None
    to_year: int = None
    max_pages: int = config.DEFAULT_MAX_PAGES
    include_titles: list = field(default_factory=list)
    exclude_titles: list = field(default_factory=list)
    count_only: bool = False
    refresh: bool = False


def parse_year(*values):
    for v in values:
        m = YEAR_RE.search(str(v or ""))
        if m:
            return int(m.group(1))
    return None


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


def _page_record(page, title, item):
    return {
        "page_id": int(page["PageID"]),
        "item_id": _int(page.get("ItemID") or item.get("ItemID")),
        "title_id": _int(title.get("TitleID") or item.get("TitleID")),
        "title": title.get("FullTitle") or title.get("ShortTitle")
                 or item.get("ContainerTitle") or item.get("Title"),
        "volume": page.get("Volume") or item.get("Volume"),
        "year": parse_year(page.get("Year"), item.get("Year"), item.get("Date"),
                           title.get("PublicationDate")),
        "page_label": _page_label(page),
        "page_url": page.get("PageUrl")
                    or f"https://www.biodiversitylibrary.org/page/{page['PageID']}",
        "ocr_url": page.get("OcrUrl"),
    }


def extract_pages(result):
    """Flatten a GetNameMetadata Result into unique page records."""
    pages = {}

    def walk(node, title, item):
        if isinstance(node, list):
            for child in node:
                walk(child, title, item)
            return
        if not isinstance(node, dict):
            return
        if "PageID" in node:
            pid = _int(node["PageID"])
            if pid is not None and pid not in pages:
                pages[pid] = _page_record(node, title, item)
            return
        if "ItemID" in node or "PartID" in node:
            item = {**item, **node}
        elif "TitleID" in node:
            title = node
        for value in node.values():
            if isinstance(value, (list, dict)):
                walk(value, title, item)

    walk(result, {}, {})
    return list(pages.values())


def apply_filters(pages, opts):
    kept = []
    for p in pages:
        y, t = p["year"], (p["title"] or "").lower()
        if opts.from_year and (y is None or y < opts.from_year):
            continue
        if opts.to_year and (y is None or y > opts.to_year):
            continue
        if opts.include_titles and not any(k.lower() in t for k in opts.include_titles):
            continue
        if any(k.lower() in t for k in opts.exclude_titles):
            continue
        kept.append(p)
    kept.sort(key=lambda p: (p["year"] is None, p["year"] or 0, p["page_id"]))
    return kept[:opts.max_pages] if opts.max_pages else kept


def harvest_species(client, store, entry, opts, log=print):
    """Search all names for one species, store hits, fetch missing OCR."""
    log(f"\n■ {entry.name}" + (f"  [{entry.tvk}]" if entry.tvk else "  [no TVK]"))
    for query_name, role in entry.query_names():
        if store.search_done(entry.name, query_name) and not opts.refresh:
            log(f"  · {query_name} ({role}) - already searched, skipping")
            continue
        try:
            result = client.name_metadata(query_name)
        except BHLError as exc:
            log(f"  ✗ {query_name} ({role}) - {exc}")
            continue
        pages = extract_pages(result)
        kept = apply_filters(pages, opts)
        capped = " (capped)" if opts.max_pages and len(kept) == opts.max_pages else ""
        log(f"  ✓ {query_name} ({role}) - {len(pages)} pages, {len(kept)} kept{capped}")
        if opts.count_only:
            continue
        for page in kept:
            store.add_page_hit(page, entry, query_name)
        store.commit()
        store.record_search(entry, query_name, role, len(pages), len(kept))
    if not opts.count_only:
        fetch_texts(client, store, entry.name, log)


def fetch_texts(client, store, accepted_name, log=print):
    todo = store.pages_missing_text(accepted_name)
    if not todo:
        return
    log(f"  … fetching text for {len(todo)} pages (~{len(todo) * client._interval:.0f}s)")
    failed = 0
    for i, page_id in enumerate(todo, 1):
        try:
            meta = client.page_metadata(page_id)
        except BHLError as exc:
            failed += 1
            log(f"    ✗ page {page_id}: {exc}")
            continue
        names = [n.get("NameCanonical") or n.get("NameFound") or ""
                 for n in meta.get("Names") or []]
        store.save_text(page_id, meta.get("OcrText") or "", meta.get("TextSource"),
                        "; ".join(sorted({n for n in names if n})))
        if i % 25 == 0:
            log(f"    {i}/{len(todo)}")
    log(f"  ✓ text fetched: {len(todo) - failed}/{len(todo)}"
        + (f"  ({failed} failed - re-run to retry)" if failed else ""))
