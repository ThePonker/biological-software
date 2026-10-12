"""Export a saved search: text bundle, Word dossier, Excel index, PDF (service.export).

Missing optional packages are reported in the messages, never as a crash:
python-docx (Word, needed for PDF too), openpyxl (Excel), docx2pdf or
LibreOffice (PDF).
"""
from datetime import date

from . import saved
from .export import _safe_filename, write_text_bundle
from .review import REVIEW_STATUSES, search_rows
from .store import now

FORMATS = ("txt", "docx", "xlsx", "pdf")
NEED_DOCX = "Word dossier not made: install python-docx once with  pip install python-docx"
NEED_XLSX = "Excel index not made: install openpyxl once with  pip install openpyxl"


def _has(mod):
    try:
        __import__(mod)
        return True
    except ImportError:
        return False


def export_search(store, sid, formats=("docx", "xlsx"), order="year", include_appendices=True,
                  include_statuses=("unreviewed", "relevant", "record_extracted"),
                  include_notes=True, out_dir=None):
    bad = set(formats) - set(FORMATS)
    if bad:
        raise ValueError(f"Unknown format(s) {sorted(bad)}; use {FORMATS}")
    bad = set(include_statuses) - set(REVIEW_STATUSES)
    if bad:
        raise ValueError(f"Unknown review status(es) {sorted(bad)}")
    conn = store.conn
    s = saved.get_search(conn, sid)
    rows, accepted = search_rows(conn, sid)
    keep = set(include_statuses)
    stem = _safe_filename(s["name"])
    files, messages, counts = {}, [], {"pages": len(rows)}
    if not rows:
        return {"files": files, "messages": ["Nothing to export: this search holds no pages yet."],
                "counts": counts}
    out_dir.mkdir(parents=True, exist_ok=True)

    if "txt" in formats:
        chosen = [r for r in rows if r["review_status"] in keep]
        path, n = write_text_bundle(s["name"], chosen, out_dir, stem)
        if path:
            files["txt"] = path
            files["csv"] = path.with_name(f"{stem}_index.csv")
            _log(conn, sid, "txt", path, n)

    wants_docx = "docx" in formats or "pdf" in formats
    if wants_docx and not _has("docx"):
        messages.append(NEED_DOCX)
    elif wants_docx:
        from .dossier import write_dossier
        last = saved.last_run(conn, sid, "fetch")
        about = [("Saved search", s["name"])]
        if last:
            about.append(("Run", f"{last['number']}, {(last['finished'] or last['started'])[:10]}"))
        about.append(("Included", ", ".join(x.replace("_", " ") for x in include_statuses)))
        want_xlsx = "xlsx" in formats
        if want_xlsx and not _has("openpyxl"):
            messages.append(NEED_XLSX)
            want_xlsx = False
        docx_path, xlsx_path, c = write_dossier(
            s["target_name"] if s["kind"] == "species" else s["name"], rows, out_dir, stem,
            order == "journal", include_appendices, include_notes, want_xlsx, accepted, about,
            keep=lambda r: r["review_status"] in keep)
        counts.update(entries=c[0], duplicates_merged=c[1], index_pages=c[2], name_not_in_text=c[3])
        if "docx" in formats or "pdf" in formats:
            files["docx"] = docx_path
            _log(conn, sid, "docx", docx_path, c[0])
        if xlsx_path:
            files["xlsx"] = xlsx_path
            _log(conn, sid, "xlsx", xlsx_path, c[0])
        if "pdf" in formats:
            from .pdf import to_pdf
            pdf_path, msg = to_pdf(docx_path)
            messages.append(msg)
            if pdf_path:
                files["pdf"] = pdf_path
                _log(conn, sid, "pdf", pdf_path, c[0])
    elif "xlsx" in formats:
        messages.append("The Excel index is made with the Word dossier, which needs python-docx.")
    conn.commit()
    return {"files": {k: str(v) for k, v in files.items()}, "messages": messages,
            "counts": counts, "date": date.today().isoformat()}


def _log(conn, sid, kind, path, pages):
    conn.execute("INSERT INTO exports (search_id, created, kind, path, pages) VALUES (?,?,?,?,?)",
                 (sid, now(), kind, str(path), pages))
