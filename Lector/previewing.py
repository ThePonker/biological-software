"""Preview of a search before it runs: found / within filters / to download (service.py).

Used for a saved search (service.preview) and for the search builder's unsaved
names and filters (service.preview_draft), so the two always agree.
"""
from . import config, engine, saved
from .bhl_client import BHLError
from .harvest import apply_filters, drop_duplicate_scans


def name_dict(n):
    """A name as the builder holds it: str or {'name', 'included', ...}."""
    return {"name": n, "included": True} if isinstance(n, str) else n


def preview_pages(store, client, names, filters, use_network=False, refresh=False,
                  progress=None, cancel=None, count_all=False):
    """names: [str or {'name', 'included'}]; filters: dict of filter keys (missing
    keys take the defaults). Only ticked names count towards the totals; with
    count_all, unticked names are counted too (shown beside each name, so a held-back
    name can be judged). Returns the preview dict plus name_found {name: int|None}."""
    f = dict(saved.DEFAULT_FILTERS)
    f.update({k: v for k, v in (filters or {}).items() if k in f})
    opts = saved.options_from_filters(f)
    names = [name_dict(n) for n in names]
    included = [n["name"] for n in names if n.get("included", True)]
    to_count = [n["name"] for n in names if count_all or n.get("included", True)]
    pages, kept, not_counted, uncached, name_found = {}, {}, [], 0, {}
    for i, n in enumerate(to_count):
        if engine.is_cancelled(cancel):
            break
        if progress:
            progress("count", i, len(to_count), f"Counting {n}")
        cached = store.cached_name_hits(n) is not None
        if not cached:
            if n in included:
                uncached += 1
            if not use_network:
                name_found[n] = None
                if n in included:
                    not_counted.append(n)
                continue
        try:
            found, _src = engine.name_pages(store, client() if not cached or refresh else None,
                                            n, refresh and use_network)
        except BHLError:
            name_found[n] = None
            if n in included:
                not_counted.append(n)
            continue
        name_found[n] = len(found)
        if n not in included:
            continue
        for p in found:
            pages.setdefault(p["page_id"], p)
        for p in apply_filters(found, opts):
            kept.setdefault(p["page_id"], p)
    if progress and to_count:
        progress("count", len(to_count), len(to_count), "Counted")
    kept_list = sorted(kept.values(), key=lambda p: (p["year"] is None, p["year"] or 0,
                                                     p["page_id"]))
    if opts.skip_duplicates:
        kept_list = drop_duplicate_scans(kept_list)
    ids = [p["page_id"] for p in kept_list]
    have = {r[0] for r in store.conn.execute(
        "SELECT page_id FROM pages WHERE fetched_at IS NOT NULL")}
    to_download = [p for p in ids if p not in have]
    est = len(included) + len(to_download)             # a run asks BHL for every name
    return {"found": len(pages), "within_filters": len(ids),
            "already_held": len(ids) - len(to_download), "to_download": len(to_download),
            "requests": est, "est_seconds": round(est * config.REQUEST_INTERVAL),
            "requests_without_refresh": (uncached if not use_network else 0) + len(to_download),
            "not_counted": not_counted, "names": included, "name_found": name_found}
