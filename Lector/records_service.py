"""LectorService methods for extracted records and the BHL API key (Round 15b; a mixin so
service.py stays readable). No Qt. The names are LectorService methods (SERVICE_API.md)."""
from . import config, records
from .bhl_client import BHLError


def _lector_error(message):
    from .service import LectorError
    return LectorError(message)


class RecordsMixin:
    # --- extracted records -------------------------------------------------------------
    def record_prefill(self, search_id, page_id):
        """The fields of a new record read from this page: the search's species and the
        page's citation, title, volume, page, year and BHL address."""
        d = self.page_detail(search_id, page_id)
        s = self.get_search(search_id)
        return {"species": s["target_name"] if s["kind"] in ("species", "family")
                else (d.get("matched_names") or "").split(",")[0],
                "citation": d["citation"], "source_title": d.get("title"),
                "source_volume": d.get("volume"), "source_page": d.get("page_label"),
                "source_year": d.get("year"), "bhl_url": d.get("page_url")}

    def _record_fields(self, fields):
        """Check the species in UKSI as the search builder does: a name UKSI knows is stored
        as UKSI's current name (with its TVK); an old name is kept in the comment."""
        f = dict(fields)
        typed = " ".join(str(f.get("species") or "").split())
        if typed:
            t = self.resolve_taxon(typed)
            if t["found"] and not t.get("uksi_missing"):
                f["species"], f["species_tvk"] = t["name"], t["tvk"]
                if t["matched_as"] == "synonym" and typed.lower() != t["name"].lower():
                    note = f"Name as printed: {typed}."
                    f["comment"] = " ".join(x for x in ((f.get("comment") or "").strip(), note)
                                            if x)
        return f

    def add_record(self, search_id, page_id, fields):
        """Store a record read from a page and mark the page 'Record extracted'. Returns the
        new record_id. LectorError for a field that fails its check."""
        try:
            f = self._record_fields(fields)
            with self._store() as st:
                rid = records.add(st.conn, page_id, search_id, f)
        except ValueError as exc:
            raise _lector_error(str(exc)) from None
        try:
            self.set_review(search_id, page_id, status="record_extracted")
        except Exception:  # noqa: BLE001 - the record is saved; the mark is a convenience
            pass
        return rid

    def get_record(self, record_id):
        with self._store() as st:
            try:
                return records.get(st.conn, record_id)
            except KeyError as exc:
                raise _lector_error(str(exc).strip("'\"")) from None

    def update_record(self, record_id, fields):
        try:
            f = self._record_fields(fields)
            with self._store() as st:
                records.update(st.conn, record_id, f)
        except (ValueError, KeyError) as exc:
            raise _lector_error(str(exc).strip("'\"")) from None

    def list_records(self, search_id=None, species=None, year=None):
        """Extracted records, newest first, each with 'search_name'."""
        with self._store() as st:
            return records.listing(st.conn, search_id, species, year)

    def record_filter_choices(self):
        """{searches: [{search_id, name}], species: [str], years: [int]} that have records."""
        with self._store() as st:
            return records.filter_choices(st.conn)

    def remove_record(self, record_id):
        """Back lector.db up (conn.backup -> backup_dir/lector_pre_remove_record_<time>.db),
        then delete that one record. Nothing else changes. {record_id, backup}."""
        with self._store() as st:
            try:
                return records.remove(st.conn, record_id, self.backup_dir)
            except KeyError as exc:
                raise _lector_error(str(exc).strip("'\"")) from None

    def export_records_csv(self, path, search_id=None, species=None, year=None):
        """Write the (filtered) records as CSV for scripts/import_contributed.py (which reads
        .xlsx: open the CSV in Excel and save it as a workbook). {path, rows}."""
        rows = self.list_records(search_id, species, year)
        if not rows:
            raise _lector_error("There are no records to export.")
        return records.export_csv(list(reversed(rows)), path)

    # --- BHL API key --------------------------------------------------------------------
    def test_api_key(self, key):
        """NETWORK, one request: does BHL accept this key? {ok, message}."""
        key = (key or "").strip()
        if not key:
            return {"ok": False, "message": "Paste the key into the box first."}
        try:
            self._key_client_factory(key).check_key()
        except BHLError as exc:
            return {"ok": False, "message": f"BHL did not accept the key: {exc}"}
        return {"ok": True, "message": "BHL accepted the key."}

    def save_api_key(self, key):
        """Write the key (one line) to data\\bhl_api_key.txt; the next BHL request uses it."""
        key = (key or "").strip()
        if not key or len(key.split()) != 1:
            raise _lector_error("The key is one word with no spaces: paste just the key.")
        config.KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        config.KEY_FILE.write_text(key + "\n", encoding="utf-8")
        self._client = None
        return str(config.KEY_FILE)

