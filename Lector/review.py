"""Review list, run comparison and exports for a saved search (used by service.py).

Review state lives on page_hits (review_status, review_tag, notes) per page and
species, so a page reviewed in one search shows as reviewed in every search of
that species. Statuses: unreviewed / relevant / not_relevant / record_extracted.
"""
import json

from . import saved
from .entries import build_entries, citation, source
from .excerpts import _norm, copyright_flag, index_reason, name_pattern, split_marked
from .store import now

REVIEW_STATUSES = ("unreviewed", "relevant", "not_relevant", "record_extracted")
REVIEW_TAGS = ("record", "biology", "mention", "index")
SECTION_LABELS = {"main": "Text", "index": "Likely index or contents page",
                  "no_match": "Name not found in the page text"}


def _marks(n):
    return ",".join("?" * n)


def search_rows(conn, sid, states=("current", "kept")):
    """Page rows held by a search, with the review state of its species."""
    accepted = saved.accepted_names(conn, sid)
    if not accepted:
        return [], []
    rows = conn.execute(
        f"SELECT p.*, sp.state, sp.matched_names AS sp_names,"
        f" GROUP_CONCAT(DISTINCT h.query_name) AS matched_names, MAX(h.tvk) AS tvk,"
        f" GROUP_CONCAT(DISTINCT h.review_status) AS statuses, MAX(h.notes) AS notes,"
        f" MAX(h.review_tag) AS review_tag, MAX(h.reviewed_at) AS reviewed_at"
        f" FROM search_pages sp JOIN pages p USING(page_id)"
        f" LEFT JOIN page_hits h ON h.page_id=p.page_id AND h.accepted_name IN ({_marks(len(accepted))})"
        f" WHERE sp.search_id=? AND sp.state IN ({_marks(len(states))})"
        f" GROUP BY p.page_id", list(accepted) + [sid] + list(states)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["matched_names"] = d["matched_names"] or d.pop("sp_names", None)
        d.pop("sp_names", None)
        d["review_status"] = combined_status(d["statuses"])
        out.append(d)
    return out, accepted


def combined_status(statuses):
    vals = [s for s in (statuses or "").split(",") if s]
    reviewed = [s for s in vals if s != "unreviewed"]
    for s in ("record_extracted", "relevant", "not_relevant"):
        if s in reviewed:
            return s
    return "unreviewed"


def _runs_new_pages(conn, sid):
    last = saved.last_run(conn, sid, "fetch")
    if not last:
        return set()
    return {r[0] for r in conn.execute(
        "SELECT page_id FROM run_pages WHERE run_id=? AND status='new'", (last["run_id"],))}


def _short(row):
    return {"page_id": row["page_id"], "citation": citation(row), "bhl_url": row["page_url"],
            "year": row["year"], "title": row["title"]}


def queue(conn, sid, status=None, order="year", include_withdrawn=False):
    states = ("current", "kept", "withdrawn") if include_withdrawn else ("current", "kept")
    rows, accepted = search_rows(conn, sid, states)
    main, index, no_match = build_entries(rows, order == "journal", accepted)
    new_ids = _runs_new_pages(conn, sid)
    items = []
    for e in sorted(main + index + no_match, key=lambda e: _order(e.row, order)):
        r = e.row
        if status and r["review_status"] != status:
            continue
        pattern = name_pattern(r["names"])
        items.append({
            "page_id": r["page_id"], "citation": citation(r), "source": source(r),
            "year": r["year"], "title": r["title"], "volume": r["volume"],
            "page_label": r["page_label"], "authors": r["authors"],
            "article_title": r["article_title"], "page_type": r["page_type"],
            "section": e.section, "section_label": SECTION_LABELS[e.section],
            "likely_index": e.section == "index",
            "index_reason": index_reason(r) if e.section == "index" else None,
            "excerpts": e.excerpts,
            "excerpt_runs": [split_marked("\n".join(x), pattern) for x in e.excerpts],
            "duplicate_group": r["page_id"] if e.copies else None,
            "copies": [_short(c) for c in e.copies],
            "bhl_url": r["page_url"], "matched_names": r["matched_names"],
            "review_status": r["review_status"], "review_tag": r["review_tag"],
            "notes": r["notes"] or "", "state": r["state"], "has_text": r["fetched_at"] is not None,
            "copyright_note": copyright_flag(r), "new_in_last_run": r["page_id"] in new_ids,
        })
    return items


def _order(r, order):
    if order == "journal":
        return (_norm(r["title"]), r["year"] is None, r["year"] or 0, r["page_id"])
    return (r["year"] is None, r["year"] or 0, _norm(r["title"]), r["page_id"])


def page_detail(conn, sid, page_id):
    rows, accepted = search_rows(conn, sid, ("current", "kept", "withdrawn"))
    row = next((r for r in rows if r["page_id"] == page_id), None)
    if row is None:
        raise KeyError(f"Page {page_id} is not in search {sid}")
    main, index, no_match = build_entries([row], False, accepted, merge_duplicates=False)
    e = (main + index + no_match)[0]
    pattern = name_pattern(e.row["names"])
    return dict(e.row, citation=citation(e.row), source=source(e.row), section=e.section,
                excerpts=e.excerpts, text_runs=split_marked(row["ocr_text"] or "", pattern),
                copyright_note=copyright_flag(row))


def set_review(conn, sid, page_id, status=None, tag=None, notes=None):
    if status is not None and status not in REVIEW_STATUSES:
        raise ValueError(f"status must be one of {REVIEW_STATUSES}")
    if tag not in (None, "") and tag not in REVIEW_TAGS:
        raise ValueError(f"tag must be one of {REVIEW_TAGS}")
    accepted = saved.accepted_names(conn, sid)
    sets, vals = ["reviewed_at=?"], [now()]
    if status is not None:
        sets.append("review_status=?")
        vals.append(status)
    if tag is not None:
        sets.append("review_tag=?")
        vals.append(tag or None)
    if notes is not None:
        sets.append("notes=?")
        vals.append(notes)
    n = conn.execute(
        f"UPDATE page_hits SET {', '.join(sets)} WHERE page_id=? AND accepted_name IN"
        f" ({_marks(len(accepted))})", vals + [page_id] + list(accepted)).rowcount
    conn.commit()
    if not n:
        raise KeyError(f"Page {page_id} has no hit for this search's species")
    return n


def run_pages(conn, run_id):
    return {r[0]: (r[1], r[2]) for r in conn.execute(
        "SELECT page_id, status, matched_names FROM run_pages WHERE run_id=?", (run_id,))}


def diff(conn, run_a, run_b):
    """Pages new / withdrawn / unchanged between two fetch runs of one search."""
    ra = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_a,)).fetchone()
    rb = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_b,)).fetchone()
    if ra is None or rb is None:
        raise KeyError("No such run")
    if ra["search_id"] != rb["search_id"]:
        raise ValueError("Runs belong to different searches")
    if "count" in (ra["mode"], rb["mode"]):
        raise ValueError("Count-only runs hold no pages to compare")
    a = {p for p, (st, _m) in run_pages(conn, run_a).items() if st != "withdrawn"}
    pb = run_pages(conn, run_b)
    b = {p for p, (st, _m) in pb.items() if st != "withdrawn"}
    ids = a | b
    meta = {r["page_id"]: dict(r) for r in conn.execute(
        f"SELECT * FROM pages WHERE page_id IN ({_marks(len(ids))})", list(ids))} if ids else {}
    cached = {r[0] for r in conn.execute(
        "SELECT page_id FROM name_hits WHERE query_name IN"
        " (SELECT name FROM search_names WHERE search_id=? AND included=1)", (ra["search_id"],))}

    def item(pid, why=None):
        row = meta.get(pid, {"page_id": pid})
        d = _short(dict({"page_url": None, "year": None, "title": None}, **row))
        d["matched_names"] = pb.get(pid, (None, None))[1]
        if why:
            d["reason"] = why
        return d

    sa, sb = json.loads(ra["settings"] or "{}"), json.loads(rb["settings"] or "{}")
    return {
        "run_a": run_a, "run_b": run_b,
        "new": [item(p) for p in sorted(b - a)],
        "withdrawn": [item(p, "Now filtered out" if p in cached else "No longer found on BHL")
                      for p in sorted(a - b)],
        "unchanged": [item(p) for p in sorted(a & b)],
        "settings_changed": settings_changes(sa, sb),
    }


def settings_changes(sa, sb):
    out = []
    na, nb = set(sa.get("names") or []), set(sb.get("names") or [])
    if nb - na:
        out.append("added " + ", ".join(sorted(nb - na)))
    if na - nb:
        out.append("removed " + ", ".join(sorted(na - nb)))
    fa, fb = sa.get("filters") or {}, sb.get("filters") or {}
    if not fa and fb:
        out.append("filters recorded from this run on")
    else:
        for k in sorted(set(fa) | set(fb)):
            if k != "recorded" and fa.get(k) != fb.get(k):
                out.append(f"{k.replace('_', ' ')}: {fa.get(k)!r} -> {fb.get(k)!r}")
    return out
