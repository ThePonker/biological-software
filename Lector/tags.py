"""Reading-list tags: the four standard ones and your own (Round 15).

The standard tags (review.REVIEW_TAGS) are fixed. Your own live in user_tags: a key
('u1', 'u2'...) that page_hits.review_tag stores and that never changes, a label you can
rename, and a hidden flag. A tag in use (some page carries it) cannot be deleted, only
hidden; hidden tags leave the review pane's buttons but pages that carry them still show
the label. Plain functions over an open connection; service.py is the public API.
"""
from .review import REVIEW_TAGS
from .store import now

STANDARD_LABELS = {"record": "Record", "biology": "Biology", "mention": "Mention",
                   "index": "Index or list"}


def _clean(label):
    return " ".join((label or "").split())


def in_use(conn, key):
    """Pages that carry this tag."""
    return conn.execute("SELECT COUNT(DISTINCT page_id) FROM page_hits WHERE review_tag=?",
                        (key,)).fetchone()[0]


def list_tags(conn, include_hidden=True):
    """[{key, label, standard, hidden, in_use}]: the standard tags, then yours in order."""
    out = [{"key": k, "label": STANDARD_LABELS[k], "standard": True, "hidden": False,
            "in_use": in_use(conn, k)} for k in REVIEW_TAGS]
    for r in conn.execute("SELECT * FROM user_tags ORDER BY position, tag_key"):
        out.append({"key": r["tag_key"], "label": r["label"], "standard": False,
                    "hidden": bool(r["hidden"]), "in_use": in_use(conn, r["tag_key"])})
    return out if include_hidden else [t for t in out if not t["hidden"]]


def label_map(conn):
    return {t["key"]: t["label"] for t in list_tags(conn)}


def exists(conn, key):
    return key in REVIEW_TAGS or bool(
        conn.execute("SELECT 1 FROM user_tags WHERE tag_key=?", (key,)).fetchone())


def _check_label(conn, label, except_key=None):
    label = _clean(label)
    if not label:
        raise ValueError("A tag needs a name.")
    for t in list_tags(conn):
        if t["key"] != except_key and t["label"].lower() == label.lower():
            raise ValueError(f"There is already a tag called “{t['label']}”.")
    return label


def add_tag(conn, label):
    """Add your own tag; returns its key."""
    label = _check_label(conn, label)
    n = 1 + max([int(r[0][1:]) for r in conn.execute("SELECT tag_key FROM user_tags")] or [0])
    pos = 1 + (conn.execute("SELECT MAX(position) FROM user_tags").fetchone()[0] or 0)
    conn.execute("INSERT INTO user_tags (tag_key, label, hidden, position, created)"
                 " VALUES (?,?,0,?,?)", (f"u{n}", label, pos, now()))
    conn.commit()
    return f"u{n}"


def _user_tag(conn, key):
    if key in REVIEW_TAGS:
        raise ValueError("The four standard tags cannot be changed.")
    if not conn.execute("SELECT 1 FROM user_tags WHERE tag_key=?", (key,)).fetchone():
        raise KeyError(f"No tag {key}")


def rename_tag(conn, key, label):
    _user_tag(conn, key)
    label = _check_label(conn, label, key)
    conn.execute("UPDATE user_tags SET label=? WHERE tag_key=?", (label, key))
    conn.commit()


def set_hidden(conn, key, hidden=True):
    _user_tag(conn, key)
    conn.execute("UPDATE user_tags SET hidden=? WHERE tag_key=?", (int(bool(hidden)), key))
    conn.commit()


def delete_tag(conn, key):
    """Delete a tag no page carries; a tag in use can only be hidden."""
    _user_tag(conn, key)
    n = in_use(conn, key)
    if n:
        raise ValueError(f"{n} page{'s carry' if n != 1 else ' carries'} this tag, so it "
                         "cannot be deleted: hide it instead.")
    conn.execute("DELETE FROM user_tags WHERE tag_key=?", (key,))
    conn.commit()
