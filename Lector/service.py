"""Lector service: the ONLY API the desktop UI uses. No Qt here.

    svc = LectorService()                       # real data/lector.db, uksi.db, BHL
    svc = LectorService(db_path=..., uksi_db=..., client_factory=lambda: FakeClient())

Every method opens its own database connection and closes it, so any method
can be called from a worker thread. Methods marked NETWORK may talk to BHL
(one request per second) and take progress / cancel arguments:
    progress(stage: str, done: int, total: int, message: str)
    cancel: threading.Event, or any function returning True to stop
Errors meant for the person using Lector are LectorError (message is plain
English); NeedsUpdate means lector.db must be updated first (update_database).
Full reference with examples: Lector/SERVICE_API.md.
"""
import os
from contextlib import contextmanager
from pathlib import Path

from . import config, engine, review, saved, summary, upgrade
from .bhl_client import BHLClient, BHLError
from .previewing import preview_pages
from .schema import NeedsMigration
from .species_source import TVK_RE, UksiLookup
from .store import LectorStore
from .synonyms import SynonymRules, candidate_names

REVIEW_STATUSES = review.REVIEW_STATUSES
REVIEW_TAGS = review.REVIEW_TAGS


class LectorError(Exception):
    """A problem to show to the user as it is."""


class NeedsUpdate(LectorError):
    """lector.db was made by an older Lector: call update_database() (after asking)."""


class LectorService:
    def __init__(self, db_path=None, uksi_db=None, client_factory=None, export_dir=None,
                 synonym_file=None, backup_dir=None):
        self.db_path = Path(db_path or config.LECTOR_DB)
        self.uksi_db = Path(uksi_db or config.UKSI_DB)
        self.export_dir = Path(export_dir or config.EXPORT_DIR)
        self.synonym_file = Path(synonym_file or config.SYNONYM_FILE)
        self.backup_dir = Path(backup_dir or self.db_path.parent / "_backups")
        self._client_factory = client_factory or self._real_client
        self._client = None

    # --- plumbing -------------------------------------------------------
    @contextmanager
    def _store(self):
        try:
            st = LectorStore(self.db_path)
        except NeedsMigration as exc:
            raise NeedsUpdate(str(exc)) from None
        try:
            yield st
        finally:
            st.close()

    @contextmanager
    def _uksi(self):
        u = UksiLookup(self.uksi_db)
        try:
            yield u
        finally:
            u.close()

    @staticmethod
    def _real_client():
        try:
            return BHLClient(config.load_api_key())
        except SystemExit as exc:              # load_api_key's message for the console
            raise LectorError(str(exc).replace("✗ ", "")) from None

    def client(self):
        """The BHL client (made on first use; NETWORK only when called)."""
        if self._client is None:
            self._client = self._client_factory()
        return self._client

    def _rules(self):
        return SynonymRules.load(self.synonym_file)

    # --- settings and database ------------------------------------------
    def settings_info(self):
        """Paths and what is installed. No network."""
        from .pdf import pdf_method
        key_source = None
        if os.environ.get(config.API_KEY_ENV, "").strip():
            key_source = "environment variable " + config.API_KEY_ENV
        elif config.KEY_FILE.exists() and config.KEY_FILE.read_text(encoding="utf-8-sig").strip():
            key_source = str(config.KEY_FILE)

        def has(mod):
            try:
                __import__(mod)
                return True
            except ImportError:
                return False
        st = upgrade.status(self.db_path)
        return {"api_key_set": key_source is not None, "api_key_source": key_source,
                "api_key_url": config.API_KEY_URL, "db_path": str(self.db_path),
                "db_exists": st["exists"], "db_needs_update": st["needs_update"],
                "uksi_db_path": str(self.uksi_db), "uksi_found": self.uksi_db.exists(),
                "export_dir": str(self.export_dir), "synonym_file": str(self.synonym_file),
                "docx_available": has("docx"), "xlsx_available": has("openpyxl"),
                "pdf_method": pdf_method(), "request_interval": config.REQUEST_INTERVAL}

    def needs_update(self):
        """None, or the dry-run report of the update lector.db needs. Changes nothing."""
        if not upgrade.status(self.db_path)["needs_update"]:
            return None
        return upgrade.dry_run(self.db_path, self._name_checker())

    def update_database(self):
        """Back up lector.db (conn.backup) then update it in place. Returns the report."""
        return upgrade.apply(self.db_path, self.backup_dir, self._name_checker())

    def _name_checker(self):
        """Old fetches' names are checked as a new search's are (UKSI + synonym lists)."""
        return upgrade.name_checker(self.uksi_db, self.synonym_file)

    # --- taxa and names (UKSI, read-only) --------------------------------
    def resolve_taxon(self, text):
        """Name or TVK -> {'found', 'tvk', 'name', 'rank', 'family', 'genus',
        'matched_as' ('accepted'|'synonym'|'tvk'|None), 'typed', 'alternatives'}."""
        text = " ".join((text or "").split())
        out = {"found": False, "typed": text, "tvk": None, "name": None, "rank": None,
               "family": None, "genus": None, "matched_as": None, "alternatives": []}
        if not text:
            return out
        with self._uksi() as u:
            if TVK_RE.match(text.upper()):
                rows, how = [t for t in [u.taxon(text.upper())] if t], "tvk"
            else:
                rows, how = u.taxa_named(text), "accepted"
                if not rows:
                    rows = [t for t in (u.taxon(x) for x in u.recommended_for(text)) if t]
                    how = "synonym"
        if not rows:
            return out
        best = rows[0]
        out.update(found=True, tvk=best["tvk"], name=best["scientific_name"], rank=best["rank"],
                   family=best.get("family") or None, genus=best.get("genus") or None,
                   matched_as=how,
                   alternatives=[{"tvk": r["tvk"], "name": r["scientific_name"],
                                  "rank": r["rank"], "family": r.get("family")} for r in rows[1:]])
        return out

    def candidate_names(self, tvk, name=None):
        """Names that could be searched for a species, each checked (LEC3). No network.
        Items: name, origin, included, held_back_reason, conflict_name, conflict_tvk, source."""
        with self._uksi() as u:
            if name is None:
                name = (u.taxon(tvk) or {}).get("scientific_name")
            if not name:
                raise LectorError(f"{tvk} is not in UKSI")
            return candidate_names(u, name, tvk, self._rules())

    def remember_name_choice(self, name, include, species=None, reason=""):
        """Write '+ name' / '- name' (for one species, or all) to data/lector_synonyms.txt."""
        return self._rules().remember("+" if include else "-", name, species, reason)

    # --- saved searches -----------------------------------------------------
    def list_searches(self):
        """One summary dict per saved search, newest activity first."""
        with self._store() as st:
            return summary.list_searches(st.conn)

    def dashboard(self):
        """Totals, recent activity and things needing attention, for the main screen."""
        with self._store() as st:
            return summary.dashboard(st.conn)

    def get_search(self, search_id):
        """Search dict with 'names' (list) and 'filters' (dict), plus 'scope' and
        'years': the filters in words, exactly as list_searches() gives them."""
        with self._store() as st:
            try:
                s = saved.get_search(st.conn, search_id)
            except KeyError as exc:
                raise LectorError(str(exc)) from None
        s["scope"], s["years"] = summary.scope_text(s["filters"]), summary.years_text(s["filters"])
        return s

    def edit_names(self, search_id):
        """The names to show when editing a search: its stored names, then the names
        the UKSI checks hold back for its species that it does not list (unticked, with
        the reason), as a new search shows them. A stored name the checks would hold
        back gets the reason too (held_back_reason), and ticked_by_update=True when it
        is ticked only because the 12 Oct lector.db update ticked it. No network."""
        s = self.get_search(search_id)
        names = [dict(n) for n in s["names"]]
        if s["kind"] != "species" or not s["target_tvk"]:
            return names
        try:
            cands = self.candidate_names(s["target_tvk"], s["target_name"])
        except LectorError:
            return names
        held = {c["name"].lower(): c for c in cands if not c["included"]}
        have = {n["name"].lower() for n in names}
        for n in names:
            c = held.get(n["name"].lower())
            if c and not n.get("held_back_reason"):
                n["held_back_reason"] = c["held_back_reason"]
                # ticked with no reason stored: the lector.db update ticked it, not you
                n["ticked_by_update"] = bool(n["included"]) and n["origin"] != "user_added"
        for key, c in held.items():
            if key not in have:
                names.append({"name": c["name"], "origin": c["origin"], "included": False,
                              "held_back_reason": c["held_back_reason"],
                              "accepted_name": s["target_name"],
                              "accepted_tvk": s["target_tvk"]})
        return names

    def create_search(self, target, name=None, kind="species", names=None, filters=None,
                      status="draft", with_synonyms=True):
        """New saved search. target: a name or TVK (resolved in UKSI), or a
        resolve_taxon() result. kind 'species': names default to the accepted
        name plus checked UKSI synonyms (held-back ones stored, not ticked).
        kind 'family': every UKSI species of the family, accepted names only.
        kind 'list': names = list of names/TVKs, each resolved. Returns the id."""
        t = target if isinstance(target, dict) else self.resolve_taxon(target)
        if kind != "list" and not t.get("found"):
            raise LectorError(f"{t.get('typed') or target} is not in UKSI - check the spelling.")
        if kind == "species" and names is None:
            names = (self.candidate_names(t["tvk"], t["name"]) if with_synonyms
                     else [{"name": t["name"], "origin": "accepted"}])
        elif kind == "family" and names is None:
            names = self.family_names(t["name"])
        elif kind == "list":
            names = [self._list_name(x) for x in names or []]
            t = {"name": t.get("name") or name or "Species list", "tvk": None}
        with self._store() as st:
            return saved.create_search(st.conn, name or t["name"], t["name"], t["tvk"], kind,
                                       status, names, filters)

    def _list_name(self, raw):
        if isinstance(raw, dict):
            return raw
        r = self.resolve_taxon(raw)
        if not r["found"]:
            return {"name": raw, "origin": "user_added", "accepted_name": raw}
        return {"name": r["name"], "origin": "accepted", "accepted_name": r["name"],
                "accepted_tvk": r["tvk"]}

    def update_search(self, search_id, name=None, status=None, notes=None, filters=None,
                      names=None):
        """Change any of: name, status ('draft'/'active'), notes, filters (dict of
        filter keys to change), names (full list: strings or dicts)."""
        with self._store() as st:
            fields = {k: v for k, v in (("name", name), ("status", status), ("notes", notes))
                      if v is not None}
            try:
                saved.update_search(st.conn, search_id, **fields)
                if filters is not None:
                    saved.set_filters(st.conn, search_id, filters)
                if names is not None:
                    saved.set_names(st.conn, search_id, names)
            except ValueError as exc:
                raise LectorError(str(exc)) from None
        return self.get_search(search_id)

    def duplicate_search(self, search_id, new_name=None):
        with self._store() as st:
            return saved.duplicate_search(st.conn, search_id, new_name)

    def journal_presets(self):
        with self._store() as st:
            return saved.presets(st.conn)

    def save_preset(self, name, include_words, exclude_words, description=None):
        with self._store() as st:
            saved.save_preset(st.conn, name, include_words, exclude_words, description)

    # --- counts, preview, runs (NETWORK) ------------------------------------
    def name_counts(self, names, refresh=False, progress=None, cancel=None):
        """NETWORK unless cached: pages BHL has for each name, before filters.
        {name: {'found': int|None, 'source': 'BHL'|'cache'|..., 'error': str|None}}."""
        out = {}
        with self._store() as st:
            for i, n in enumerate(names):
                if engine.is_cancelled(cancel):
                    break
                if progress:
                    progress("count", i, len(names), f"Counting {n} on BHL")
                try:
                    pages, src = engine.name_pages(st, self.client(), n, refresh)
                    out[n] = {"found": len(pages), "source": src, "error": None}
                except BHLError as exc:
                    out[n] = {"found": None, "source": None, "error": str(exc)}
        return out

    def preview(self, search_id, use_network=False, refresh=False, progress=None, cancel=None):
        """Found / within filters / already held / to download / est. seconds.
        Without use_network, names never searched are listed in 'not_counted'."""
        with self._store() as st:
            s = saved.get_search(st.conn, search_id)
            return preview_pages(st, self.client, s["names"], s["filters"], use_network,
                                 refresh, progress, cancel)

    def preview_draft(self, names, filters=None, use_network=False, refresh=False,
                      progress=None, cancel=None, count_all=True):
        """NETWORK only with use_network. Preview of names and filters not saved yet
        (the search builder). names: [str or {'name', 'included'}]; filters: dict
        (missing keys = defaults). As preview(), plus name_found {name: pages or None}
        for every name (ticked or not, unless count_all=False)."""
        with self._store() as st:
            return preview_pages(st, self.client, names, filters, use_network, refresh,
                                 progress, cancel, count_all)

    def default_filters(self):
        """The filters a new search starts with."""
        return {k: (list(v) if isinstance(v, list) else v)
                for k, v in saved.DEFAULT_FILTERS.items()}

    def family_names(self, family):
        """Names a family search would use: every UKSI species, accepted names only."""
        with self._uksi() as u:
            return [{"name": n, "origin": "accepted", "included": True, "accepted_name": n,
                     "accepted_tvk": v, "held_back_reason": None}
                    for v, n in u.family_species(family)]

    def run_search(self, search_id, mode="fetch", refresh=True, progress=None, cancel=None):
        """NETWORK. Run a saved search: 'count' (no pages stored) or 'fetch'.
        refresh=True asks BHL afresh for every name (finds new scans); False
        re-uses BHL's last answers and only re-applies the filters.
        Returns {'run_id', 'status' ('done'|'cancelled'|'failed'), 'found', 'kept',
        'new', 'unchanged', 'withdrawn', 'text_fetched', 'failed', 'requests',
        'message', 'names': [per-name dicts]}."""
        with self._store() as st:
            try:
                result = engine.run_search(st, search_id, self.client(), mode, refresh,
                                           progress, cancel)
            except ValueError as exc:
                raise LectorError(str(exc)) from None
            saved.update_search(st.conn, search_id, status="active")
            return result

    def fetch_missing_text(self, search_id, progress=None, cancel=None):
        """NETWORK. Download the text of the pages this search holds that have none,
        and nothing else: no name searches, no filters, nothing withdrawn (works when
        the search's filters were never recorded). Shown under Recent activity.
        {'status' ('done'/'cancelled'), 'missing', 'text_fetched', 'failed',
        'still_missing', 'requests', 'message'}."""
        with self._store() as st:
            try:
                return engine.fetch_missing_text(st, search_id, self.client(), progress, cancel)
            except KeyError as exc:
                raise LectorError(str(exc)) from None

    # --- history -------------------------------------------------------------
    def list_runs(self, search_id):
        """Runs newest first, each with its settings snapshot and page counts."""
        with self._store() as st:
            out = saved.runs(st.conn, search_id)
            for r in out:
                r.update({k: 0 for k in ("new", "unchanged", "withdrawn")})
                for status, n in st.conn.execute("SELECT status, COUNT(*) FROM run_pages WHERE"
                                                 " run_id=? GROUP BY status", (r["run_id"],)):
                    r[status] = n
            return out

    def run_diff(self, search_id, run_a=None, run_b=None):
        """Compare two fetch runs (default: the last two). {'new', 'withdrawn',
        'unchanged': [page dicts], 'settings_changed': [str]} or None if <2 runs."""
        with self._store() as st:
            fetches = [r["run_id"] for r in saved.runs(st.conn, search_id) if r["mode"] == "fetch"]
            if run_b is None:
                if len(fetches) < 2:
                    return None
                run_b, run_a = fetches[0], fetches[1]
            try:
                d = review.diff(st.conn, run_a, run_b)
            except (KeyError, ValueError) as exc:
                raise LectorError(str(exc)) from None
            numbers = saved.run_numbers(st.conn, search_id)
            d["number_a"], d["number_b"] = numbers.get(d["run_a"]), numbers.get(d["run_b"])
            return d

    def keep_page(self, search_id, page_id):
        """Keep a withdrawn page in the search anyway."""
        with self._store() as st:
            st.conn.execute("UPDATE search_pages SET state='kept' WHERE search_id=? AND page_id=?",
                            (search_id, page_id))

    # --- review --------------------------------------------------------------
    def review_queue(self, search_id, status=None, order="year", include_withdrawn=False):
        """Pages of a search for reading, duplicates grouped (copies inside)."""
        with self._store() as st:
            return review.queue(st.conn, search_id, status, order, include_withdrawn)

    def page_detail(self, search_id, page_id):
        with self._store() as st:
            try:
                return review.page_detail(st.conn, search_id, page_id)
            except KeyError as exc:
                raise LectorError(str(exc)) from None

    def set_review(self, search_id, page_id, status=None, tag=None, notes=None):
        """Set review status / tag / notes of a page (None = leave as is)."""
        with self._store() as st:
            try:
                review.set_review(st.conn, search_id, page_id, status, tag, notes)
            except (KeyError, ValueError) as exc:
                raise LectorError(str(exc)) from None

    # --- export --------------------------------------------------------------
    def export(self, search_id, formats=("docx", "xlsx"), order="year", include_appendices=True,
               include_statuses=("unreviewed", "relevant", "record_extracted"),
               include_notes=True, out_dir=None):
        """Write files for a search. formats: any of 'txt', 'docx', 'xlsx', 'pdf'
        (pdf implies docx). Returns {'files': {fmt: path}, 'messages': [str], 'counts'}."""
        from .exporting import export_search
        with self._store() as st:
            return export_search(st, search_id, formats, order, include_appendices,
                                 include_statuses, include_notes,
                                 Path(out_dir) if out_dir else self.export_dir)

    def list_exports(self, search_id=None):
        with self._store() as st:
            q = "SELECT * FROM exports" + (" WHERE search_id=?" if search_id else "")
            return [dict(r) for r in st.conn.execute(q + " ORDER BY created DESC",
                                                     (search_id,) if search_id else ())]


