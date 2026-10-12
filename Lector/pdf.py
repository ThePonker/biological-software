"""Word dossier -> PDF (LEC1). Optional: uses whatever converter is installed.

Order tried:
  1. Microsoft Word, through the docx2pdf package (Windows; pip install docx2pdf);
  2. LibreOffice (soffice) on the PATH or in its usual Windows folder.
If neither is there, nothing is written and the message says what to install.
The Word file is always written first; the PDF is a copy of it.
"""
import os
import shutil
import subprocess
from pathlib import Path

WINDOWS_SOFFICE = [Path(os.environ.get(v, "")) / "LibreOffice" / "program" / "soffice.exe"
                   for v in ("ProgramFiles", "ProgramFiles(x86)")]
NOT_AVAILABLE = ("PDF not made: it needs Microsoft Word with the docx2pdf package "
                 "(pip install docx2pdf) or LibreOffice. The Word file is ready; "
                 "you can also save it as PDF from Word.")


def _docx2pdf():
    try:
        from docx2pdf import convert
    except ImportError:
        return None
    return convert


def _soffice():
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    for p in WINDOWS_SOFFICE:
        if str(p) and p.exists():
            return str(p)
    return None


def pdf_method():
    """'word' / 'libreoffice' / None - what to_pdf() would use."""
    if os.name == "nt" and _docx2pdf():
        return "word"
    if _soffice():
        return "libreoffice"
    return None


def to_pdf(docx_path, timeout=180):
    """Convert a .docx beside itself. Returns (pdf_path or None, message)."""
    docx_path = Path(docx_path)
    pdf_path = docx_path.with_suffix(".pdf")
    method = pdf_method()
    if method == "word":
        try:
            _docx2pdf()(str(docx_path), str(pdf_path))
        except Exception as exc:                    # Word not installed / COM error
            if not _soffice():
                return None, f"PDF not made: Word could not convert it ({exc})."
            method = "libreoffice"
        else:
            if pdf_path.exists():
                return pdf_path, "PDF made with Microsoft Word."
    if method == "libreoffice":
        try:
            subprocess.run([_soffice(), "--headless", "--convert-to", "pdf", "--outdir",
                            str(docx_path.parent), str(docx_path)],
                           check=True, capture_output=True, timeout=timeout)
        except (OSError, subprocess.SubprocessError) as exc:
            return None, f"PDF not made: LibreOffice could not convert it ({exc})."
        if pdf_path.exists():
            return pdf_path, "PDF made with LibreOffice."
        return None, "PDF not made: LibreOffice gave no file."
    return None, NOT_AVAILABLE
