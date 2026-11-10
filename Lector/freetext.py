"""Free-text searches (Round 15): an author or place name instead of species names.

BHL's PublicationSearch (searchterm, searchtype 'F' = catalogue and full text, page; 200
results a page) returns PUBLICATIONS - each with BHLType Title, Item or Part, FoundIn
(Metadata, Text or Both), the Item/Part/Title ids, title, authors, date, volume and a URL -
and no page ids. Lector therefore stores each publication in the pages table under a
made-up NEGATIVE page_id (a real BHL PageID is always positive), with the item_id /
part_id / title_id and the BHL link (page_url) kept in their own columns. Such a row has
no page text and is never sent to GetPageMetadata. The searched terms are stored as the
search's names, with no UKSI checks.
"""
from .harvest import _authors, _int, parse_year

ITEM_BASE, PART_BASE, TITLE_BASE = 0, 100_000_000, 200_000_000
PAGE_SIZE = 200
MAX_RESULT_PAGES = 5                       # at most 1,000 publications per term
CACHE_PREFIX = "text: "                    # name_hits key, apart from species names


def is_publication_id(page_id):
    return page_id is not None and page_id < 0


def cache_key(term):
    return CACHE_PREFIX + term


def publication_id(bhl_type, item_id=None, part_id=None, title_id=None):
    """The made-up negative page_id of an item, part or title."""
    if bhl_type == "Part" and part_id:
        return -(PART_BASE + part_id)
    if bhl_type == "Title" and title_id:
        return -(TITLE_BASE + title_id)
    if item_id:
        return -(ITEM_BASE + item_id)
    return None


def _walk(node, out):
    if isinstance(node, list):
        for c in node:
            _walk(c, out)
    elif isinstance(node, dict):
        if "BHLType" in node:
            out.append(node)
        else:
            for v in node.values():
                if isinstance(v, (list, dict)):
                    _walk(v, out)


def extract_publications(result, term=None):
    """PublicationSearch Result -> page-shaped records (see the module note), unique."""
    found = []
    _walk(result, found)
    records = {}
    for n in found:
        kind = n.get("BHLType") or "Item"
        item_id, part_id, title_id = _int(n.get("ItemID")), _int(n.get("PartID")), _int(n.get("TitleID"))
        pid = publication_id(kind, item_id, part_id, title_id)
        if pid is None or pid in records:
            continue
        found_in = n.get("FoundIn")
        container = n.get("ContainerTitle")
        records[pid] = {
            "page_id": pid, "item_id": item_id, "title_id": title_id,
            "title": (container or n.get("Title")) if kind == "Part" else n.get("Title"),
            "volume": n.get("Volume"),
            "year": parse_year(n.get("Date"), n.get("Year"), n.get("Volume")),
            "page_label": n.get("PageRange") or None,
            "page_url": n.get("PartUrl") if kind == "Part" else (
                n.get("ItemUrl") or n.get("TitleUrl")),
            "ocr_url": None,
            "page_type": f"Publication ({kind}" + (f", found in {found_in}" if found_in else "")
                         + ")",
            "part_id": part_id,
            "article_title": (n.get("Title") or "").strip() or None if kind == "Part" else None,
            "authors": _authors(n),
            "found_in": found_in,
        }
    return list(records.values())


def search_term(client, term, max_pages=MAX_RESULT_PAGES, cancel=None):
    """All publications for a term: successive result pages until one is short."""
    out = {}
    for page in range(1, max_pages + 1):
        if cancel is not None and (cancel.is_set() if hasattr(cancel, "is_set") else cancel()):
            break
        result = client.publication_search(term, page=page)
        for r in extract_publications(result, term):
            out.setdefault(r["page_id"], r)
        if len(result) < PAGE_SIZE:
            break
    return list(out.values())

