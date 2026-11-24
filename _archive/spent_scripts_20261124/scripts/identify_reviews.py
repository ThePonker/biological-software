"""Identify downloaded review files from their own contents.  READ ONLY.

For each PDF / spreadsheet in Downloads (or a folder given as argument):
  PDF          NECR number, title, author/date lines from the first pages,
               page count, licence/copyright line, whether text extracts
  spreadsheet  sheets; for the main sheet: header row, species rows, and any
               long-text column (a sign the accounts are in the spreadsheet)

Run:  python scripts\\identify_reviews.py
      python scripts\\identify_reviews.py "C:\\some\\other\\folder"
"""
import os, re, sys

D = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.expanduser("~"), "Downloads")
files = sorted(f for f in os.listdir(D) if f.lower().endswith((".pdf", ".xls", ".xlsx")))
print(f"Review files in {D}  --  READ ONLY")
print("=" * 90)


def short(s, n):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[:n] + "..."


def pdf(p):
    try:
        from pypdf import PdfReader
    except ImportError:
        print("   (pypdf missing: pip install pypdf --break-system-packages)");  return
    try:
        rd = PdfReader(p)
        text = "\n".join((rd.pages[i].extract_text() or "") for i in range(min(4, len(rd.pages))))
    except Exception as e:
        print(f"   x unreadable: {e}");  return
    words = len(text.split())
    necr = re.search(r"NECR\s?(\d{3})", text)
    title = re.search(r"(A (?:review|Provisional Assessment)[^\n]{10,200}(?:\n[^\n]{3,120}){0,2})", text, re.I)
    year = re.search(r"\b(19[89]\d|20[0-2]\d)\b", text)
    lic = re.search(r"(Open Government Licence[^\n]{0,40}|Creative Commons[^\n]{0,30}|©[^\n]{0,60}|Copyright[^\n]{0,60})", text)
    print(f"   PDF  {len(rd.pages)} pages  {'NECR' + necr.group(1) if necr else 'no NECR no.'}  first year {year.group(1) if year else '?'}"
          f"  text: {'yes' if words > 150 else 'LITTLE -- possibly scanned'}")
    print(f"        title:   {short(title.group(1), 150) if title else short(text[:150], 150)}")
    print(f"        licence: {short(lic.group(1), 90) if lic else 'none found on first pages'}")


def sheet(p):
    try:
        if p.lower().endswith(".xls"):
            import xlrd
            wb = xlrd.open_workbook(p)
            sheets = [(s.name, [s.row_values(i) for i in range(s.nrows)]) for s in wb.sheets()]
        else:
            import openpyxl
            wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
            sheets = [(ws.title, [list(r) for r in ws.iter_rows(values_only=True)]) for ws in wb.worksheets]
    except ImportError as e:
        print(f"   (missing library: {e.name} -- pip install {e.name} --break-system-packages)");  return
    except Exception as e:
        print(f"   x unreadable: {e}");  return
    main = max(sheets, key=lambda s: len(s[1]))
    print(f"   SHEET  sheets: {[s for s, _ in sheets]}   main: {main[0]!r} ({len(main[1])} rows)")
    rows = main[1]
    hi = next((i for i, r in enumerate(rows[:30]) if sum(1 for v in r if isinstance(v, str) and v.strip()) >= 5), None)
    if hi is None:
        return
    hdr = [short(h, 28) for h in rows[hi]]
    data = [r for r in rows[hi + 1:] if any(str(v).strip() for v in r if v is not None)]
    longc = []
    for j, h in enumerate(hdr):
        vals = [str(r[j]) for r in data if j < len(r) and isinstance(r[j], str) and r[j].strip()]
        if vals and sum(map(len, vals)) / len(vals) > 120:
            longc.append(f"{h} (~{sum(map(len, vals)) // len(vals)} chars)")
    print(f"          header row {hi + 1}, {len(data)} data rows")
    print(f"          columns: {short(', '.join(h for h in hdr if h), 230)}")
    print(f"          long-text columns: {longc or 'none -- accounts probably only in the PDF'}")


for f in files:
    print(f"\n## {f}")
    p = os.path.join(D, f)
    (pdf if f.lower().endswith(".pdf") else sheet)(p)
print("\nREAD ONLY -- nothing has been changed.")
