"""Batch maps (R9-7, 11 Oct 2026): many maps with the same settings in one go -- every
longhorn in VC23, a list of taxa across several VCs, a whole group atlas-style. Read-only;
no Qt here (the pages are drawn by views/mapping/batch_render.py).

The figures are the Mapping tab's, by construction: each taxon is ONE chip given to
map_selection.fetch (the tab's one query builder: sources, counting switches, embargo,
each record once), then the tab's tetrad rule (map_notes.hold_tetrads) and its squares
(map_square_service.squares_for). Nothing is counted a second way.

    settings = BatchSettings(sources=("scheme",), vcs=(23,), grid="hectad")
    taxa = species_in(settings, within=find_taxon("Cerambycidae", "family"))
    for tm in run(taxa, settings): ...        # one TaxonMap per taxon (per VC if per_vc)
"""
from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

from shared.maps.grid_squares import HECTAD, MONAD, TETRAD

from . import map_square_service as squares_svc
from .map_selection import MapFilters, MapResult, fetch, normalise_sources
from .map_taxa import RANKS, get_context, search_taxa

GRIDS = {"hectad": HECTAD, "tetrad": TETRAD, "monad": MONAD, "1km": MONAD}
GRID_NAMES = {HECTAD: "hectad", TETRAD: "tetrad", MONAD: "monad"}

INDEX_HEADER = ["taxon", "common_name", "tvk", "rank", "area", "records", "mapped_records",
                "squares", "first_year", "last_year", "undated_records", "embargoed_not_shown",
                "duplicates_shown_once", "tetrad_refs_left_off", "too_coarse", "not_on_gb_grid",
                "file"]


# ---------------------------------------------------------------- settings

@dataclass
class AreaFilters(MapFilters):
    """MapFilters with several vice-counties (OR'd, as the filter builder ORs VC chips)."""
    vcs: Tuple[int, ...] = ()

    def builder_keys(self) -> dict:
        out = super().builder_keys()
        nums = [int(v) for v in self.vcs] + ([int(self.vc)] if self.vc else [])
        if nums:
            out["vice_county"] = [str(n) for n in dict.fromkeys(nums)]
        return out


@dataclass
class BatchSettings:
    """One set of map settings, the Mapping panel's fields. vcs () = all GB."""
    sources: Tuple[str, ...] = ("personal",)       # map_selection.SOURCES keys
    date_from: Optional[str] = None                 # ISO, as MapFilters
    date_to: Optional[str] = None
    vcs: Tuple[int, ...] = ()
    per_vc: bool = False                            # one map per VC rather than one over all
    grid: str = "hectad"                            # hectad / tetrad / monad (1km)
    include_tetrads: bool = True                    # mapping/include_tetrad_refs (default on)
    include_embargoed: bool = False
    recorder: str = ""
    site: str = ""
    project: str = ""
    style: str = "presence"                         # square_style.STYLES key
    period: str = "default"                         # BAND_PRESETS key (the date style)
    colour: str = "#0072B2"                         # Presence colour: a lone chip's default
    dpi: int = 300

    @property
    def size(self) -> int:
        return GRIDS[self.grid.lower()]

    @property
    def grid_name(self) -> str:
        return GRID_NAMES[self.size]

    def areas(self) -> List[Tuple[int, ...]]:
        """The VC sets to map: [()] for GB, [(23, 24)] together, [(23,), (24,)] per VC."""
        if not self.vcs:
            return [()]
        return [(v,) for v in self.vcs] if self.per_vc else [tuple(self.vcs)]

    def filters(self, vcs: Sequence[int] = ()) -> AreaFilters:
        return AreaFilters(date_from=self.date_from, date_to=self.date_to, recorder=self.recorder,
                           site=self.site, project=self.project,
                           include_embargoed=self.include_embargoed, vcs=tuple(vcs))

    def source_keys(self) -> Tuple[str, ...]:
        return normalise_sources(list(self.sources))


def area_label(vcs: Sequence[int]) -> str:
    """'GB', 'VC23', 'VC23-24-33' (a file-name part)."""
    return "GB" if not vcs else "VC" + "-".join(str(int(v)) for v in vcs)


# ---------------------------------------------------------------- choosing the taxa

def taxon_chip(tvk: str, uksi_path=None, db_path=None) -> Optional[dict]:
    """The Mapping tab's chip for a UKSI TVK (old TVKs read as their current taxon)."""
    ctx = get_context(db_path, uksi_path)
    cur = ctx.current(tvk, None) or tvk
    i = ctx.idx.pos.get(cur)
    if i is None:
        return None
    idx = ctx.idx
    name = idx.label[i] or idx.sci[i]          # as the picker labels it (species_search._result)
    if name == idx.sci[i] and idx.rank[i] in ("Species aggregate", "Species sensu lato"):
        if not any(w in name for w in ("agg", "/", "group")):
            name += " agg." if idx.rank[i] == "Species aggregate" else " s.l."
    return {"kind": "taxon", "tvk": cur, "scientific_name": name,
            "common_name": idx.common[i] or "", "rank": idx.rank[i]}


def find_taxon(text: str, rank: str = "family", db_path=None, uksi_path=None) -> Optional[dict]:
    """A chip for a recorded taxon of that rank (picker search; an exact name wins), or a taxon
    group chip for rank 'group'. None when nothing recorded matches."""
    hits = search_taxa(text, rank=rank, limit=20, db_path=db_path, uksi_path=uksi_path)
    if not hits:
        return None
    want = (text or "").strip().lower()
    exact = [h for h in hits if (h.get("scientific_name") or "").lower() == want]
    h = (exact or hits)[0]
    if h["kind"] == "group":
        return {"kind": "group", "label": h["label"], "scientific_name": h["label"]}
    return {k: h[k] for k in ("kind", "tvk", "scientific_name", "common_name", "rank")}


def species_in(settings: BatchSettings, within: Optional[dict] = None, db_path=None,
               uksi_path=None) -> List[dict]:
    """Every species with records for these settings (sources, dates, VCs, embargo), under
    `within` (a chip; None = every record), as chips in taxonomic order. A record counts
    as its species (subspecies roll up, map_taxa.species_key); records named only above
    species, and names UKSI doesn't hold, give no map."""
    res = fetch([within] if within else [], list(settings.source_keys()),
                settings.filters(settings.vcs), db_path=db_path, uksi_path=uksi_path)
    keys = {r["species"] for r in res.records
            if r.get("species") and not str(r["species"]).startswith("name:")}
    chips = [c for c in (taxon_chip(k, uksi_path, db_path) for k in keys) if c]
    return taxonomic_order(chips, db_path, uksi_path)


def taxonomic_order(chips: Iterable[dict], db_path=None, uksi_path=None) -> List[dict]:
    """Order, family, then the checklist order within a family (shared/checklist_order),
    else by name."""
    from shared.checklist_order import reorder
    ctx = get_context(db_path, uksi_path)
    rows = []
    for c in chips:
        i = ctx.idx.pos.get(c.get("tvk") or "")
        fam = ctx.idx.family[i] if i is not None else ""
        order = ctx.idx.order[i] if i is not None else ""
        gen = ctx.idx.genus[i] if i is not None else ""
        rows.append({"order_name": order or "", "family": fam or "", "genus": gen or "",
                     "species_name": c.get("scientific_name") or "", "chip": c})
    rows.sort(key=lambda r: (r["order_name"], r["family"], r["species_name"].lower()))
    return [r["chip"] for r in reorder(rows)]


def resolve(tvks: Sequence[str] = (), group: str = "", rank: str = "family",
            settings: Optional[BatchSettings] = None, db_path=None, uksi_path=None
            ) -> Tuple[List[dict], List[str]]:
    """(chips, problems) for the CLI / screen: listed TVKs as given (order kept), or every
    species with records under a group / family / genus / order (`group` searched at `rank`),
    or -- neither -- every species with records for the settings (e.g. all of VC23)."""
    settings = settings or BatchSettings()
    problems: List[str] = []
    if tvks:
        chips = []
        for t in tvks:
            c = taxon_chip(t.strip(), uksi_path, db_path)
            if c:
                chips.append(c)
            else:
                problems.append(f"TVK not in UKSI: {t}")
        return chips, problems
    within = None
    if group:
        if rank not in RANKS:
            return [], [f"Unknown rank '{rank}' (use one of {', '.join(RANKS)})"]
        within = find_taxon(group, rank, db_path, uksi_path)
        if within is None:
            return [], [f"No recorded {rank} matches '{group}'"]
    return species_in(settings, within, db_path, uksi_path), problems


# ---------------------------------------------------------------- one taxon's map

@dataclass
class TaxonMap:
    """One taxon's map for one area: what the Mapping tab would show with these settings."""
    chip: dict
    vcs: Tuple[int, ...]
    size: int
    result: MapResult
    squares: Dict[str, dict]
    mapped: List[dict]            # the records squared (tetrad rule applied)
    coarse: int = 0
    unparsed: int = 0
    tetrads_held: int = 0
    file: str = ""                # set when its page is saved
    extra: dict = field(default_factory=dict)

    @property
    def records(self) -> int:
        """Records fetched -- the tab's header '· n records'."""
        return len(self.result.records)

    @property
    def mapped_records(self) -> int:
        return sum(s["count"] for s in self.squares.values())

    def years(self) -> Tuple[Optional[int], Optional[int], int]:
        """(first year, last year, undated records) over the mapped records."""
        ys = [r["year"] for r in self.mapped if r.get("square") and r.get("year") is not None]
        undated = sum(1 for r in self.mapped if r.get("square") and r.get("year") is None)
        return (min(ys) if ys else None, max(ys) if ys else None, undated)

    def index_row(self) -> list:
        first, last, undated = self.years()
        c = self.chip
        return [c.get("scientific_name") or c.get("label") or "", c.get("common_name") or "",
                c.get("tvk") or "", c.get("rank") or "", area_label(self.vcs), self.records,
                self.mapped_records, len(self.squares), first, last, undated,
                self.result.embargoed, self.result.merged, self.tetrads_held, self.coarse,
                self.unparsed, os.path.basename(self.file) if self.file else ""]


def map_taxon(chip: dict, settings: BatchSettings, vcs: Sequence[int] = (), db_path=None,
              uksi_path=None) -> TaxonMap:
    """The Mapping tab's _generate_map for one chip, without the screen."""
    from ..views.mapping.map_notes import hold_tetrads
    res = fetch([chip], list(settings.source_keys()), settings.filters(vcs), db_path=db_path,
                uksi_path=uksi_path)
    bands = squares_svc.BAND_PRESETS.get(settings.period, squares_svc.BAND_PRESETS["default"])
    mappable, held = hold_tetrads(res.records, settings.include_tetrads)
    squares, coarse, unparsed = squares_svc.squares_for(
        mappable, settings.size, lambda y: squares_svc.year_to_band(y, bands))
    return TaxonMap(chip=chip, vcs=tuple(vcs), size=settings.size, result=res, squares=squares,
                    mapped=mappable, coarse=coarse, unparsed=unparsed, tetrads_held=held)


def run(chips: Iterable[dict], settings: BatchSettings, db_path=None, uksi_path=None
        ) -> Iterator[TaxonMap]:
    """One TaxonMap per taxon per area, taxa in the order given."""
    for chip in chips:
        for vcs in settings.areas():
            yield map_taxon(chip, settings, vcs, db_path, uksi_path)


# ---------------------------------------------------------------- files

def file_name(chip: dict, settings: BatchSettings, vcs: Sequence[int] = (), suffix: str = "",
              ext: str = ".png") -> str:
    """'Rutpela_maculata_hectad_VC23.png' (+ '_dateclass', '_1980s' ...): the taxon, the grid,
    the area -- the same for every taxon of a batch, so the folder sorts by name."""
    from ..views.mapping.atlas_export import safe_filename
    name = safe_filename(chip.get("scientific_name") or chip.get("label") or "taxon")
    parts = [name, settings.grid_name, area_label(vcs)] + ([suffix] if suffix else [])
    return "_".join(parts) + ext


def documents_dir() -> str:
    """The user's Documents folder as Windows has it (OneDrive-redirected Documents too),
    else ~/Documents."""
    try:
        from PySide6.QtCore import QStandardPaths
        d = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        if d:
            return os.path.normpath(d)
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Documents")


def default_out_dir(label: str = "batch") -> str:
    """Documents\\Observatum batch maps\\<YYYYMMDD_HHMM>_<label> (created when written)."""
    from ..views.mapping.atlas_export import safe_filename
    docs = documents_dir()
    return os.path.join(docs, "Observatum batch maps",
                        f"{datetime.now():%Y%m%d_%H%M}_{safe_filename(label)}")


def write_index(path: str, maps: Iterable[TaxonMap]) -> int:
    """index.csv: one row per map (UTF-8 with BOM, opens cleanly in Excel)."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    n = 0
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(INDEX_HEADER)
        for tm in maps:
            w.writerow(["" if v is None else v for v in tm.index_row()])
            n += 1
    return n


def describe(settings: BatchSettings) -> str:
    """The settings in words (the CLI's header line and the index's settings.txt)."""
    from ..views.mapping.source_picker import sources_label
    bits = [sources_label(list(settings.source_keys())), f"{settings.grid_name}s",
            "GB" if not settings.vcs else ("each of " if settings.per_vc and len(settings.vcs) > 1
                                           else "") + area_label(settings.vcs)]
    if settings.date_from or settings.date_to:
        bits.append(f"dates {settings.date_from or '…'} to {settings.date_to or '…'}")
    if settings.recorder:
        bits.append(f"recorder contains '{settings.recorder}'")
    if settings.site:
        bits.append(f"site contains '{settings.site}'")
    if settings.project:
        bits.append(f"project '{settings.project}'")
    bits.append("embargoed included" if settings.include_embargoed else "embargoed held back")
    bits.append("2 km tetrad refs " + ("included" if settings.include_tetrads else "left off"))
    return "; ".join(bits)
