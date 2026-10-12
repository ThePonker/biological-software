"""Lector fix 1: year from volume string; de-duplicate repeat scans.

Run from the Biological Software root:  python fix1_lector_years_dupes.py
Backs up Lector/harvest.py to harvest.py.bak_fix1. Safe to re-run.
"""
import shutil
import sys
from pathlib import Path

TARGET = Path("Lector") / "harvest.py"

EDITS = [
    (
        "year: page, item, item volume string, then title date",
        '''        "year": parse_year(page.get("Year"), item.get("Year"), item.get("Date"),
                           title.get("PublicationDate")),''',
        '''        "year": parse_year(page.get("Year"), item.get("Year"), item.get("Date"),
                           item.get("Volume"), title.get("PublicationDate")),''',
    ),
    (
        "dedupe helper",
        '''def apply_filters(pages, opts):''',
        '''def _norm(text):
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def drop_duplicate_scans(pages):
    """Keep one copy where several libraries scanned the same page.

    Pages count as duplicates when normalised title, volume and printed page
    number all match. Pages without a printed page number are always kept.
    """
    seen, kept = set(), []
    for p in pages:
        if p["page_label"]:
            key = (_norm(p["title"]), _norm(p["volume"]), _norm(p["page_label"]))
            if key in seen:
                continue
            seen.add(key)
        kept.append(p)
    return kept


def apply_filters(pages, opts):''',
    ),
    (
        "apply dedupe after filtering",
        '''    kept.sort(key=lambda p: (p["year"] is None, p["year"] or 0, p["page_id"]))
    return kept[:opts.max_pages] if opts.max_pages else kept''',
        '''    kept.sort(key=lambda p: (p["year"] is None, p["year"] or 0, p["page_id"]))
    kept = drop_duplicate_scans(kept)
    return kept[:opts.max_pages] if opts.max_pages else kept''',
    ),
]


def main():
    if not TARGET.exists():
        sys.exit(f"✗ {TARGET} not found - run this from the Biological Software root.")
    text = TARGET.read_text(encoding="utf-8")
    new = text
    to_apply = []
    for name, old, repl in EDITS:
        if repl in new:
            print(f"✓ {name} (already applied)")
        elif new.count(old) == 1:
            to_apply.append((name, old, repl))
        else:
            sys.exit(f"✗ {name}: anchor found {new.count(old)} times - nothing written.")
    if not to_apply:
        print("Nothing to do.")
        return
    shutil.copy2(TARGET, TARGET.with_name("harvest.py.bak_fix1"))
    for name, old, repl in to_apply:
        new = new.replace(old, repl)
        print(f"✓ {name}")
    TARGET.write_text(new, encoding="utf-8", newline="\n")
    compile(new, str(TARGET), "exec")
    import importlib
    sys.path.insert(0, str(Path.cwd()))
    importlib.import_module("Lector.harvest")
    print("✓ compiles and imports")


if __name__ == "__main__":
    main()
