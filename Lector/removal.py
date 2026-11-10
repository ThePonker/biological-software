"""Deleting a saved search and removing its not-relevant pages (Round 15).

Both back lector.db up first with conn.backup() into the backup folder upgrade.py uses
(data\\_backups): lector_pre_delete_<time>.db and lector_pre_remove_<time>.db, then change
the file in ONE transaction. Nothing here touches page text except the removal of a page
no other search holds (see remove_not_relevant). Plain functions over an open connection;
service.py is the public API.
"""
import sqlite3
from datetime import datetime
from pathlib import Path

from . import review, saved


def _marks(n):
    return ",".join("?" * n)


def backup_database(conn, backup_dir, label, commit=True):
    """conn.backup() of the open database to <backup_dir>/lector_pre_<label>_<time>.db
    (never overwrites a file). Returns the path. commit=False: called inside a transaction
    already holding the write lock, which it must not end."""
    if commit:
        conn.commit()
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = f"{datetime.now():%Y%m%d_%H%M%S}"
    dest, n = backup_dir / f"lector_pre_{label}_{stamp}.db", 1
    while dest.exists():
        n += 1
        dest = backup_dir / f"lector_pre_{label}_{stamp}_{n}.db"
    dst = sqlite3.connect(str(dest))
    src = conn
    if not commit:      # our own connection holds the write lock: copy through a reader,
        path = conn.execute("PRAGMA database_list").fetchone()[2]   # which sees the file as
        src = sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True)  # locked
    try:
        src.backup(dst)
    finally:
        dst.close()
        if src is not conn:
            src.close()
    return dest


def _in_one_transaction(conn, work):
    conn.commit()
    try:
        conn.execute("BEGIN IMMEDIATE")
        result = work()
        conn.commit()
        return result
    except BaseException:
        conn.rollback()
        raise


# --- delete a search -------------------------------------------------------------------
def _own_hits(conn, sid):
    """(page_id, accepted_name) review links that belong only to this search: its species'
    marks on its pages, unless another saved search of the same species holds the page too."""
    accepted = saved.accepted_names(conn, sid)
    if not accepted:
        return []
    pages = [r[0] for r in conn.execute("SELECT page_id FROM search_pages WHERE search_id=?",
                                        (sid,))]
    out = []
    for a in accepted:
        for i in range(0, len(pages), 500):
            chunk = pages[i:i + 500]
            for pid, status, notes in conn.execute(
                    f"SELECT page_id, review_status, notes FROM page_hits WHERE accepted_name=?"
                    f" AND page_id IN ({_marks(len(chunk))})", [a] + chunk).fetchall():
                shared = conn.execute(
                    "SELECT 1 FROM search_pages sp JOIN search_names n USING(search_id)"
                    " WHERE sp.page_id=? AND n.accepted_name=? AND sp.search_id != ? LIMIT 1",
                    (pid, a, sid)).fetchone()
                if not shared:
                    out.append((pid, a, status != "unreviewed" or bool(notes)))
    return out


def delete_preview(conn, sid):
    """What deleting the search would remove and keep (nothing is changed)."""
    s = saved.get_search(conn, sid)
    held = [r[0] for r in conn.execute("SELECT page_id FROM search_pages WHERE search_id=?",
                                       (sid,))]
    shared = [p for p in held if conn.execute(
        "SELECT 1 FROM search_pages WHERE page_id=? AND search_id != ?", (p, sid)).fetchone()]
    own = _own_hits(conn, sid)
    return {"search_id": sid, "name": s["name"],
            "runs": conn.execute("SELECT COUNT(*) FROM runs WHERE search_id=?", (sid,)).fetchone()[0],
            "names": len(s["names"]), "pages": len(held), "pages_shared": len(shared),
            "marks": sum(1 for _p, _a, marked in own if marked)}


def delete_search(conn, sid, backup_dir):
    """Back up, then in one transaction delete the search, its runs, names, filters and
    page links, and the review marks that belong only to it. Page texts and every page
    row stay (pages other searches hold are untouched).

    What is deleted is worked out INSIDE the transaction, after the write lock is taken
    (a run in another window cannot slip in between), and the backup is taken there too,
    so it holds exactly what is deleted. The preview shown for the confirmation is an
    estimate: the result carries the figures found inside, and `estimate` (the earlier
    ones) with `estimate_differed` when they were not the same.
    Returns {backup, estimate, estimate_differed, ...preview figures}."""
    estimate = delete_preview(conn, sid)

    def work():
        info = delete_preview(conn, sid)
        own = _own_hits(conn, sid)
        dest = backup_database(conn, backup_dir, "delete", commit=False)
        conn.executemany("DELETE FROM page_hits WHERE page_id=? AND accepted_name=?",
                         [(p, a) for p, a, _m in own])
        conn.execute("DELETE FROM run_pages WHERE run_id IN"
                     " (SELECT run_id FROM runs WHERE search_id=?)", (sid,))
        for table in ("runs", "search_pages", "search_names", "search_filters"):
            conn.execute(f"DELETE FROM {table} WHERE search_id=?", (sid,))
        conn.execute("DELETE FROM saved_searches WHERE search_id=?", (sid,))
        return dict(info, backup=str(dest))
    done = _in_one_transaction(conn, work)
    return dict(done, estimate=estimate, estimate_differed=done_differs(done, estimate))


def done_differs(done, estimate):
    return any(done[k] != estimate[k] for k in estimate if k in done and k != "backup")


# --- remove not-relevant pages ---------------------------------------------------------
def not_relevant_ids(conn, sid):
    """Pages the search holds (current or kept) whose review status, as the reading list
    shows it, is not_relevant. No other status ever matches."""
    rows, _acc = review.search_rows(conn, sid)
    return [r["page_id"] for r in rows if r["review_status"] == "not_relevant"]


def _held_elsewhere(conn, page_id, sid):
    return bool(conn.execute("SELECT 1 FROM search_pages WHERE page_id=? AND search_id != ?",
                             (page_id, sid)).fetchone())


def remove_preview(conn, sid):
    ids = not_relevant_ids(conn, sid)
    shared = sum(1 for p in ids if _held_elsewhere(conn, p, sid))
    return {"search_id": sid, "pages": len(ids), "pages_shared": shared,
            "pages_deleted": len(ids) - shared}


def remove_not_relevant(conn, sid, backup_dir):
    """Back up, then in one transaction take the search's not-relevant pages out of it:
    their links (search_pages, and this search's run_pages) go; a page no other search
    holds also loses its page row, text and review marks; a page another search holds
    stays whole.

    The pages are worked out INSIDE the transaction after the write lock is taken, and the
    backup is taken there too. The earlier count is an estimate: the result carries the
    figures found inside, plus `estimate` and `estimate_differed`.
    Returns {backup, pages, pages_shared, pages_deleted, estimate, estimate_differed}."""
    estimate = remove_preview(conn, sid)

    def work():
        ids = not_relevant_ids(conn, sid)
        shared = [p for p in ids if _held_elsewhere(conn, p, sid)]
        info = {"search_id": sid, "pages": len(ids), "pages_shared": len(shared),
                "pages_deleted": len(ids) - len(shared), "backup": None}
        if not ids:
            return info
        info["backup"] = str(backup_database(conn, backup_dir, "remove", commit=False))
        gone = [p for p in ids if p not in set(shared)]
        conn.executemany("DELETE FROM search_pages WHERE search_id=? AND page_id=?",
                         [(sid, p) for p in ids])
        conn.executemany(
            "DELETE FROM run_pages WHERE page_id=? AND run_id IN"
            " (SELECT run_id FROM runs WHERE search_id=?)", [(p, sid) for p in ids])
        conn.executemany("DELETE FROM page_hits WHERE page_id=?", [(p,) for p in gone])
        conn.executemany("DELETE FROM pages WHERE page_id=?", [(p,) for p in gone])
        return info
    done = _in_one_transaction(conn, work)
    return dict(done, estimate=estimate, estimate_differed=done_differs(done, estimate))
