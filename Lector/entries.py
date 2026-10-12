"""Page rows -> dossier/review entries: excerpts, section, duplicate groups,
and citations with authors and article titles (LEC1).

Shared by the Word dossier, the Excel index and the service's review list.
Pure functions; rows may be sqlite3.Row or dicts, missing columns allowed.
"""
from dataclasses import dataclass, field

from .excerpts import _norm, classify, find_excerpts, group_duplicates

ROW_KEYS = ("page_id", "item_id", "title_id", "title", "volume", "year", "page_label",
            "page_url", "ocr_url", "text_source", "ocr_text", "names_found", "fetched_at",
            "page_type", "part_id", "article_title", "authors", "matched_names", "tvk",
            "statuses", "review_status", "review_tag", "notes", "state")


def prepare_row(row, extra_names=()):
    """Plain dict with every key present; 'names' = names to look for in the text."""
    d = dict(row) if not isinstance(row, dict) else dict(row)
    for k in ROW_KEYS:
        d.setdefault(k, None)
    if not d["page_url"] and d["page_id"]:
        d["page_url"] = f"https://www.biodiversitylibrary.org/page/{d['page_id']}"
    matched = [n.strip() for n in (d["matched_names"] or "").split(",") if n.strip()]
    d["names"] = list(dict.fromkeys(matched + [n for n in extra_names if n]))
    return d


def authors_short(authors, limit=3):
    names = [a.strip() for a in (authors or "").split(";") if a.strip()]
    if len(names) > limit:
        return f"{names[0]} et al."
    return " & ".join(names)


def source(row):
    """Citation without the year (the year has its own column):
    'Smith, J. "Notes on Coleoptera". Entomologist's Monthly Magazine, 7, Page 81'."""
    head = []
    if row.get("authors"):
        head.append(authors_short(row["authors"]).rstrip("."))
    if row.get("article_title"):
        head.append(f"“{row['article_title'].rstrip('.')}”")
    bits = [row.get("title") or "Untitled"]
    if row.get("volume"):
        bits.append(str(row["volume"]))
    if row.get("page_label"):
        bits.append(row["page_label"])
    return ". ".join(head + [", ".join(bits)])


def citation(row):
    """Full citation with the year: 'Smith, J. (1870). "Notes". Ent. Mon. Mag., 7, Page 81'."""
    year = f"({row['year']})" if row.get("year") else "(n.d.)"
    head = authors_short(row.get("authors"))
    rest = source(dict(row, authors=None))
    return f"{head} {year}. {rest}" if head else f"{rest} {year}"


@dataclass
class Entry:
    row: dict
    excerpts: list
    section: str                   # main / index / no_match
    copies: list = field(default_factory=list)
    key: str = ""
    number: int = 0


def order_key(by_journal):
    def key(r):
        if by_journal:
            return (_norm(r["title"]), r["year"] is None, r["year"] or 0, r["page_id"])
        return (r["year"] is None, r["year"] or 0, _norm(r["title"]), r["page_id"])
    return key


def build_entries(rows, by_journal=False, extra_names=(), merge_duplicates=True, keep=None):
    """Split rows into (main, index, no_match) entry lists, duplicates merged.

    Duplicates are looked for across all three lists, so a scan where OCR
    missed the name joins the scan where it was found (LEC2). keep(row) -> bool
    then drops whole groups by their leading row (e.g. pages marked not relevant)."""
    prepared = sorted((prepare_row(r, extra_names) for r in rows), key=order_key(by_journal))
    entries = []
    for r in prepared:
        ex = find_excerpts(r["ocr_text"], r["names"])
        entries.append(Entry(r, ex, classify(r, ex)))
    if merge_duplicates:
        entries = group_duplicates(entries)
    if keep is not None:
        entries = [e for e in entries if keep(e.row)]
    main = [e for e in entries if e.section == "main"]
    index = [e for e in entries if e.section == "index"]
    no_match = [e for e in entries if e.section == "no_match"]
    for i, e in enumerate(main, 1):
        e.number = i
    return main, index, no_match
