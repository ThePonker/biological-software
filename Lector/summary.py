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
            "journal_preset": f["journal_preset"], "years": _years(f),
            "filters_recorded": f["recorded"], "pages_held": len(rows),
            "pages_with_text": sum(r["fetched_at"] is not None for r in rows),
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
    exports = c.execute("SELECT * FROM exports ORDER BY created DESC LIMIT 10").fetchall()
    activity = [{"when": r["finished"] or r["started"], "kind": "run",
                 "text": _run_text(r)} for r in runs]
    activity += [{"when": e["created"], "kind": "export",
                  "text": f"Exported {Path(e['path']).name} ({e['pages'] or 0} pages)"}
                 for e in exports]
    activity.sort(key=lambda a: a["when"] or "", reverse=True)
    attention = []
    for s in searches:
        if s["names_held_back"] and s["status"] == "active":
            attention.append(f"{s['name']}: {', '.join(s['names_held_back'])} held back "
                             "(UKSI synonym checks); confirm them in the search to use them.")
        if not s["filters_recorded"]:
            attention.append(f"{s['name']}: the filters of its first fetch were not recorded. "
                             "Set the filters before running it again.")
        if s["pages_held"] > s["pages_with_text"]:
            attention.append(f"{s['name']}: {s['pages_held'] - s['pages_with_text']} pages "
                             "still without text; run again to fetch them.")
    return {"searches": len(searches),
            "pages_harvested": sum(s["pages_held"] for s in searches),
            "awaiting_review": sum(s["pages_held"] - s["reviewed"] for s in searches),
            "records_extracted": sum(s["records_extracted"] for s in searches),
            "activity": activity[:10], "attention": attention}

def _years(f):
    a, b = f["from_year"], f["to_year"]
    if not a and not b:
        return "All years"
    if a and b:
        return f"{a}-{b}"
    return f"From {a}" if a else f"Before {b + 1}"


def _run_brief(r):
    if not r:
        return None
    return {k: r[k] for k in ("run_id", "started", "finished", "mode", "status", "found",
                              "kept", "requests", "failed")}


def _run_text(r):
    if r["mode"] == "count":
        return f"Count only, {r['name']}: {r['found'] or 0} found, {r['kept'] or 0} within filters"
    return (f"Ran “{r['name']}”: {r['kept'] or 0} pages"
            + (f", {r['requests']} requests" if r["requests"] is not None else "")
            + ("" if r["status"] in ("done", "migrated") else f" ({r['status']})"))
