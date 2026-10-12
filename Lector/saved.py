"""Saved searches in lector.db: plain functions over an open connection.

A saved search = a target taxon, the names sent to BHL (each included or held
back, with where it came from), a filter set, and its runs. Lector.service is
the public API over this; the engine (Lector.engine) runs searches.
"""
import json

from . import config
from .harvest import HarvestOptions
from .store import now

KINDS = ("species", "family", "list")
STATUSES = ("draft", "active")
ORIGINS = ("accepted", "uksi_synonym", "user_added")

DEFAULT_FILTERS = {
    "from_year": None, "to_year": None, "journal_preset": None,
    "include_words": [], "exclude_words": [],
    "max_pages": config.DEFAULT_MAX_PAGES, "skip_index": False, "skip_duplicates": True,
    "recorded": True,
}


def _row(r):
    return dict(r) if r is not None else None


# --- searches -------------------------------------------------------------
def create_search(conn, name, target_name, target_tvk=None, kind="species", status="draft",
                  names=None, filters=None, notes=None):
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    sid = conn.execute(
        "INSERT INTO saved_searches (name, target_tvk, target_name, kind, status, created,"
        " updated, notes) VALUES (?,?,?,?,?,?,?,?)",
        (name, target_tvk, target_name, kind, status, now(), now(), notes)).lastrowid
    set_names(conn, sid, names if names is not None else
              [{"name": target_name, "origin": "accepted"}],
              default_accepted=(target_name, target_tvk))
    set_filters(conn, sid, filters or {})
    conn.commit()
    return sid


def get_search(conn, sid):
    s = _row(conn.execute("SELECT * FROM saved_searches WHERE search_id=?", (sid,)).fetchone())
    if s is None:
        raise KeyError(f"No saved search {sid}")
    s["names"] = get_names(conn, sid)
    s["filters"] = get_filters(conn, sid)
    return s


def update_search(conn, sid, **fields):
    allowed = {"name", "target_name", "target_tvk", "kind", "status", "notes"}
    bad = set(fields) - allowed
    if bad:
        raise ValueError(f"Cannot update {sorted(bad)}")
    if fields.get("status") and fields["status"] not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    if fields:
        cols = sorted(fields)
        conn.execute(f"UPDATE saved_searches SET {', '.join(c + '=?' for c in cols)}, updated=?"
                     " WHERE search_id=?", [fields[c] for c in cols] + [now(), sid])
        conn.commit()


def touch(conn, sid):
    conn.execute("UPDATE saved_searches SET updated=? WHERE search_id=?", (now(), sid))


def find_search(conn, target_name, name=None, kind="species"):
    row = conn.execute(
        "SELECT search_id FROM saved_searches WHERE kind=? AND target_name=? AND name=?"
        " ORDER BY search_id LIMIT 1", (kind, target_name, name or target_name)).fetchone()
    return row[0] if row else None


def duplicate_search(conn, sid, new_name=None):
    s = get_search(conn, sid)
    return create_search(conn, new_name or f"{s['name']} (copy)", s["target_name"],
                         s["target_tvk"], s["kind"], "draft", s["names"],
                         dict(s["filters"], recorded=True), s["notes"])


# --- names ----------------------------------------------------------------
def get_names(conn, sid):
    rows = conn.execute("SELECT * FROM search_names WHERE search_id=? ORDER BY position, name",
                        (sid,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["included"] = bool(d["included"])
        out.append(d)
    return out


def set_names(conn, sid, names, default_accepted=None):
    """Replace the search's names. Each item: a name string, or a dict with
    name, origin, included, held_back_reason, accepted_name, accepted_tvk."""
    if default_accepted is None:
        s = conn.execute("SELECT target_name, target_tvk FROM saved_searches WHERE search_id=?",
                         (sid,)).fetchone()
        default_accepted = (s[0], s[1])
    conn.execute("DELETE FROM search_names WHERE search_id=?", (sid,))
    seen = set()
    for i, n in enumerate(names):
        n = {"name": n} if isinstance(n, str) else dict(n)
        name = (n.get("name") or "").strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        origin = n.get("origin") or "user_added"
        if origin not in ORIGINS:
            raise ValueError(f"origin must be one of {ORIGINS}")
        conn.execute(
            "INSERT INTO search_names (search_id, name, origin, included, held_back_reason,"
            " accepted_name, accepted_tvk, position) VALUES (?,?,?,?,?,?,?,?)",
            (sid, name, origin, int(bool(n.get("included", True))), n.get("held_back_reason"),
             n.get("accepted_name") or default_accepted[0],
             n.get("accepted_tvk") or (None if n.get("accepted_name") else default_accepted[1]),
             i))
    touch(conn, sid)
    conn.commit()


# --- filters --------------------------------------------------------------
def get_filters(conn, sid):
    r = conn.execute("SELECT * FROM search_filters WHERE search_id=?", (sid,)).fetchone()
    if r is None:
        return dict(DEFAULT_FILTERS)
    f = dict(r)
    f.pop("search_id", None)
    f["include_words"] = json.loads(f["include_words"] or "[]")
    f["exclude_words"] = json.loads(f["exclude_words"] or "[]")
    for k in ("skip_index", "skip_duplicates", "recorded"):
        f[k] = bool(f[k])
    return f


def set_filters(conn, sid, filters):
    """Set (part of) a search's filters; keys as DEFAULT_FILTERS. Setting any
    filter marks the filter set as recorded."""
    f = dict(DEFAULT_FILTERS)
    if conn.execute("SELECT 1 FROM search_filters WHERE search_id=?", (sid,)).fetchone():
        f.update(get_filters(conn, sid))
        f["recorded"] = True
    unknown = set(filters) - set(DEFAULT_FILTERS)
    if unknown:
        raise ValueError(f"Unknown filter(s): {sorted(unknown)}")
    f.update(filters)
    conn.execute(
        "INSERT OR REPLACE INTO search_filters (search_id, from_year, to_year, journal_preset,"
        " include_words, exclude_words, max_pages, skip_index, skip_duplicates, recorded)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (sid, f["from_year"], f["to_year"], f["journal_preset"],
         json.dumps([w for w in f["include_words"] if w.strip()]),
         json.dumps([w for w in f["exclude_words"] if w.strip()]),
         f["max_pages"], int(bool(f["skip_index"])), int(bool(f["skip_duplicates"])),
         int(bool(f["recorded"]))))
    touch(conn, sid)
    conn.commit()


def options_from_filters(f, count_only=False, refresh=False):
    return HarvestOptions(
        from_year=f["from_year"], to_year=f["to_year"], max_pages=f["max_pages"] or 0,
        include_titles=list(f["include_words"]), exclude_titles=list(f["exclude_words"]),
        count_only=count_only, refresh=refresh,
        skip_index=bool(f["skip_index"]), skip_duplicates=bool(f["skip_duplicates"]))


def filters_from_options(opts):
    return {"from_year": opts.from_year, "to_year": opts.to_year,
            "include_words": list(opts.include_titles or []),
            "exclude_words": list(opts.exclude_titles or []),
            "max_pages": opts.max_pages, "skip_index": opts.skip_index,
            "skip_duplicates": opts.skip_duplicates}


# --- presets --------------------------------------------------------------
def presets(conn):
    out = []
    for r in conn.execute("SELECT * FROM journal_presets ORDER BY builtin DESC, name"):
        d = dict(r)
        d["include_words"] = json.loads(d["include_words"])
        d["exclude_words"] = json.loads(d["exclude_words"])
        d["builtin"] = bool(d["builtin"])
        out.append(d)
    return out


def save_preset(conn, name, include_words, exclude_words, description=None):
    conn.execute(
        "INSERT INTO journal_presets (name, description, include_words, exclude_words, builtin)"
        " VALUES (?,?,?,?,0) ON CONFLICT(name) DO UPDATE SET description=excluded.description,"
        " include_words=excluded.include_words, exclude_words=excluded.exclude_words",
        (name, description, json.dumps(list(include_words)), json.dumps(list(exclude_words))))
    conn.commit()


# --- runs and membership --------------------------------------------------
def run_numbers(conn, sid):
    """run_id -> the run's number within its search (1, 2, 3 for its fetch runs, in
    order), or None for a count-only run. run_id itself is shared by every search."""
    out, n = {}, 0
    for run_id, mode in conn.execute("SELECT run_id, mode FROM runs WHERE search_id=?"
                                     " ORDER BY run_id", (sid,)):
        if mode == "count":
            out[run_id] = None
        else:
            n += 1
            out[run_id] = n
    return out


def run_label(number):
    """'Run 2', or 'Count' for a count-only run (number None)."""
    return "Count" if number is None else f"Run {number}"


def requests_text(r):
    """'19 BHL requests (3 name searches, 16 page texts)'; runs made before 12 Oct
    (Round 8) kept only the total."""
    total = r.get("requests")
    if total is None:
        return "requests not recorded"
    head = f"{total:,} BHL request{'s' if total != 1 else ''}"
    names, texts = r.get("name_requests"), r.get("text_requests")
    if names is None or texts is None:
        return head
    bits = [f"{names:,} name search{'es' if names != 1 else ''}",
            f"{texts:,} page text{'s' if texts != 1 else ''}"]
    return f"{head} ({', '.join(bits)})"


def _run_dict(r, numbers):
    d = dict(r)
    d["settings"] = json.loads(d["settings"] or "{}")
    d["number"] = numbers.get(d["run_id"])
    d["label"] = run_label(d["number"])
    d["requests_text"] = requests_text(d)
    return d


def runs(conn, sid):
    numbers = run_numbers(conn, sid)
    return [_run_dict(r, numbers) for r in
            conn.execute("SELECT * FROM runs WHERE search_id=? ORDER BY run_id DESC", (sid,))]


def last_run(conn, sid, mode=None):
    q = "SELECT * FROM runs WHERE search_id=?" + (" AND mode=?" if mode else "")
    r = conn.execute(q + " ORDER BY run_id DESC LIMIT 1", (sid, mode) if mode else (sid,)).fetchone()
    if r is None:
        return None
    return _run_dict(r, run_numbers(conn, sid))


def held_pages(conn, sid):
    """page_id -> (state, matched_names) for pages the search holds or held."""
    return {r[0]: (r[1], r[2]) for r in conn.execute(
        "SELECT page_id, state, matched_names FROM search_pages WHERE search_id=?", (sid,))}


def accepted_names(conn, sid):
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT accepted_name FROM search_names WHERE search_id=?", (sid,))]
