"""Lector command line.

    python -m Lector fetch species.txt [--synonyms] [--from-year 1800 --to-year 1950]
    python -m Lector fetch species.csv --count-only     # see hit counts first
    python -m Lector probe "Lamia textor"               # dump raw BHL JSON
    python -m Lector status
    python -m Lector export --all          (or --name "Lamia textor")
    python -m Lector                       # no command: type species one at a time
"""
import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from . import config
from .bhl_client import BHLClient, BHLError
from .export import export_species
from .harvest import HarvestOptions, extract_pages, harvest_species
from .species_source import UksiLookup, read_input
from .store import LectorStore


def _utf8_console():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


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
        count_only=args.count_only, refresh=args.refresh)
    n_names = sum(len(e.query_names()) for e in entries)
    print(f"Lector: {len(entries)} species, {n_names} names to search"
          + ("  [count only]" if opts.count_only else ""))

    store = LectorStore()
    try:
        for entry in entries:
            harvest_species(client, store, entry, opts)
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
    store = LectorStore()
    rows = store.status_rows()
    store.close()
    if not rows:
        print("Nothing harvested yet.")
        return
    print(f"{'Species':38} {'TVK':17} {'Pages':>6} {'Text':>6}  Years")
    for r in rows:
        years = f"{r['first_year'] or '?'}-{r['last_year'] or '?'}"
        print(f"{r['accepted_name'][:38]:38} {r['tvk'] or '':17} "
              f"{r['pages']:>6} {r['fetched']:>6}  {years}")


def cmd_export(args):
    store = LectorStore()
    names = store.species_names() if args.all else [args.name]
    out_dir = Path(args.out) if args.out else config.EXPORT_DIR
    for name in names:
        path, n = export_species(store, name, out_dir)
        print(f"✓ {name}: {n} pages → {path}" if path else f"✗ {name}: nothing harvested")
    store.close()


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
    store = LectorStore()
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
            if entry.synonyms:
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
                   help="keep only titles containing any of these words")
    f.add_argument("--exclude-title", nargs="+", metavar="WORD",
                   help="drop titles containing any of these words")
    f.add_argument("--count-only", action="store_true", help="report hit counts, store nothing")
    f.add_argument("--refresh", action="store_true", help="re-search names already searched")
    f.add_argument("--key", help="BHL API key (otherwise env var or data/bhl_api_key.txt)")
    f.set_defaults(func=cmd_fetch)

    pr = sub.add_parser("probe", help="dump BHL's raw response for one name")
    pr.add_argument("name")
    pr.add_argument("--key")
    pr.set_defaults(func=cmd_probe)

    s = sub.add_parser("status", help="summary of what has been harvested")
    s.set_defaults(func=cmd_status)

    e = sub.add_parser("export", help="write readable text bundles per species")
    g = e.add_mutually_exclusive_group(required=True)
    g.add_argument("--name", help="accepted species name")
    g.add_argument("--all", action="store_true")
    e.add_argument("--out", help=f"output folder (default {config.EXPORT_DIR})")
    e.set_defaults(func=cmd_export)
    return p


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
