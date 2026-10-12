"""Summaries of saved searches for the main screen (used by service.py)."""
from pathlib import Path

from . import review, saved


def list_searches(c):
    out = []
    for s in c.execute("SELECT * FROM saved_searches ORDER BY COALESCE(updated, created) DESC"):
        sid = s["search_id"]
        names = saved.get_names(c, sid)
        f = saved.get_filters(c, sid)
        rows, _acc = review.search_rows(c, sid)
        last = saved.last_run(c, sid)
        found_last = saved.last_run(c, sid, "fetch")
        out.append({
            **dict(s), "names_total": len(names),
            "names_included": sum(n["included"] for n in names),
            "names_held_back": [n["name"] for n in names if not n["included"]],
            "journal_preset": f["journal_preset"], "years": years_text(f), "scope": scope_text(f),
            "filters_recorded": f["recorded"], "pages_held": len(rows),
            "pages_with_text": sum(r["fetched_at"] is not None for r in rows),
            "pages_without_text": sum(r["fetched_at"] is None for r in rows),
            "reviewed": sum(r["review_status"] != "unreviewed" for r in rows),
            "records_extracted": sum(r["review_status"] == "record_extracted" for r in rows),
            "runs": c.execute("SELECT COUNT(*) FROM runs WHERE search_id=?", (sid,)).fetchone()[0],
            "last_run": _run_brief(last), "found_last": found_last and found_last["found"],
        })
    return out


def dashboard(c):
    searches = list_searches(c)
    runs = c.execute("SELECT r.*, s.name FROM runs r JOIN saved_searches s USING(search_id)"
                     " ORDER BY COALESCE(r.finished, r.started) DESC LIMIT 10").fetchall()
    numbers = {}
    for r in runs:
        if r["search_id"] not in numbers:
            numbers[r["search_id"]] = saved.run_numbers(c, r["search_id"])
    exports = c.execute("SELECT * FROM exports ORDER BY created DESC LIMIT 10").fetchall()
    activity = [{"when": r["finished"] or r["started"], "kind": "run",
                 "text": _run_text(r, numbers[r["search_id"]].get(r["run_id"]))} for r in runs]
    activity += [{"when": e["created"], "kind": "export",
                  "text": f"Exported {Path(e['path']).name} ({e['pages'] or 0} pages)"}
                 for e in exports]
    activity += [{"when": a["finished"] or a["started"], "kind": a["kind"], "text": a["text"]}
                 for a in c.execute("SELECT * FROM activity ORDER BY COALESCE(finished, started)"
                                    " DESC LIMIT 10")]
    activity.sort(key=lambda a: a["when"] or "", reverse=True)
    items = []
    for s in searches:
        sid = s["search_id"]
        if s["names_held_back"] and s["status"] == "active":
            items.append({"text": f"{s['name']}: {', '.join(s['names_held_back'])} held back "
                                  "(UKSI synonym checks); confirm them in the search to use them.",
                          "search_id": sid, "action": None})
        if not s["filters_recorded"]:
            items.append({"text": f"{s['name']}: the filters of its first fetch were not "
                                  "recorded. Set the filters before running it again.",
                          "search_id": sid, "action": "set_filters"})
        if s["pages_without_text"]:
            n = s["pages_without_text"]
            items.append({"text": f"{s['name']}: {n:,} page{'s' if n != 1 else ''} still "
                                  "without text.",
                          "search_id": sid, "action": "fetch_text", "pages": n})
    return {"searches": len(searches),
            "pages_harvested": sum(s["pages_held"] for s in searches),
            "awaiting_review": sum(s["pages_held"] - s["reviewed"] for s in searches),
            "records_extracted": sum(s["records_extracted"] for s in searches),
            "activity": activity[:10], "attention": [i["text"] for i in items],
            "attention_items": items}


def years_text(f):
    """The years of a filter set, as every screen shows them."""
    a, b = f.get("from_year"), f.get("to_year")
    if not a and not b:
        return "All years"
    if a and b:
        return f"{a}\u2013{b}"
    return f"From {a}" if a else f"To {b}"


def scope_text(f):
    """The journals of a filter set in words: the ONE description every screen uses
    (Saved searches' Scope column, a search's summary)."""
    if not f.get("recorded", True):
        return "Filters not recorded"
    inc, exc = f.get("include_words") or [], f.get("exclude_words") or []
    if f.get("journal_preset"):
        text = f["journal_preset"]
    elif inc:
        text = f"Your title words ({len(inc)})"
    else:
        text = "Any journal"
    if exc and not f.get("journal_preset"):         # a preset's own words go unsaid
        text += f", {len(exc)} word{'s' if len(exc) != 1 else ''} left out"
    return text


def _run_brief(r):
    if not r:
        return None
    out = {k: r[k] for k in ("run_id", "started", "finished", "mode", "status", "found",
                             "kept", "requests", "failed", "name_requests", "text_requests")}
    out.update(number=r["number"], label=r["label"], requests_text=r["requests_text"])
    return out


def _run_text(r, number):
    if r["mode"] == "count":
        return f"Count only, {r['name']}: {r['found'] or 0} found, {r['kept'] or 0} within filters"
    return (f"{saved.run_label(number)} of “{r['name']}”: {r['kept'] or 0} pages"
            + (f", {saved.requests_text(dict(r))}" if r["requests"] is not None else "")
            + ("" if r["status"] in ("done", "migrated") else f" ({r['status']})"))
