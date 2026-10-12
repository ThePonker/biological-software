"""Lector command line.

    python -m Lector fetch species.txt [--synonyms] [--from-year 1800 --to-year 1950]
    python -m Lector fetch species.csv --count-only     # see hit counts first
    python -m Lector fetch species.txt --replace-search --include-title Annals
                        # a species with a saved search: use these names/filters instead
    python -m Lector probe "Lamia textor"               # dump raw BHL JSON
    python -m Lector status
    python -m Lector export --all          (or --name "Lamia textor")
    python -m Lector export --name "Lamia textor" --docx [--by-journal] [--pdf]
    python -m Lector forget --name "Lamia textor"   # then fetch again with new filters
    python -m Lector synonyms "Lamia textor"        # which older names would be searched
    python -m Lector gui                   # the desktop window
    python -m Lector                       # no command: type species one at a time
"""
import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from . import config, saved, upgrade
from .bhl_client import BHLClient, BHLError
from .export import export_species
from .harvest import HarvestOptions, extract_pages, harvest_species
from .species_source import UksiLookup, read_input
from .store import LectorStore, NeedsMigration


def _utf8_console():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def _checker():
    """Names of old fetches are checked as a new search's are (UKSI + synonym lists)."""
    return upgrade.name_checker(config.UKSI_DB, config.SYNONYM_FILE)


def open_store():
    """LectorStore; an older lector.db is updated only after you type YES."""
    try:
        return LectorStore()
    except NeedsMigration as exc:
        print(f"! {exc}\n  What the update would do (dry run, nothing changed yet):")
        print(upgrade.format_report(upgrade.dry_run(config.LECTOR_DB, _checker())))
        try:
            ok = input(f"\nType YES to update {config.LECTOR_DB.name} "
                       "(a backup copy is made first): ").strip() == "YES"
        except EOFError:
            ok = False
        if not ok:
            raise SystemExit("Nothing has been changed.")
        print(upgrade.format_report(upgrade.apply(config.LECTOR_DB, config.BACKUP_DIR,
                                                  _checker())))
        print("✓ lector.db updated.\n")
        return LectorStore()


def cmd_fetch(args):
    client = BHLClient(config.load_api_key(args.key))
    raw_values = read_input(args.input)
    uksi = UksiLookup()
    entries, seen = [], set()
    for raw in raw_values:
        try:
            entry = uksi.resolve(raw, with_synonyms=args.synonyms)
        except ValueError as exc:
            print(f"✗ {exc}")
            continue
        if entry.name in seen:
            continue                      # same species listed by name and TVK
        seen.add(entry.name)
        entries.append(entry)
    for w in uksi.warnings:
        print(f"! {w}")
    uksi.close()

    opts = HarvestOptions(
        from_year=args.from_year, to_year=args.to_year, max_pages=args.max_pages,
        include_titles=args.include_title or [], exclude_titles=args.exclude_title or [],
        count_only=args.count_only, refresh=args.refresh, skip_index=args.skip_index)
    n_names = sum(len(e.query_names()) for e in entries)
    held = sum(len(e.held_back) for e in entries)
    print(f"Lector: {len(entries)} species, {n_names} names to search"
          + ("  [count only]" if opts.count_only else "")
          + (f"  ({held} synonyms held back - see `python -m Lector synonyms`)" if held else ""))

    store = open_store()
    try:
        for entry in entries:
            harvest_species(client, store, entry, opts, replace=args.replace_search)
    except KeyboardInterrupt:
        print("\n! Interrupted - progress so far is saved; re-run to resume.")
    finally:
        store.close()
    print(f"\nDone. {client.request_count} requests. Database: {config.LECTOR_DB}")


def cmd_probe(args):
    client = BHLClient(config.load_api_key(args.key))
    try:
        data = client.raw("GetNameMetadata", name=args.name)
    except BHLError as exc:
        raise SystemExit(f"✗ {exc}")
    config.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = config.EXPORT_DIR / f"probe_{args.name.replace(' ', '_')}.json"
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    pages = extract_pages(data.get("Result") or [])
    print(f"Status: {data.get('Status')}  {data.get('ErrorMessage') or ''}")
    print(f"Pages parsed: {len(pages)}")
    for p in pages[:10]:
        print(f"  {p['year'] or '????'}  {(p['title'] or '')[:55]:55}  "
              f"{p['volume'] or ''}  {p['page_label'] or ''}  [{p['page_id']}]")
    if len(pages) > 10:
        print(f"  … and {len(pages) - 10} more")
    print(f"Raw JSON written to: {out}")


def cmd_status(args):
    store = open_store()
    rows = store.status_rows()
    store.close()
    if not rows:
        print("Nothing harvested yet.")
        return
    print("Every page ever found per species, withdrawn ones too (the window shows each saved"
          " search's own pages).")
    print(f"{'Species':38} {'TVK':17} {'Pages':>6} {'Text':>6}  Years")
    for r in rows:
        years = f"{r['first_year'] or '?'}-{r['last_year'] or '?'}"
        print(f"{r['accepted_name'][:38]:38} {r['tvk'] or '':17} "
              f"{r['pages']:>6} {r['fetched']:>6}  {years}")


def cmd_export(args):
    store = open_store()
    names = store.species_names() if args.all else [args.name]
    out_dir = Path(args.out) if args.out else config.EXPORT_DIR
    for name in names:
        if args.docx or args.pdf:
            _export_docx(store, name, out_dir, args.by_journal, args.pdf)
            continue
        path, n = export_species(store, name, out_dir)
        print(f"✓ {name}: {n} pages → {path}" if path else f"✗ {name}: nothing harvested")
    store.close()


def _export_docx(store, name, out_dir, by_journal, pdf=False):
    from .dossier import export_dossier          # needs python-docx
    docx_path, xlsx_path, counts = export_dossier(store, name, out_dir, by_journal)
    if not docx_path:
        print(f"✗ {name}: nothing harvested")
        return
    entries, merged, index, no_match = counts
    print(f"✓ {name}: {entries} entries ({merged} duplicate scans merged), "
          f"{index} index pages, {no_match} without the name in the text")
    print(f"  Word:  {docx_path}")
    print(f"  Excel: {xlsx_path}" if xlsx_path
          else "  Excel index skipped - install openpyxl:  pip install openpyxl")
    if pdf:
        from .pdf import to_pdf
        pdf_path, msg = to_pdf(docx_path)
        print(f"  PDF:   {pdf_path}" if pdf_path else f"  {msg}")


def cmd_forget(args):
    store = open_store()
    reviewed = store.reviewed_count(args.name)
    if reviewed and not args.yes:
        store.close()
        raise SystemExit(f"✗ {args.name}: {reviewed} pages have a review status or notes, which "
                         "forget would lose. Nothing has been changed.\n  Runs now re-apply "
                         "changed filters by themselves, so forget is rarely needed; add --yes "
                         "to go ahead anyway.")
    n = store.forget_species(args.name)
    store.close()
    print(f"✓ {args.name}: {n} page links removed. Page text is kept, so fetching "
          "again only re-runs the searches." if n else f"✗ {args.name}: nothing stored")


def cmd_synonyms(args):
    """Show which names a species' search would use, and change your list."""
    from .synonyms import SynonymRules, candidate_names
    uksi = UksiLookup()
    try:
        entry = uksi.resolve(_tidy_name(args.name))
    except ValueError as exc:
        raise SystemExit(f"✗ {exc}")
    if not entry.tvk:
        uksi.close()
        raise SystemExit(f"✗ {args.name} is not in UKSI - check the spelling.")
    rules = SynonymRules.load()
    for change, sign in ((args.add, "+"), (args.exclude, "-")):
        for name in change or []:
            line = rules.remember(sign, name, None if args.all_species else entry.name, args.reason or "")
            print(f"✓ added to {rules.user_file.name}: {line}")
    print(f"{entry.name}  [{entry.tvk}]")
    for c in candidate_names(uksi, entry.name, entry.tvk, rules):
        mark = "✓" if c["included"] else "✗"
        print(f"  {mark} {c['name']:32} {c['origin'].replace('_', ' ')} - {c['source']}")
        if c["held_back_reason"]:
            print(f"      {c['held_back_reason']}")
    for w in rules.warnings:
        print(f"! {w}")
    print(f"\nYour list: {rules.user_file}"
          + ("" if rules.user_file.exists() else " (not made yet; --add / --exclude make it)"))
    uksi.close()


def _tidy_name(raw):
    """'lamia  TEXTOR' -> 'Lamia textor' (TVKs are left alone)."""
    parts = raw.split()
    if len(parts) == 1 and len(raw) == 16 and raw[:6].isalpha():
        return raw.upper()
    return " ".join([parts[0].capitalize()] + [p.lower() for p in parts[1:]])


def _ask_yes(prompt, default=True):
    ans = input(prompt).strip().lower()
    return default if not ans else ans.startswith("y")


def _open_file(path):
    try:
        os.startfile(path)                     # Windows: opens in the default app
    except (AttributeError, OSError):
        print(f"  (open it from: {path})")


def cmd_interactive(args):
    """Type a species, Lector searches BHL, fetches the text and opens the file."""
    print("Lector - search the Biodiversity Heritage Library")
    print("Type a species name (or TVK). Older names are searched too, if you say so.\n")
    client = BHLClient(config.load_api_key())
    uksi = UksiLookup()
    store = open_store()
    shown = 0
    try:
        while True:
            try:
                raw = input("Species (or Enter to finish): ").strip()
            except EOFError:
                break
            if not raw:
                break
            raw = _tidy_name(raw)
            synonyms = _ask_yes("Also search its older names (synonyms)? [Y/n]: ")
            try:
                entry = uksi.resolve(raw, with_synonyms=synonyms)
            except ValueError as exc:
                print(f"✗ {exc}\n")
                continue
            for w in uksi.warnings[shown:]:
                print(f"! {w}")
            shown = len(uksi.warnings)
            if not entry.tvk and not _ask_yes(
                    f"  {raw} is not in UKSI - check the spelling. Search BHL as typed anyway? [y/N]: ",
                    default=False):
                print()
                continue
            plain = lambda n: " ".join(w for w in n.split() if not w.startswith("("))
            entry.synonyms = [n for n in entry.synonyms if plain(n) != entry.name]  # subgenus only
            # a species with a saved search: its own names and filters are used (printed)
            if entry.synonyms and saved.find_search(store.conn, entry.name) is None:
                print("  Names to search: " + ", ".join([entry.name] + entry.synonyms))
            try:
                harvest_species(client, store, entry, HarvestOptions())
            except KeyboardInterrupt:
                print("\n! Stopped - what was fetched is saved; search again to carry on.")
            path, n = export_species(store, entry.name, config.EXPORT_DIR)
            if path:
                print(f"\n✓ {n} pages -> {path}")
                _open_file(path)
            else:
                print(f"\n✗ Nothing found on BHL for {entry.name}.")
            print()
    finally:
        store.close()
        uksi.close()
    print(f"Done. {client.request_count} requests.")


def build_parser():
    p = argparse.ArgumentParser(prog="python -m Lector",
                                description="Harvest species pages from the Biodiversity Heritage Library.")
    sub = p.add_subparsers(dest="command", required=True)

    f = sub.add_parser("fetch", help="search BHL for each species and fetch page text")
    f.add_argument("input", help=".txt (one name/TVK per line) or .csv (tvk / species column)")
    f.add_argument("--synonyms", action="store_true", help="also search UKSI synonyms")
    f.add_argument("--from-year", type=int)
    f.add_argument("--to-year", type=int)
    f.add_argument("--max-pages", type=int, default=config.DEFAULT_MAX_PAGES,
                   help=f"cap per searched name (default {config.DEFAULT_MAX_PAGES}; 0 = no cap)")
    f.add_argument("--include-title", nargs="+", metavar="WORD",
                   help="keep only titles containing any of these whole words")
    f.add_argument("--exclude-title", nargs="+", metavar="WORD",
                   help="drop titles containing any of these whole words")
    f.add_argument("--count-only", action="store_true", help="report hit counts, store nothing")
    f.add_argument("--refresh", action="store_true",
                   help="ask BHL again for names already searched (finds new scans); without it"
                        " the last answer is re-used and only the filters are applied again")
    f.add_argument("--skip-index", action="store_true",
                   help="leave out pages BHL types as index or contents")
    f.add_argument("--replace-search", action="store_true",
                   help="a species that already has a saved search: replace its names and "
                        "filters with this command's (without it the saved search's own are "
                        "used, so ticks made in the window are kept)")
    f.add_argument("--key", help="BHL API key (otherwise env var or data/bhl_api_key.txt)")
    f.set_defaults(func=cmd_fetch)

    pr = sub.add_parser("probe", help="dump BHL's raw response for one name")
    pr.add_argument("name")
    pr.add_argument("--key")
    pr.set_defaults(func=cmd_probe)

    s = sub.add_parser("status", help="summary of what has been harvested")
    s.set_defaults(func=cmd_status)

    e = sub.add_parser("export", help="write readable text bundles per species: every page "
                                      "ever found, withdrawn too, as <Species>_all_pages.txt")
    g = e.add_mutually_exclusive_group(required=True)
    g.add_argument("--name", help="accepted species name")
    g.add_argument("--all", action="store_true")
    e.add_argument("--out", help=f"output folder (default {config.EXPORT_DIR})")
    e.add_argument("--docx", action="store_true",
                   help="Word dossier + Excel index instead of text (needs python-docx)")
    e.add_argument("--by-journal", action="store_true",
                   help="with --docx: order entries by journal, then year")
    e.add_argument("--pdf", action="store_true",
                   help="Word dossier and a PDF copy (needs Word + docx2pdf, or LibreOffice)")
    e.set_defaults(func=cmd_export)

    fg = sub.add_parser("forget", help="remove a species' searches so it can be re-fetched"
                                       " with new filters (page text is kept)")
    fg.add_argument("--name", required=True, help="accepted species name")
    fg.add_argument("--yes", action="store_true", help="go ahead even if pages have been reviewed")
    fg.set_defaults(func=cmd_forget)

    sy = sub.add_parser("synonyms", help="show the names a species' search would use;"
                                         " --add / --exclude change your list")
    sy.add_argument("name", help="species name or TVK")
    sy.add_argument("--add", nargs="+", metavar="NAME", help="also search these names")
    sy.add_argument("--exclude", nargs="+", metavar="NAME", help="never search these names")
    sy.add_argument("--all-species", action="store_true",
                    help="with --exclude: for every species, not just this one")
    sy.add_argument("--reason", help="your reason, kept in the list")
    sy.set_defaults(func=cmd_synonyms)

    gu = sub.add_parser("gui", help="open the Lector window (saved searches, reading list)")
    gu.set_defaults(func=cmd_gui)
    return p


def cmd_gui(_args):
    """The desktop window (Lector/ui); launchers\\run_lector_gui.bat, Atrium's tile."""
    from .ui.app import main as gui_main
    raise SystemExit(gui_main())


def main(argv=None):
    _utf8_console()
    parser = build_parser()
    if not (sys.argv[1:] if argv is None else argv):
        try:
            cmd_interactive(None)          # no command: type species one at a time
        except KeyboardInterrupt:
            print("\nDone.")
        return
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except sqlite3.Error as exc:
        raise SystemExit(f"✗ Database error: {exc}\n  ({config.LECTOR_DB} - is it open "
                         "elsewhere or still syncing in OneDrive?)")


if __name__ == "__main__":
    main()
