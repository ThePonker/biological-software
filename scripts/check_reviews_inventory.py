"""What is in each review file, and what does Codex already carry?  READ ONLY.

For every file in data/reviews:
  .xlsx  sheets; for each, the header row (first row with 3+ text cells), the
         columns, data-row count, two sample rows, and any column that looks
         like account text (long strings)
  .csv   header, row count, two sample rows
  .pdf   page count; whether text extracts; how often "status", "distribution",
         "habitat", "ecology" appear (a rough sign of species accounts)
Then Codex: designations whose source mentions sawfly / Symphyta, butterfly /
Lepidoptera, macro-moth, leaf beetle -- to show what JNCC already includes.

Run:  python scripts\\check_reviews_inventory.py | Out-File -FilePath reviews_inventory.txt -Encoding utf8
"""
import csv, os, re, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths

D = os.path.join(ROOT, "data", "reviews")
print("Review inventory  --  READ ONLY")
print("=" * 78)


def short(v, n=60):
    s = str(v).replace("\n", " ").strip()
    return s if len(s) <= n else s[:n] + "..."


def xlsx(p):
    try:
        import openpyxl
    except ImportError:
        print("  (openpyxl not installed)")
        return
    wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        hdr_i = next((i for i, r in enumerate(rows[:30])
                      if sum(1 for v in r if isinstance(v, str) and v.strip()) >= 3), None)
        print(f"  sheet {ws.title!r}: {len(rows)} rows")
        if hdr_i is None:
            continue
        hdr = [short(v, 40) if v is not None else "" for v in rows[hdr_i]]
        data = [r for r in rows[hdr_i + 1:] if any(v not in (None, "") for v in r)]
        print(f"    header at row {hdr_i + 1}; {len(data)} data rows")
        print(f"    columns: {[h for h in hdr if h]}")
        long_cols = []
        for j, h in enumerate(hdr):
            vals = [r[j] for r in data if j < len(r) and isinstance(r[j], str)]
            if vals and sum(len(v) for v in vals) / len(vals) > 80:
                long_cols.append(f"{h or j} (avg {int(sum(len(v) for v in vals) / len(vals))} chars)")
        print(f"    long-text columns (possible accounts): {long_cols or 'none'}")
        for r in data[:2]:
            print("    e.g. " + " | ".join(short(v, 30) for v in r if v not in (None, ""))[:220])


def csvf(p):
    with open(p, encoding="utf-8-sig", errors="replace") as f:
        rows = list(csv.reader(f))
    print(f"  {len(rows)} rows" + (f"; header {rows[0]}" if rows else " (empty)"))
    for r in rows[1:3]:
        print("    e.g. " + " | ".join(short(v, 30) for v in r)[:220])


def pdf(p):
    txt = None
    for mod in ("pypdf", "PyPDF2"):
        try:
            m = __import__(mod)
            rd = m.PdfReader(p)
            n = len(rd.pages)
            txt = "\n".join((pg.extract_text() or "") for pg in rd.pages)
            break
        except ImportError:
            continue
        except Exception as e:
            print(f"  ({mod} failed: {e})")
            return
    if txt is None:
        print("  (no PDF library -- pip install pypdf --break-system-packages)")
        return
    words = len(txt.split())
    print(f"  {n} pages; {words:,} words of extractable text"
          + ("  <- little text: may be scanned" if words < 200 * n * 0.2 else ""))
    for w in ("status", "distribution", "habitat", "ecology", "threat", "criteria"):
        print(f"    '{w}': {len(re.findall(w, txt, re.I))}", end="")
    print()
    m = re.search(r"(Open Government Licence[^\n]{0,40}|Creative Commons[^\n]{0,40}|ISBN[^\n]{0,30})", txt)
    if m:
        print(f"    licence/ISBN line: {short(m.group(0), 80)}")


for f in sorted(os.listdir(D)):
    p = os.path.join(D, f)
    if not os.path.isfile(p):
        continue
    print(f"\n### {f}  ({os.path.getsize(p) // 1024} KB)")
    ext = f.lower().rsplit(".", 1)[-1]
    try:
        {"xlsx": xlsx, "csv": csvf, "pdf": pdf}.get(ext, lambda _: print("  (skipped)"))(p)
    except Exception as e:
        print(f"  x could not read: {type(e).__name__}: {e}")

print("\n" + "=" * 78)
print("What Codex already carries (designations, by source)")
c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
for label, pat in (("sawflies", "%awfl%"), ("Symphyta", "%ymphyta%"), ("butterflies", "%utterfl%"),
                   ("macro-moths", "%acro%moth%"), ("moths (any)", "%moth%"),
                   ("leaf beetles", "%eaf%beetle%"), ("Fox", "%Fox%"), ("Musgrove", "%usgrove%")):
    rows = c.execute("""SELECT source, COUNT(1), MIN(date_designated), MAX(date_designated)
                        FROM designations WHERE source LIKE ? OR source_description LIKE ?
                        GROUP BY source ORDER BY 2 DESC LIMIT 6""", (pat, pat)).fetchall()
    print(f"\n  {label}:")
    for s, n, d0, d1 in rows:
        print(f"    {n:>5}  {short(s, 70)}  [{d0} .. {d1}]")
    if not rows:
        print("    none")
print("\n  Codex reviews table:", c.execute("SELECT id, review_name, licence FROM reviews").fetchall())
print("\nREAD ONLY -- nothing has been changed.")
