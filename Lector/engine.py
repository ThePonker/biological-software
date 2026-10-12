"""Running a saved search: BHL name search -> filters -> pages -> text.

run_search() is what the command line and the service both use. Every run is
recorded with a snapshot of its names and filters. A run always applies the
search's CURRENT filters (LEC5): BHL's page list for each name is kept
(name_hits), so changed filters are re-applied without asking BHL again, and
pages that no longer pass are marked withdrawn (never deleted; review notes
stay). refresh=True asks BHL again, which finds pages scanned since.

Network goes only through the client passed in (BHLClient or a test double);
progress(stage, done, total, message) is called as work proceeds, and cancel
(a threading.Event or a function returning True) is checked between requests.
"""
import json
from collections import defaultdict

from . import saved
from .bhl_client import BHLError
from .harvest import apply_filters, drop_duplicate_scans, extract_pages
from .species_source import SpeciesEntry
from .store import now


CANCELLED_MESSAGE = "Cancelled. Whatever was downloaded is kept; running again carries on from there."


class Cancelled(Exception):
    """Raised inside run_search when cancel is set; the run is saved as cancelled."""


def is_cancelled(cancel):
    if cancel is None:
        return False
    if hasattr(cancel, "is_set"):
        return cancel.is_set()
    return bool(cancel())


def _quiet(*_args, **_kw):
    pass


def name_pages(store, client, name, refresh=False):
    """(pages, source) for a name: BHL's list, from the cache unless refresh
    or never searched. source is 'BHL' or 'cache'. Raises BHLError only when
    BHL fails and nothing is cached."""
    pages = None if refresh else store.cached_name_hits(name)
    if pages is not None:
        return pages, "cache"
    try:
        pages = extract_pages(client.name_metadata(name))
    except BHLError:
        cached = store.cached_name_hits(name)
        if cached is None:
            raise
        return cached, "cache (BHL failed)"
    store.cache_name_hits(name, pages)
    return pages, "BHL"


def _finish(conn, run_id, **fields):
    fields["finished"] = now()
    cols = sorted(fields)
    conn.execute(f"UPDATE runs SET {', '.join(c + '=?' for c in cols)} WHERE run_id=?",
                 [fields[c] for c in cols] + [run_id])
    conn.commit()


def run_search(store, search_id, client, mode="fetch", refresh=False, progress=None,
               cancel=None, log=None):
    """Run a saved search; returns the run summary (see service.run_search)."""
    if mode not in ("count", "fetch"):
        raise ValueError("mode must be 'count' or 'fetch'")
    progress, log = progress or _quiet, log or _quiet
    conn = store.conn
    s = saved.get_search(conn, search_id)
    names = [n for n in s["names"] if n["included"]]
    if not names:
        raise ValueError("This search has no names to search: tick at least one.")
    if mode == "fetch" and not s["filters"]["recorded"]:
        raise ValueError(f"{s['name']} was fetched before Lector kept each search's filters. "
                         "Set its filters first (years, journals, page limit), then run it.")
    opts = saved.options_from_filters(s["filters"])
    settings = {"names": [n["name"] for n in names],
                "held_back": [[n["name"], n["held_back_reason"]] for n in s["names"]
                              if not n["included"]],
                "filters": s["filters"], "refresh": refresh}
    r0 = client.request_count
    run_id = conn.execute(
        "INSERT INTO runs (search_id, started, mode, settings, status) VALUES (?,?,?,?,?)",
        (search_id, now(), mode, json.dumps(settings), "running")).lastrowid
    conn.commit()
    summary = {"run_id": run_id, "search_id": search_id, "mode": mode, "found": 0, "kept": 0,
               "new": 0, "unchanged": 0, "withdrawn": 0, "text_fetched": 0, "failed": 0,
               "requests": 0, "name_requests": 0, "text_requests": 0, "status": "running",
               "message": "", "names": []}
    r_names = [None]                           # request count when the name searches ended

    def counts():
        """requests, name_requests, text_requests of this run so far."""
        total = client.request_count - r0
        names = total if r_names[0] is None else r_names[0] - r0
        return {"requests": total, "name_requests": names, "text_requests": total - names}
    try:
        per_name, failed_names = {}, []
        for i, n in enumerate(names):
            progress("search", i, len(names), f"Searching BHL for {n['name']}")
            if is_cancelled(cancel):
                raise Cancelled
            try:
                pages, source = name_pages(store, client, n["name"], refresh)
            except BHLError as exc:
                failed_names.append(n["name"])
                summary["names"].append({"name": n["name"], "error": str(exc)})
                log(f"  ✗ {n['name']} - {exc}")
                continue
            kept = apply_filters(pages, opts)
            per_name[n["name"]] = (n, pages, kept)
            capped = opts.max_pages and len(kept) == opts.max_pages
            summary["names"].append({"name": n["name"], "found": len(pages), "kept": len(kept),
                                     "capped": bool(capped), "source": source})
            role = "accepted" if n["origin"] == "accepted" else "synonym"
            log(f"  ✓ {n['name']} ({role}) - {len(pages)} pages, {len(kept)} kept"
                + (" (capped)" if capped else "")
                + ("" if source == "BHL" else f"  [{source}; --refresh asks BHL again]"))
            if source == "BHL" and mode == "fetch":
                store.record_search(SpeciesEntry(n["accepted_name"], n["accepted_tvk"]),
                                    n["name"], role, len(pages), len(kept))
        progress("search", len(names), len(names), "Searched")
        r_names[0] = client.request_count
        if names and not per_name:
            raise BHLError("every name search failed")
        found = {p["page_id"] for _n, pages, _k in per_name.values() for p in pages}
        by_id, matched = {}, defaultdict(list)
        for n, _pages, kept in per_name.values():
            for p in kept:
                by_id.setdefault(p["page_id"], p)
                matched[p["page_id"]].append(n)
        kept_list = sorted(by_id.values(), key=lambda p: (p["year"] is None, p["year"] or 0,
                                                          p["page_id"]))
        if opts.skip_duplicates:
            kept_list = drop_duplicate_scans(kept_list)
        kept_ids = [p["page_id"] for p in kept_list]
        summary.update(found=len(found), kept=len(kept_ids))
        if mode == "count":
            summary["status"] = "done"
            summary.update(counts())
            _finish(conn, run_id, found=len(found), kept=len(kept_ids), status="done",
                    failed=len(failed_names), **counts())
            return _numbered(conn, summary)

        _record_pages(store, search_id, run_id, kept_list, matched, failed_names, summary)
        _fetch_texts(store, client, kept_ids, summary, progress, cancel, log)
        summary["status"] = "done"
        _finish(conn, run_id, found=len(found), kept=len(kept_ids), status="done",
                failed=summary["failed"] + len(failed_names),
                message=_message(summary, failed_names), **counts())
    except (Cancelled, KeyboardInterrupt) as exc:
        summary["status"] = "cancelled"
        _finish(conn, run_id, found=summary["found"], kept=summary["kept"], status="cancelled",
                failed=summary["failed"], message=CANCELLED_MESSAGE, **counts())
        if isinstance(exc, KeyboardInterrupt):
            raise
    except BHLError as exc:
        summary.update(status="failed", message=str(exc))
        _finish(conn, run_id, status="failed", message=str(exc), **counts())
    except Exception as exc:                       # record, then let the caller see it
        _finish(conn, run_id, status="failed", message=f"{type(exc).__name__}: {exc}",
                **counts())
        raise
    summary.update(counts())
    if summary["status"] != "done":
        summary["message"] = summary["message"] or conn.execute(
            "SELECT message FROM runs WHERE run_id=?", (run_id,)).fetchone()[0]
    return _numbered(conn, summary)


def _numbered(conn, summary):
    """The run's number within its search, its label and its requests in words."""
    summary["number"] = saved.run_numbers(conn, summary["search_id"]).get(summary["run_id"])
    summary["label"] = saved.run_label(summary["number"])
    summary["requests_text"] = saved.requests_text(summary)
    return summary


def fetch_missing_text(store, search_id, client, progress=None, cancel=None):
    """Download the OCR text of the pages this search holds (current or kept) that
    have none yet. Nothing else: no BHL name searches, no filters applied, nothing
    withdrawn, so it works on a search whose filters were never recorded.
    Recorded in the activity table (Recent activity)."""
    progress = progress or _quiet
    conn = store.conn
    s = saved.get_search(conn, search_id)
    held = [pid for pid, (state, _m) in saved.held_pages(conn, search_id).items()
            if state in ("current", "kept")]
    todo = store.pages_missing_text(page_ids=held)
    r0, started = client.request_count, now()
    summary = {"search_id": search_id, "status": "running", "missing": len(todo),
               "text_fetched": 0, "failed": 0, "requests": 0, "message": ""}
    try:
        _fetch_texts(store, client, held, summary, progress, cancel, _quiet)
        summary["status"] = "done"
    except (Cancelled, KeyboardInterrupt) as exc:
        summary["status"] = "cancelled"
        if isinstance(exc, KeyboardInterrupt):
            raise
    finally:
        summary["requests"] = client.request_count - r0
        left = len(store.pages_missing_text(page_ids=held))
        summary["still_missing"] = left
        n, f = summary["text_fetched"], summary["failed"]
        text = (f"Fetched missing text, “{s['name']}”: {n:,} page{'s' if n != 1 else ''}"
                + (f", {f} failed" if f else "")
                + f", {summary['requests']:,} BHL requests"
                + ("" if summary["status"] == "done" else f" ({summary['status']})"))
        if summary["status"] == "cancelled":
            summary["message"] = (f"Cancelled. Text kept for the {n:,} pages downloaded; "
                                  f"{left:,} still without text.")
        elif not todo:
            summary["message"] = "Every page of this search already has its text."
        else:
            summary["message"] = (f"Text downloaded for {n:,} of {len(todo):,} pages"
                                  + (f"; {f} failed: fetch again to retry them" if f else "")
                                  + ".")
        if summary["status"] != "running":
            conn.execute("INSERT INTO activity (search_id, started, finished, kind, status, text,"
                         " requests) VALUES (?,?,?,?,?,?,?)",
                         (search_id, started, now(), "fetch_text", summary["status"], text,
                          summary["requests"]))
            conn.commit()
    return summary


def _message(summary, failed_names):
    bits = [f"{summary['new']} new, {summary['withdrawn']} withdrawn, "
            f"{summary['unchanged']} unchanged"]
    if failed_names:
        bits.append("BHL failed for " + ", ".join(failed_names))
    if summary["failed"]:
        bits.append(f"{summary['failed']} page texts failed - run again to retry")
    return "; ".join(bits)


def _record_pages(store, search_id, run_id, kept_list, matched, failed_names, summary):
    """Store the pages and their name links; mark new / unchanged / withdrawn."""
    conn = store.conn
    held = saved.held_pages(conn, search_id)
    before = {pid for pid, (state, _m) in held.items() if state in ("current", "kept")}
    kept_ids = set()
    for p in kept_list:
        pid = p["page_id"]
        kept_ids.add(pid)
        store.upsert_page(p)
        for n in matched[pid]:
            store.add_hit(pid, n["accepted_name"], n["name"], n["accepted_tvk"])
        names = ",".join(n["name"] for n in matched[pid])
        status = "unchanged" if pid in before else "new"
        summary[status] += 1
        conn.execute("INSERT OR REPLACE INTO run_pages (run_id, page_id, status, matched_names)"
                     " VALUES (?,?,?,?)", (run_id, pid, status, names))
        conn.execute(
            "INSERT INTO search_pages (search_id, page_id, state, matched_names, first_run,"
            " last_run) VALUES (?,?,'current',?,?,?) ON CONFLICT(search_id, page_id) DO UPDATE"
            " SET state='current', matched_names=excluded.matched_names,"
            " last_run=excluded.last_run", (search_id, pid, names, run_id, run_id))
    failed = {n.lower() for n in failed_names}
    for pid, (state, names) in held.items():
        if state != "current" or pid in kept_ids:
            continue                               # 'kept' pages stay: you chose them
        if failed and any(x.strip().lower() in failed for x in (names or "").split(",")):
            continue                               # its name could not be searched this time
        summary["withdrawn"] += 1
        conn.execute("INSERT OR REPLACE INTO run_pages (run_id, page_id, status, matched_names)"
                     " VALUES (?,?,'withdrawn',?)", (run_id, pid, names))
        conn.execute("UPDATE search_pages SET state='withdrawn', last_run=? WHERE search_id=?"
                     " AND page_id=?", (run_id, search_id, pid))
    conn.commit()


def _fetch_texts(store, client, page_ids, summary, progress, cancel, log):
    todo = store.pages_missing_text(page_ids=page_ids)
    if todo:
        log(f"  … fetching text for {len(todo)} pages (~{len(todo) * getattr(client, '_interval', 1):.0f}s)")
    for i, page_id in enumerate(todo):
        progress("text", i, len(todo), f"Downloading page text {i + 1} of {len(todo)}")
        if is_cancelled(cancel):
            raise Cancelled
        try:
            meta = client.page_metadata(page_id)
        except BHLError as exc:
            summary["failed"] += 1
            log(f"    ✗ page {page_id}: {exc}")
            continue
        names = [n.get("NameCanonical") or n.get("NameFound") or ""
                 for n in meta.get("Names") or []]
        store.save_text(page_id, meta.get("OcrText") or "", meta.get("TextSource"),
                        "; ".join(sorted({n for n in names if n})))
        types = "; ".join(t.get("PageTypeName") or "" for t in meta.get("PageTypes") or [])
        if types:
            store.conn.execute("UPDATE pages SET page_type=? WHERE page_id=? AND page_type IS NULL",
                               (types, page_id))
        summary["text_fetched"] += 1
        if (i + 1) % 25 == 0:
            log(f"    {i + 1}/{len(todo)}")
    progress("text", len(todo), len(todo), "Done")
    if todo:
        log(f"  ✓ text fetched: {len(todo) - summary['failed']}/{len(todo)}"
            + (f"  ({summary['failed']} failed - re-run to retry)" if summary["failed"] else ""))


def harvest_entry(client, store, entry, opts, log=print, progress=None, cancel=None,
                  keep_filters=False, replace=False):
    """Command-line fetch of one species (`fetch`, the interactive console).

    A species with no saved search yet gets one (named after it) with this command's names
    and filters. An existing saved search keeps its own names and filters - your ticks and
    filters from the window are never overwritten from the console (Round 8 review) - unless
    replace=True (`fetch --replace-search`), when it takes this command's names and filters
    (keep_filters=True: the names only). What the run uses is printed either way."""
    conn = store.conn
    log(f"\n■ {entry.name}" + (f"  [{entry.tvk}]" if entry.tvk else "  [no TVK]"))
    names = [{"name": entry.name, "origin": "accepted"}]
    names += [{"name": n, "origin": "user_added" if n in entry.added else "uksi_synonym"}
              for n in entry.synonyms]
    names += [{"name": n, "origin": "uksi_synonym", "included": False, "held_back_reason": r}
              for n, r in entry.held_back]
    sid = saved.find_search(conn, entry.name)
    filters = saved.filters_from_options(opts)
    if sid is None:
        sid = saved.create_search(conn, entry.name, entry.name, entry.tvk, "species", "active",
                                  names, filters)
        log(f"  New saved search \u201c{entry.name}\u201d, with this command's names and filters.")
    elif replace:
        saved.set_names(conn, sid, names, default_accepted=(entry.name, entry.tvk))
        if not keep_filters:
            saved.set_filters(conn, sid, filters)
        saved.update_search(conn, sid, status="active")
        log(f"  Saved search \u201c{entry.name}\u201d: its names"
            + ("" if keep_filters else " and filters") + " replaced by this command's"
            " (--replace-search).")
    else:
        saved.update_search(conn, sid, status="active")
        log(f"  Saved search \u201c{entry.name}\u201d kept as it is: its own names and filters"
            " are used, not this command's (--replace-search would replace them).")
    _log_search_used(conn, sid, log)
    if not saved.get_filters(conn, sid)["recorded"]:
        log(f"  ! {entry.name} was fetched before Lector kept filters, so it is not re-run here."
            "\n    Set its filters in the Lector window (Edit), or run `fetch` again with your"
            " filters (e.g. --include-title ...) and --replace-search.")
        return None
    result = run_search(store, sid, client, "count" if opts.count_only else "fetch",
                        refresh=opts.refresh, progress=progress, cancel=cancel, log=log)
    if result["mode"] == "fetch" and result["status"] == "done" and (result["new"] or result["withdrawn"]):
        log(f"  {result['new']} new pages, {result['withdrawn']} no longer within the filters"
            " (withdrawn; your notes on them are kept)")
    return result


def _log_search_used(conn, sid, log):
    """The names and filters a console run uses, as the window shows them."""
    from .summary import scope_text, years_text
    s = saved.get_search(conn, sid)
    f = s["filters"]
    used = [n["name"] for n in s["names"] if n["included"]]
    log("  Names: " + ", ".join(used))
    for n in s["names"]:
        if not n["included"]:
            log(f"  - {n['name']}: {n['held_back_reason'] or 'not ticked'}")
    if f["recorded"]:
        log(f"  Filters: {scope_text(f)}; {years_text(f)}; page limit "
            + (f"{f['max_pages']:,} per name" if f["max_pages"] else "none")
            + ("; index pages left out" if f["skip_index"] else ""))
