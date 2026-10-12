# Batch maps and spread over time (R9-7), draft design, 11 Oct 2026

> **Decisions answered 12 Oct 2026** (Q41–Q50 in project note
> `claude/45_Open_Questions_20261012.md`; the draft below is unchanged): the screen **later,
> the script is enough for now** (Q41). Q1 date classes **pre-1970 / 1970–99 / 2000–19 / 2020+,
> editable** (Q42). Q2 class by **first record, latest as an option** (Q43). Q3 **cumulative
> frames, new squares in a second colour** (Q44). Q4 **decades from 1950 plus a "to 1949"
> frame** (Q45). Q5 file names **`Genus_species_grid_area.png`** (Q46). Q6 output
> **`Documents\Observatum batch maps\<date>_<label>\`** (Q47). Q7 **one A4 page per species**
> (Q48). Q8 **keep** an empty species' page and index row (Q49). Q9 **longhorn checklist order**
> (Q50; a checklist CSV is needed). The odd first years noted at the end get a cleaning-report
> check ("date before 1700", Q65).

Wil asked for "a way of running multiple maps with the same settings": for example every
longhorn species in VC23, a range of taxa across several VCs, or full distribution maps for a
taxon group (atlas-style). He also asked for "graphics such as species spread over time".
The engine and a command-line script are built. The screen is not built yet.

## What is built

| File | What it does |
|---|---|
| `Observatum/src/services/batch_maps.py` | The engine (no Qt). `BatchSettings` holds the Mapping panel's fields: sources, dates, VC list (all together or one map per VC), grid, tetrad refs, embargo, recorder, site, project, style and colour. It chooses the taxa (`resolve`: a list of TVKs, every species with records under a family, genus, order or taxon group, or every species with records for the settings). `map_taxon` builds one map, and `file_name`, `write_index` and `describe` handle the output. |
| `Observatum/src/services/batch_spread.py` | The maths for spread over time (pure). Date classes are set by break years, and a square can be classed by its **first** or its **latest** record. Cumulative frames run by decade or by year, with "new this period" marked. |
| `Observatum/src/views/mapping/batch_render.py` | The pages. It draws through the tab's own `GridMap.render_sheet` (the same A4 300 dpi atlas page) and `colour_squares`. The subtitle uses the tab's wording (`map_note`), and the footer wording is the same as `render_atlas`. It can also draw a date-class page, numbered frames with a large period stamp, and an animated GIF when Pillow is installed (Pillow is already an optional dependency of the raster maps). |
| `scripts/batch_maps.py` | The CLI. It is READ ONLY: it writes only PNG files, a GIF, `index.csv` and `settings.txt`. |
| `tests/test_batch_maps_r3.py` | Covers taxon selection, file naming, date classes and frames. It also checks that the figures equal the Mapping tab's for 3 species and settings. |

**Same figures as the Mapping tab, by construction.** Each taxon is one chip passed to
`map_selection.fetch`, which is the tab's single query builder: sources, counting switches,
embargo, and each record counted once. After that, the tab's tetrad rule (`hold_tetrads`) and
`squares_for` apply. Proof on the data copy (Mapping tab driven offscreen against the batch,
both read-only):

| Taxon | Settings | Tab: records / squares / embargoed / merged | Batch |
|---|---|---|---|
| *Rutpela maculata* | All records, GB, hectad | 19,967 / 1,125 / 4 / 59 | the same |
| *Tetrops praeustus* | Personal + Scheme, VC23, tetrad | 19 / 8 / 0 / 0 | the same |
| *Stenocorus meridianus* | Scheme, VC23, hectad | 84 / 22 / 0 / 0 | the same |

Each square's record count and the page footer also match.

### Examples

    py -3.14 scripts\batch_maps.py --group Cerambycidae --vc 23 --sources all
    py -3.14 scripts\batch_maps.py --group Cerambycidae --sources all --res tetrad --out D:\Maps\Longhorns
    py -3.14 scripts\batch_maps.py --tvk NHMSYS0020109270,NBNSYS0000011045 --vc 23 --vc 24 --per-vc
    py -3.14 scripts\batch_maps.py --vc 23 --sources all --list
    py -3.14 scripts\batch_maps.py --tvk NHMSYS0020109270 --sources all --timeclasses --frames decade --from-year 1950

If no `--out` is given, files go to `Documents\Observatum batch maps\<YYYYMMDD_HHMM>_<label>\`.
File names follow the pattern `<Genus_species>_<grid>_<area>[_<suffix>].png`, for example
`Rutpela_maculata_hectad_VC23.png`, `…_dateclass-first.png`, `…_f05_1980s.png` and
`…_spread-decade.gif`.

`index.csv` has one row per map with these columns: taxon, common name, TVK, rank, area,
records, mapped records, squares, first year, last year, undated, embargoed not shown,
duplicates shown once, tetrad refs left off, too coarse, not on GB grid, and file.

Timings on the copy: 42 longhorn species in VC23 at 300 dpi took 75 s. The 4 GB hectad maps
took 21 s.

## Proposed screen (later)

A **Batch maps…** button in the Mapping toolbar, next to Export Atlas PNG. It opens a dialog
that starts from the panel's current settings (sources, dates, VC, grid, tetrad and embargo
boxes, Style), so "what you see is what the batch makes":

1. **Taxa**: three choices.
   - *The chips chosen*: one map per chip.
   - *Every species under…*: a taxon picker, with a count, e.g. "Cerambycidae: 68 species with
     records".
   - *Every species recorded in the area*.

   A preview list with tick boxes lets Wil drop species.
2. **Area**: GB, or the VCs ticked, with a choice between "one map over all of them" and "one
   map per VC".
3. **Pages**:
   - the distribution map (always);
   - a date-class map (break years box, first or latest record);
   - spread frames (decade or year, start year, GIF tick box).
4. **Output folder**: remembered (QSettings `mapping/batch_folder`), with an "Open folder when
   done" tick box.
5. **Run**: runs on a worker thread with a progress bar ("12 of 42: Leptura aurulenta") and a
   Cancel button. When done, it shows a summary with a link to `index.csv`.

The dialog would go in new files (`views/mapping/batch_dialog.py`). The only change to the tab
would be the button and one signal.

## Questions for Wil

1. **Period classes for the date-class map.** *Recommended: Pre-1970 / 1970–1999 / 2000–2019 /
   2020+ as the default, editable as break years.* This splits pre-1970 out the way BRC/BWARS
   atlases do and keeps the current decade apart. The tab's own "Date classes" style stays as it
   is (3 bands, by latest record).
2. **Class by first record or latest record?** *Recommended: first record for "spread"*, because
   it shows when the species reached each square. Latest record is offered as an option, since
   it shows where a species may have been lost.
3. **Frames cumulative?** *Recommended: yes, cumulative, with squares new in that period in a
   second colour.* Non-cumulative "recorded in this decade" frames mostly show recording effort
   rather than spread.
4. **Frame step and start.** *Recommended: decades, starting at 1950, with earlier records lumped
   into a "to 1949" first frame.* Year-by-year from 1675 would make over 300 frames. Year frames
   stay available for recent periods.
5. **File naming.** *Recommended: `Genus_species_grid_area.png` with no number prefix.* The index
   carries the order. Should file names start with a checklist number (`012_Rutpela…`) so the
   folder sorts in taxonomic order? This is useful for atlas page order, but the numbers change
   when a species is added.
6. **Output folder.** *Recommended: Documents\Observatum batch maps\<date>_<label>\ by default,
   with the last folder used remembered.* Should it stay out of OneDrive's synced Biological
   Software folder, so large batches don't sync?
7. **Atlas layout and index sheet.** *Recommended: keep one A4 page per species now, and add an
   optional single PDF later (all pages, plus a first page listing species, records, squares and
   years from index.csv).* Other options are small multiples (6 or 9 species per page, which suits
   longhorn atlas plates) or the subtitle also stating the date filter and VCs, as the batch
   pages already do (the tab's subtitle doesn't).
8. **Empty maps.** A species with records but no square (too coarse, or only tetrad refs with
   tetrads off) still gets a page and a row in the index. *Recommended: keep it, so the set is
   complete. Should it be skipped instead?*
9. **Species order.** This is currently order, then family, then checklist order, else
   alphabetical. There are no checklist files yet (`shared/checklists/` doesn't exist), so the
   longhorns come out alphabetical. *Recommended: add a longhorn checklist CSV (Wil has the scheme's list).*

## Notes found on the way

- Some first years on the copy are implausible: *Alosterna tabacicolor* 1500 and *Acanthocinus
  aedilis* / *Agapanthia villosoviridescens* 1675. These are probably mis-keyed or "range"
  dates in scheme records. The batch only reports them (index.csv `first_year`), but they will
  put squares in the earliest date class. Worth checking in the cleaning report.
- The Rutpela GIF (10 decade frames at 900 px wide) is about 0.9 MB.
