"""Natural England Species Status reviews: file them, extract spreadsheet accounts.

1. FILES every downloaded review into data\\reviews\\<folder>\\source\\ (copied,
   SHA-256 verified, then removed from Downloads -- as organise_reviews.py).
2. For reviews whose data table has an "Ecological account" column, WRITES
   extracted\\review.csv + accounts.csv (+ statuses.csv for reference):
     * citation from the report's own "should be cited as" text
     * account = "Distribution Overview" (where present) + "Ecological account",
       each checked verbatim against its cell
     * tracks_assessed = accounts  -> load_review.py writes accounts only;
       these statuses are already in Codex via JNCC
3. Lists the reviews whose accounts are only in the PDF (a later step).

DRY RUN by default: shows the filing plan, each citation and a sample account.
--apply to file and extract.

Run:  python scripts\\prepare_ne_reviews.py
      python scripts\\prepare_ne_reviews.py --apply
"""
import csv, hashlib, os, re, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(ROOT, "data", "reviews")
DL = os.path.join(os.path.expanduser("~"), "Downloads")
APPLY = "--apply" in sys.argv

# necr: (folder, taxon group, PDF filename pattern, table filename pattern, extract accounts?)
PLAN = {
    "134": ("coleoptera_soldier_beetles_necr134_2014", "Coleoptera: soldier beetles and allies", r"^NECR134 _edition_2\.pdf$", r"^NECR134 data table", True),
    "148": ("coleoptera_darkling_beetles_necr148_2014", "Coleoptera: darkling beetles and allies", r"^NECR148_edition_2\.pdf$", r"^NECR148 data table", True),
    "161": ("coleoptera_chrysomelidae_necr161_2014", "Coleoptera: leaf beetles (superseded by NECR702)", r"^NECR161_edition_1\.pdf$", r"^Copy of Data table 2nd version", False),
    "174": ("plecoptera_stoneflies_necr174_2015", "Plecoptera", r"^NECR174_edition_1\.pdf$", r"^NECR174 data table", True),
    "186": ("myriapoda_isopoda_necr186_2015", "Millipedes, centipedes and woodlice", None, r"^NECR186 data table", False),
    "187": ("orthoptera_necr187_2015", "Orthoptera and allied", r"^NECR187_edition_1\.pdf$", None, False),
    "188": ("hemiptera_aquatic_necr188_2015", "Hemiptera: aquatic and semi-aquatic bugs", r"^NECR188_edition_1\.pdf$", r"^NECR188 data table", True),
    "189": ("coleoptera_carabidae_necr189_2016", "Coleoptera: ground beetles", r"^NECR189_edition_1\.pdf$", r"^NECR189 data table", False),
    "190": ("hemiptera_shieldbugs_necr190_2016", "Hemiptera: shieldbugs and allies", None, r"^NECR190 data table", False),
    "191": ("trichoptera_necr191_2016", "Trichoptera", r"^NECR191_edition_1\.pdf$", None, False),
    "192": ("diptera_larger_brachycera_necr192_2017", "Diptera: larger Brachycera", r"^NECR192 Edition 1", None, False),
    "193": ("ephemeroptera_necr193_2016", "Ephemeroptera", r"^NECR193_edition_1\.pdf$", r"^NECR193 data table", True),
    "195": ("diptera_dolichopodidae_necr195_2018", "Diptera: Dolichopodidae", r"^NECR 195 edition 1", None, False),
    "217": ("diptera_acalyptratae_necr217_2016", "Diptera: Acalyptratae (provisional)", r"^NECR217 edition 1", None, False),
    "224": ("coleoptera_scarabaeoidea_necr224_2016", "Coleoptera: Scarabaeoidea", r"^NECR224 .*\.pdf$", r"^NECR224 .*\.xls$", True),
    "234": ("diptera_calyptratae_necr234_2017", "Diptera: Calyptratae (provisional)", r"^NECR234 Edition 1", None, False),
    "235": ("coleoptera_histeridae_necr235_2017", "Coleoptera: clown beetles and false clown beetles", r"^NECR235 Edition 1", r"^Edition 1 Histeridae Spreadsheet", True),
    "236": ("coleoptera_bostrichoidea_necr236_2017", "Coleoptera: wood-boring and spider beetles", r"^NECR236 Edition 1", r"^Bostrichoidea Derodontoidea Review", True),
    "246": ("diptera_lonchopteridae_necr246_2018", "Diptera: Lonchopteridae, Platypezidae, Opetiidae", r"^NECR246 Edition 1", None, False),
    "265": ("coleoptera_tachyporinae_necr265_2019", "Coleoptera: Staphylinidae Tachyporinae", r"^NECR265 .*\.pdf$", r"^NECR265 .*\.xls$", True),
    "272": ("coleoptera_cerambycidae_necr272_2019", "Coleoptera: longhorn beetles", r"^NECR272 .*\.pdf$", r"^NECR272 .*\.xlsx$", True),
}


# The 2014-16 reports' citation page is an image, not text, so these are
# supplied -- confirmed from publication records (Pantheon bibliography,
# Natural England's catalogue and citing papers), 4 October 2026.
KNOWN_CITATIONS = {
    "134": ("Alexander, K.N.A. 2014. A review of the beetles of Great Britain: The Soldier Beetles and their allies. "
            "Species Status No.16. Natural England Commissioned Reports, Number 134"),
    "148": ("Alexander, K.N.A., Dodd, S. & Denton, J.S. 2014. A review of the beetles of Great Britain: The Darkling "
            "Beetles and their allies. Species Status No.18. Natural England Commissioned Reports, Number 148"),
    "174": ("Macadam, C.R. 2015. A review of the stoneflies (Plecoptera) of Great Britain. Species Status No.20. "
            "Natural England Commissioned Reports, Number 174"),
    "188": ("Cook, A.A. 2015. A review of the Hemiptera of Great Britain: The Aquatic and Semi-aquatic Bugs "
            "(Dipsocoromorpha, Gerromorpha, Leptopodomorpha & Nepomorpha). Species Status No.24. "
            "Natural England Commissioned Reports, Number 188"),
    "193": ("Macadam, C.R. 2016. A review of the status of the mayflies (Ephemeroptera) of Great Britain. "
            "Species Status No.28. Natural England Commissioned Reports, Number 193"),
    "224": ("Lane, S.A. & Mann, D.J. 2016. A review of the status of the beetles of Great Britain: The stag beetles, "
            "dor beetles, dung beetles, chafers and their allies - Lucanidae, Geotrupidae, Trogidae and Scarabaeidae. "
            "Species Status No.31. Natural England Commissioned Reports, Number 224"),
}


def binomial(name):
    """Scientific name without authority: genus, optional (Subgenus), epithet(s)."""
    toks = name.replace("\u00a0", " ").split()
    if not toks:
        return ""
    out = [toks[0]]
    for t in toks[1:]:
        if len(out) == 1 and t.startswith("(") and t[1:2].isupper():   # (Subgenus)
            continue
        if t[:1].islower() and re.fullmatch(r"[a-z][a-z\-]*", t):
            out.append(t)
        else:
            break                                                   # authority starts
    return " ".join(out)


def tidy_author(a):
    """'LANE, S.A' -> 'Lane, S.A.'"""
    a = re.sub(r"\b([A-Z])([A-Z]{2,})\b", lambda m: m.group(1) + m.group(2).lower(), a)
    return a + "." if re.search(r"[A-Z]\.[A-Z]$", a) else a


def tidy_cite(c):
    c = re.sub(r"([a-z])(Natural England)", r"\1. \2", c)
    c = re.sub(r"(Number|No\.)(\d)", r"\1 \2", c)
    return re.sub(r"\s+", " ", c).strip()


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def find(pattern):
    """The single file in Downloads (or already filed) matching pattern."""
    if not pattern:
        return None
    hits = [os.path.join(DL, f) for f in os.listdir(DL) if re.search(pattern, f)]
    return hits


def clean(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return re.sub(r"[ \t]+", " ", str(v)).strip()


def read_table(p):
    """All sheets as lists of rows."""
    if p.lower().endswith(".xls"):
        import xlrd
        wb = xlrd.open_workbook(p)
        return [(s.name, [s.row_values(i) for i in range(s.nrows)]) for s in wb.sheets()]
    import openpyxl
    wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
    try:
        return [(ws.title, [list(r) for r in ws.iter_rows(values_only=True)]) for ws in wb.worksheets]
    finally:
        wb.close()          # read-only workbooks hold the file open on Windows until closed


def pick(hdr, *cands):
    low = [h.lower() for h in hdr]
    for c in cands:
        for i, h in enumerate(low):
            if h.startswith(c):
                return i
    return None


def extract(table):
    """[(name, tvk, iucn, rarity_raw, account, sheet, row)], problems"""
    out, problems = [], []
    for sname, rows in read_table(table):
        hi = next((i for i, r in enumerate(rows[:6])
                   if any(clean(v).lower().startswith("ecological account") for v in r)), None)
        if hi is None:
            continue
        hdr = [clean(h) for h in rows[hi]]
        first = hi + 1
        if hi + 1 < len(rows) and any(clean(v).lower().startswith("species name") for v in rows[hi + 1]):
            nxt = list(rows[hi + 1]) + [None] * (len(hdr) - len(rows[hi + 1]))
            hdr = [clean(f"{a} {clean(b)}") for a, b in zip(hdr, nxt)]     # e.g. "NBN Taxon No."
            first = hi + 2
        cn = pick(hdr, "species name", "species (scientific")
        ct = pick(hdr, "recommended tvk", "nbn taxon no", "tvk")
        ci = pick(hdr, "gb iucn status", "proposed gb iucn status")
        cr = pick(hdr, "gb rarity status", "suggested jncc status")
        cd = pick(hdr, "distribution overview")
        ce = pick(hdr, "ecological account")
        if cn is None or ce is None:
            problems.append(f"{sname}: species or account column not found");  continue
        for k, r in enumerate(rows[first:], start=first + 1):
            r = list(r) + [None] * (len(hdr) - len(r))
            name = binomial(clean(r[cn]))
            if not name or len(name.split()) < 2:
                continue
            parts = [clean(r[c]) for c in (cd, ce) if c is not None and clean(r[c])]
            acc = "\n\n".join(parts)
            for c in (cd, ce):                      # verbatim check
                if c is not None and clean(r[c]) and clean(r[c]) not in acc:
                    problems.append(f"{sname} row {k}: account not verbatim")
            tvk = clean(r[ct]) if ct is not None else ""
            out.append((name, tvk if re.match(r"^[A-Z]{6}\d{10}$", tvk) else "",
                        clean(r[ci]) if ci is not None else "", clean(r[cr]) if cr is not None else "",
                        acc, sname, k))
    return out, problems


def citation(pdf):
    try:
        from pypdf import PdfReader
        text = "\n".join((pg.extract_text() or "") for pg in PdfReader(pdf).pages[:6])
    except Exception as e:
        return None, f"pdf unreadable: {e}"
    t = re.sub(r"\s+", " ", text)
    m = (re.search(r"(?:should be cited as|citation)[:\s]+(.{20,360}?Number\s*\d+)", t, re.I)
         or re.search(r"(?:should be cited as|citation)[:\s]+(.{20,320}?No\.\s*\d+)", t, re.I))
    if not m:
        return None, "no 'should be cited as' found"
    cite = tidy_cite(m.group(1))
    y = re.search(r"\b(19|20)\d{2}\b", cite)
    author = tidy_author(cite[:y.start()].strip(" ,(")) if y else ""
    after = cite[y.end():].strip(" .)") if y else cite
    title = re.split(r"\.\s+(?:Species Status|Natural England)", after)[0].strip(" .")
    return (cite, author, y.group(0) if y else "", title), None


print("Natural England Species Status reviews -- " + ("APPLY" if APPLY else "DRY RUN"))
print("=" * 90)
moves, writes, pdf_only, problems = [], [], [], []
for necr, (folder, group, ppat, tpat, do_acc) in PLAN.items():
    src_dir = os.path.join(R, folder, "source")
    files = []
    for pat in (ppat, tpat):
        if not pat:
            continue
        hits = find(pat)
        filed = [os.path.join(src_dir, f) for f in (os.listdir(src_dir) if os.path.isdir(src_dir) else [])
                 if re.search(pat, f)]
        if len(hits) == 1:
            files.append(hits[0]);  moves.append((hits[0], os.path.join(src_dir, os.path.basename(hits[0]))))
        elif len(hits) == 0 and len(filed) == 1:
            files.append(filed[0])
        else:
            problems.append(f"NECR{necr}: pattern {pat!r} matched {len(hits)} in Downloads, {len(filed)} filed")
    pdf = next((f for f in files if f.lower().endswith(".pdf")), None)
    table = next((f for f in files if not f.lower().endswith(".pdf")), None)
    line = f"NECR{necr:<4} {folder:<48}"
    if not do_acc:
        why = ("superseded" if necr == "161" else "accounts in PDF only" if pdf and not table or necr == "189"
               else "PDF needed for citation" if not pdf else "accounts in PDF only")
        print(f"  {line} file only  ({why})")
        if why == "accounts in PDF only":
            pdf_only.append(necr)
        continue
    rows, probs = extract(table) if table else ([], ["no table"])
    cit, err = citation(pdf) if pdf else (None, "no PDF")
    problems += [f"NECR{necr}: {p}" for p in probs]
    if err and necr in KNOWN_CITATIONS:
        kc = KNOWN_CITATIONS[necr]
        y = re.search(r"\b(19|20)\d{2}\b", kc)
        after = kc[y.end():].strip(" .")
        cit = (kc, kc[:y.start()].strip(" ,"), y.group(0),
               re.split(r"\.\s+(?:Species Status|Natural England)", after)[0].strip(" ."))
        print("           (citation page is an image -- using the confirmed citation)")
    elif err:
        print(f"           ! citation not found ({err}) -- falling back to the report number")
        cit = (f"Natural England Commissioned Report NECR{necr}", "", "", f"Natural England Commissioned Report NECR{necr}")
    n_acc = sum(1 for r in rows if r[4])
    print(f"  {line} {len(rows):>4} species  {n_acc:>4} accounts")
    if cit:
        print(f"           cited as: {cit[0]}")
    if rows:
        s = next((r for r in rows if r[4]), rows[0])
        print(f"           e.g. {s[0]}: {s[4][:110]!r}")
    writes.append((necr, folder, group, pdf, table, rows, cit))

if pdf_only:
    print(f"\n  Accounts only in the PDF (a later step): NECR{', NECR'.join(pdf_only)}")
for p in problems:
    print(f"  x {p}")
if problems:
    sys.exit("\nABORTED -- nothing filed or written.")
if not APPLY:
    print(f"\nDRY RUN -- {len(moves)} files to file, {len(writes)} reviews to extract. Re-run with --apply.")
    sys.exit(0)

locked = []
for src, dst in moves:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(os.path.dirname(dst)), "extracted"), exist_ok=True)
    if not os.path.exists(dst):
        shutil.copy2(src, dst)
    if sha(src) != sha(dst):
        sys.exit(f"  x {dst} does not verify against {src} -- stopped")
    try:
        os.remove(src)
    except OSError as e:     # the copy is verified; a locked original is not a reason to stop
        locked.append(os.path.basename(src))
print(f"\n  {len(moves)} files filed and verified")
for f in locked:
    print(f"  ! could not remove the original (in use): {f} -- its copy is verified; delete it by hand")

for necr, folder, group, pdf, table, rows, cit in writes:
    d = os.path.join(R, folder, "extracted")
    os.makedirs(d, exist_ok=True)
    cite, author, year, title = cit
    with open(os.path.join(d, "review.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["review_name", "author", "date_published", "citation", "licence", "source_file",
                    "species_count", "taxon_group", "tracks_assessed"])
        w.writerow([f"{title[:200]} (NECR{necr})", author, year, cite, "Open Government Licence v3.0",
                    os.path.basename(table), len(rows), group, "accounts"])
    with open(os.path.join(d, "accounts.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["species_name", "tvk", "account_text", "source_columns", "sheet_row"])
        for name, tvk, iucn, rar, acc, sname, k in rows:
            if acc:
                w.writerow([name, tvk, acc, "Distribution Overview; Ecological account", f"{sname}!{k}"])
    with open(os.path.join(d, "statuses.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["species_name", "tvk", "iucn_status", "rarity_raw", "sheet_row"])
        for name, tvk, iucn, rar, acc, sname, k in rows:
            w.writerow([name, tvk, iucn, rar, f"{sname}!{k}"])
    print(f"  NECR{necr}: extracted -> {os.path.relpath(d, ROOT)}")
print("\nNext: python scripts\\load_review.py data\\reviews\\<folder>   (dry run, then --apply)")
