"""
Species accounts -- the one reader.

Two layers, never mixed:

    review accounts   codex.db.species_profiles, one per species per review,
                      verbatim and cited. Written only by
                      scripts/import_status_review.py. Never edited.
    your account      observatum.db.species_profiles, one per species, keyed on
                      TVK. Written only by the profile editor.

Every display in the suite gets its text from here rather than querying either
table itself. Seven separate copies of "SELECT profile_text ... WHERE
species_tvk = ?, else by name" existed before this; a rule written seven times
drifts (05_Rules.md).

    from shared.species_accounts import get_species_accounts
    acc = get_species_accounts(tvk, species_name)
    acc.own                 # your text, or None
    acc.reviews             # [ReviewAccount], current review first
    acc.current_review      # the newest non-superseded one, or None
    acc.preview_text()      # what a short display should show, or None

Read-only. Opens each database read-only per call; displays ask for one species
at a time, so there is nothing to cache.
"""

import os
import sqlite3
import sys
from dataclasses import dataclass, field
from typing import List, Optional

try:
    import paths  # noqa: F401
except ImportError:  # pragma: no cover -- run from outside the project root
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import paths  # noqa: E402


@dataclass
class ReviewAccount:
    text: str
    source: str = ""                  # full citation as imported
    review_id: int = 0
    review_name: str = ""
    author: str = ""                  # e.g. "Lane, 2026"
    date_published: str = ""
    licence: Optional[str] = None
    superseded: bool = False

    @property
    def cite(self) -> str:
        """Short citation for display: 'Lane, 2026', else the stored source."""
        return self.author or self.source or self.review_name or "published review"


@dataclass
class SpeciesAccounts:
    tvk: Optional[str] = None
    species_name: Optional[str] = None
    own: Optional[str] = None
    own_updated: Optional[str] = None
    reviews: List[ReviewAccount] = field(default_factory=list)

    @property
    def current_review(self) -> Optional[ReviewAccount]:
        for r in self.reviews:
            if not r.superseded:
                return r
        return None

    @property
    def has_any(self) -> bool:
        return bool(self.own or self.reviews)

    def preview_text(self) -> Optional[str]:
        """Text for a short display (the ~300-character previews).

        Your account where you have written one -- it is the one you would
        quote. Otherwise the current review's, with its citation in front, so
        a reader can never mistake published text for yours.
        """
        if self.own:
            return self.own
        r = self.current_review
        if r and r.text:
            return f"[{r.cite}] {r.text}"
        return None


def _ro(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _review_accounts(tvk, species_name, codex_db):
    try:
        c = _ro(codex_db)
    except sqlite3.Error:
        return []
    try:
        where, arg = ("p.tvk = ?", tvk) if tvk else ("p.species_name = ?", species_name)
        rows = c.execute(f"""
            SELECT p.profile_text, p.source, p.review_id,
                   r.review_name, r.author, r.date_published, r.licence,
                   EXISTS (SELECT 1 FROM reviews r2
                           WHERE r2.supersedes_id = p.review_id) AS superseded
            FROM species_profiles p
            LEFT JOIN reviews r ON r.id = p.review_id
            WHERE {where}
            ORDER BY superseded, COALESCE(r.date_published, '') DESC""",
            (arg,)).fetchall()
    except sqlite3.Error:
        # An older codex.db without review_id: one account per TVK, unlinked
        try:
            rows = [(t, s, 0, None, None, None, None, 0) for t, s in c.execute(
                "SELECT profile_text, source FROM species_profiles WHERE tvk = ?",
                (tvk,))] if tvk else []
        except sqlite3.Error:
            rows = []
    finally:
        c.close()
    return [ReviewAccount(text=t or "", source=s or "", review_id=rid or 0,
                          review_name=rn or "", author=au or "",
                          date_published=dp or "", licence=lic,
                          superseded=bool(sup))
            for t, s, rid, rn, au, dp, lic, sup in rows if t]


def _own_account(tvk, species_name, observatum_db):
    try:
        c = _ro(observatum_db)
    except sqlite3.Error:
        return None, None
    try:
        row = None
        if tvk:
            row = c.execute("SELECT profile_text, updated_at FROM species_profiles "
                            "WHERE species_tvk = ?", (tvk,)).fetchone()
        if row is None and species_name:
            row = c.execute("SELECT profile_text, updated_at FROM species_profiles "
                            "WHERE species_name = ?", (species_name,)).fetchone()
        return (row[0] or None, row[1]) if row else (None, None)
    except sqlite3.Error:
        return None, None
    finally:
        c.close()


def get_species_accounts(tvk=None, species_name=None,
                         codex_db=None, observatum_db=None) -> SpeciesAccounts:
    """Both layers for one species. Either argument may be None."""
    tvk = (tvk or "").strip() or None
    species_name = (species_name or "").strip() or None
    codex_db = codex_db or str(paths.CODEX_DB)
    observatum_db = observatum_db or str(paths.OBSERVATUM_DB)

    acc = SpeciesAccounts(tvk=tvk, species_name=species_name)
    if not (tvk or species_name):
        return acc
    acc.reviews = _review_accounts(tvk, species_name, codex_db)
    if not acc.reviews and tvk and species_name:
        acc.reviews = _review_accounts(None, species_name, codex_db)
    acc.own, acc.own_updated = _own_account(tvk, species_name, observatum_db)
    return acc


def get_preview_text(tvk=None, species_name=None) -> Optional[str]:
    """Convenience for the display sites that want a single string."""
    return get_species_accounts(tvk, species_name).preview_text()
