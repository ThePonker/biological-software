"""batch_maps.py -- many distribution maps with the same settings in one go (R9-7, 11 Oct 2026).
READ ONLY on the databases: writes PNG pages, an index.csv and settings.txt to an output folder.

    py -3.14 scripts\\batch_maps.py --group Cerambycidae --vc 23 --res hectad
    py -3.14 scripts\\batch_maps.py --group Cerambycidae --sources all --out D:\\Maps\\Longhorns
    py -3.14 scripts\\batch_maps.py --tvk NHMSYS0020109270 --tvk NBNSYS0000011045 --vc 23 --vc 24 --per-vc
    py -3.14 scripts\\batch_maps.py --vc 23                      (every species recorded in VC23)
    py -3.14 scripts\\batch_maps.py --tvk NHMSYS0020109270 --timeclasses --frames decade
    py -3.14 scripts\\batch_maps.py --group Cerambycidae --list   (just list the taxa, no maps)

Taxa: --tvk (repeat, or a comma list), or --group NAME (every species with records under that
family; --rank genus / order / group for others), or neither (every species with records for
the settings). Settings are the Mapping tab's: --sources (personal, commercial, collection,
scheme, contributed or all; repeat or comma list), --from / --to (ISO dates or years),
--vc (repeat), --per-vc, --res hectad|tetrad|monad, --no-tetrad-refs, --include-embargoed,
--style presence|density|date. Figures are the Mapping tab's for the same settings.

Output: --out FOLDER, default Documents\\Observatum batch maps\\<date_time>_<label>\\.
--timeclasses [1970,2000,2020] adds a date-class map (by --by first|last record); --frames
decade|year adds cumulative frames (and a GIF when Pillow is installed; --no-gif to skip).
"""
import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, "Observatum")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

READ_ONLY = "READ ONLY. Nothing in the databases has been changed."


def _many(values):
    out = []
    for v in values or ():
        out += [x.strip() for x in str(v).split(",") if x.strip()]
    return out


def _date(text, end=False):
    """'2000' -> 2000-01-01 (or -12-31 for --to); ISO passes through."""
    if not text:
        return None
    from shared.import_core import date_bounds
    b = date_bounds(text)
    if not b:
        raise SystemExit(f"Could not read the date '{text}' (use 2000, 06/2000 or 2000-06-01)")
    return b[1] if end else b[0]


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Batch distribution maps (read only).")
    ap.add_argument("--tvk", action="append", help="taxon TVK (repeat or comma list)")
    ap.add_argument("--group", default="", help="every species with records under this taxon")
    ap.add_argument("--rank", default="family", help="rank of --group: family, genus, order, group")
    ap.add_argument("--sources", action="append", help="data sources (default personal)")
    ap.add_argument("--from", dest="date_from", default="")
    ap.add_argument("--to", dest="date_to", default="")
    ap.add_argument("--vc", action="append", help="vice-county number (repeat); none = GB")
    ap.add_argument("--per-vc", action="store_true", help="one map per VC, not one over all")
    ap.add_argument("--res", default="hectad", choices=["hectad", "tetrad", "monad", "1km"])
    ap.add_argument("--no-tetrad-refs", action="store_true",
                    help="leave off 2 km tetrad grid refs (the tab's box unticked)")
    ap.add_argument("--include-embargoed", action="store_true")
    ap.add_argument("--recorder", default="")
    ap.add_argument("--site", default="")
    ap.add_argument("--project", default="")
    ap.add_argument("--style", default="presence", choices=["presence", "density", "date"])
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--out", default="", help="output folder (created)")
    ap.add_argument("--timeclasses", nargs="?", const="1970,2000,2020", default=None,
                    help="also a date-class map; optional class start years")
    ap.add_argument("--by", default="first", choices=["first", "last"])
    ap.add_argument("--frames", choices=["decade", "year"], default=None)
    ap.add_argument("--from-year", type=int, default=None, help="first frame (earlier lumped)")
    ap.add_argument("--no-gif", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="first N taxa only (a trial run)")
    ap.add_argument("--list", action="store_true", help="list the taxa and stop")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    a = parse_args(argv)
    from src.services import batch_maps as bm
    from src.services import batch_spread as spread

    settings = bm.BatchSettings(
        sources=tuple(_many(a.sources) or ["personal"]), date_from=_date(a.date_from),
        date_to=_date(a.date_to, end=True), vcs=tuple(int(v) for v in _many(a.vc)),
        per_vc=a.per_vc, grid=a.res, include_tetrads=not a.no_tetrad_refs,
        include_embargoed=a.include_embargoed, recorder=a.recorder, site=a.site,
        project=a.project, style=a.style, dpi=a.dpi)
    breaks = spread.parse_breaks(a.timeclasses) if a.timeclasses else None
    print("Settings:", bm.describe(settings))
    t0 = time.perf_counter()
    chips, problems = bm.resolve(_many(a.tvk), a.group, a.rank, settings)
    for p in problems:
        print("  !", p)
    if a.limit:
        chips = chips[:a.limit]
    print(f"{len(chips)} taxa ({time.perf_counter() - t0:.1f} s)")
    if a.list or not chips:
        for c in chips:
            print(f"  {c['scientific_name']}  {c.get('common_name') or ''}  {c.get('tvk') or ''}")
        print(READ_ONLY)
        return 0 if chips or not problems else 1

    label = a.group or (chips[0]["scientific_name"] if len(chips) == 1 else "taxa")
    out = a.out or bm.default_out_dir(f"{label}_{settings.grid_name}_{bm.area_label(settings.vcs)}")
    os.makedirs(out, exist_ok=True)
    from src.views.mapping.batch_render import BatchRenderer, pillow_available
    r = BatchRenderer(settings)
    if a.frames and not a.no_gif and not pillow_available():
        print("  (Pillow not installed: frames saved as PNGs, no GIF)")
    done = []
    for tm in bm.run(chips, settings):
        r.save_map(tm, out)
        extra = []
        if breaks:
            extra.append(r.save_date_classes(tm, out, breaks, a.by))
        if a.frames:
            extra += r.save_frames(tm, out, a.frames, a.from_year, gif=not a.no_gif)
        done.append(tm)
        print(f"  {tm.chip['scientific_name']:<40} {bm.area_label(tm.vcs):<10} "
              f"{tm.records:>7,} records {len(tm.squares):>5,} squares  "
              f"{os.path.basename(tm.file)}" + (f"  +{len(extra)} files" if extra else ""))
    n = bm.write_index(os.path.join(out, "index.csv"), done)
    with open(os.path.join(out, "settings.txt"), "w", encoding="utf-8") as f:
        f.write(bm.describe(settings) + "\n")
        f.write("Command: " + " ".join(sys.argv) + "\n")
    print(f"{n} maps, index.csv and settings.txt in {out} ({time.perf_counter() - t0:.0f} s)")
    print(READ_ONLY)
    return 0


if __name__ == "__main__":
    sys.exit(main())
