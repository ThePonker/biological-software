# Architecture

## Updated 12 October 2026 (Lector window, startup, map layers, shared rule homes)

---

## 1. The suite

Latin-themed desktop tools sharing a common data layer, built with
Python / PySide6 / SQLite by a single developer, Wil Heeney, trading as Flauna.

| Name | Meaning | Purpose |
|---|---|---|
| **Observatum** | "that which has been observed" | Main recording app — observations, specimens, recording scheme, Data Entry |
| **Examen** | "examination / swarm of bees" | Invertebrate assemblage assessment; replaces the Pantheon website |
| **Codex** | "book of law" | Conservation authority — database plus a maintenance GUI |
| **Curator** | "the one who takes care" | Insect collection organiser — box planning, labels |
| **Tabella** | "writing tablet" | Field workbook generator (Excel+VBA). **Retired 7 Oct 2026** to `_archive\Tabella_20261007` — superseded by Data Entry |
| **Lector** | "reader" | Biodiversity Heritage Library reader (BHL API v3): saved searches for a species and its synonyms, page text, a reading list, Word/Excel/PDF dossiers; writes `data\lector.db`. Joined 7 Oct 2026; desktop window 12 Oct (§4d). Paused |
| **Munia** | "duties" | Capacity planner (not in use until work comes in) |
| **Atrium** | "entrance hall" | System-tray launcher; one copy at a time; tiles for the apps, a Tools row for console tools (Lector console) |
| **Data Entry** | — | The recording grid, a drop-in package opened from Observatum — see `09` |

Codex is infrastructure, not a product: nobody uses it directly, and its measure
of success is whether Observatum and Examen always get accurate conservation data.

---

## 2. Folder structure

```
Biological Software/
├── paths.py                 Suite-wide path registry — PERMANENT, never delete
├── run.bat                  Observatum launcher
├── CLAUDE.md                Instructions for Claude Code (rules, safety, where things are)
├── .claude/settings.json    Claude Code deny rules: no deletion, no destructive git
├── .git/  .gitattributes    main (development) / stable (field-season tool)
├── shared/                  UI-agnostic library — the analysis engine and the one home of
│   │                        each suite-wide rule (table in §4e)
│   ├── maps/                The map: grid_map, map_layers, coast, vc_topology, vc_labels,
│   │                        atlas_sheet, project_many, grid_squares ... (§4c)
│   ├── repositories/        CodexRepository · PantheonRepository
│   └── services/            PantheonAnalysisService
├── Observatum/              Main app; src/ re-exports from shared/ via shims
├── DataEntry/               Drop-in package, 23 modules — see 09
├── Examen/                  Assessment tool — see 08
│   └── workbook_export.py   Multi-sheet Excel assessment workbook
├── Codex/                   Conservation manager GUI
├── Curator/  Munia/  Atrium/
├── Lector/                  BHL reader: engine, service.py (the UI's only API), ui/ (§4d)
├── data/                    The databases, incl. lector.db (git-excluded, backup-protected)
├── scripts/                 Build, reset, import, patch and check scripts
│   ├── build_gb_basemap.py  Builds the GB basemap for Data Entry — keep (moved here 7 Oct)
│   └── _oneoff/             One-off data-changing scripts, git-ignored, archived later
├── launchers/               run_atrium, run_codex, run_lector (console), run_lector_gui, run_munia
├── tests/                   pytest suite (~1,220 tests); manual_import_files/ for Wil's import tests
├── _archive/                Retired code, dated
└── docs/                    This set, the research documents, Lector_User_Manual.md, drafts/

C:\BiologicalSoftware_Backups\    Outside OneDrive by design
├── current/  previous/           Working databases, two generations
└── reference/                    Codex/Pantheon/UKSI copies, on demand

D:\BiologicalSoftware_Offsite\     External drive — mirror of both of the above
```

Spider Extract moved out on 7 Oct to `OneDrive\Natural History Tools\Spider Extract`
(its own git repo). `Observatum\` is ~200 MB, almost all `test data\` (~120 MB,
including the **Pantheon 3.7.4 source CSVs that D5 needs**) and `BackUps\` (~86 MB of
CSV exports and the close-time CSV safety backup). Neither is in git.

**`build_gb_basemap.py`** was deleted in September and restored from git before
the deletion was committed. It is a build script, and build scripts are exactly
what this project has lost before (`uksi_extractor.py`, `build_pantheon_db.py`).
Being recoverable from history is not the same as being where you would look.

**`paths.py` is load-bearing.** Every project does `import paths` rather than
walking `.parent.parent`. It was accidentally deleted once during the March 2026
restructure for "looking like a temp utility script"; it now carries a banner and
`run.bat` checks for it.

**The re-export shims** — `Observatum/src/repositories/codex_repository.py` and
similar — are three-line files importing from `shared/`. That is deliberate:
import, don't copy. Note that a filename search returns both the shim and the
implementation, and the shim is the small one.

---

## 3. The databases

| Database | Holds | Written by |
|---|---|---|
| `observatum.db` | Observations, specimens, recording scheme, Data Entry staging | Observatum |
| `codex.db` | Conservation status, SQS, TVK bridge | `build_codex_db.py`, Codex Manager |
| `uksi.db` | Taxonomy — names, TVKs, sort codes, synonyms; `name_map`, `tvk_remap`, `taxon_qualifiers` | `build_uksi_from_release.py` (NHM *Simplified Copy*) |
| `pantheon.db` | Ecology — biotopes, habitats, SATs, guilds, fidelity | `build_pantheon_db.py` (rebuilt 9 Oct, D5) from the 3.7.4 CSVs |
| `vc_lookup.db` | Vice-county per 1 km square | Shapefile import |
| `vc_splits.db` | The 1 km squares a VC boundary crosses, each VC's share (F29) | `build_vc_splits.py` |
| `lector.db` | Lector: BHL answers, pages and text, saved searches, runs, review notes, activity (schema v3) | Lector (`Lector/store.py`, `saved.py`); updates by `Lector/upgrade.py` |
| `data/maps/*` | `vc_brc_wgs84.geojson` (VC outlines, from `convert_vc_shapefile.py`), `gb_outline.json` (on the PC: 2013 ONS districts, no build script), `uk_vice_counties.svg` | scripts / by hand |
| `examen.db` | Frozen assessments -- **retired 9 Oct 2026** (E13); nothing reads or writes it now. Export: `scripts/export_examen_snapshots.py` | none (still backed up) |
| `munia.db` | Project allocations, day logs | Munia |
| `gamification.db` | Achievements | Observatum |

### Which app reads what

| | observatum | codex | uksi | pantheon | vc_lookup |
|---|---|---|---|---|---|
| Observatum | read/write | read | read | read | read |
| Examen | read | read | read | read | — |
| Curator | read | — | read | — | — |
| Lector | — | — | read | — | — |
| ~~Tabella~~ (retired) | — | read | read | — | read |
| Codex Manager | — | read/write | read | read | — |
| Munia | — | — | — | — | — |

---

## 4. The TVK bridge — the join that matters

`pantheon.db` is keyed on **Pantheon's 2017 TVKs**. Everything else works in
**current UKSI TVKs**. `codex.db.tvk_bridge` translates between them.

Getting this wrong is silent. Two instances found on 5 September 2026:

- The bridge itself never consulted `uksi.synonyms`, so 3,000 species were
  dropped entirely.
- `PantheonRepository` queried Pantheon with UKSI TVKs and never used the
  bridge at all, so **3,666 species returned no ecology** — of 400 sampled,
  zero were found. Habitat and SAT figures in every assessment were computed
  over the directly-matched species only.

`PantheonRepository` is now bridge-aware: it translates on the way in, maps back
on the way out, unions across taxa that merged, and takes the incumbent's SQS.
Callers pass current UKSI TVKs and need know nothing about it.

**Rule: any join between Pantheon and anything else goes through the bridge.**

### 4a. Taxon groups — one grouping (10 October 2026)

`shared/taxon_groups.py` is the only taxon-group rule. Records carry iRecord's
label in `taxon_group` ("insect - beetle (Coleoptera)") on observations,
recording_scheme and specimens. A label that arrived with the record (iRecord,
NBN/iRecord-format scheme files) is kept; otherwise it is worked out from UKSI by
TVK (family → order → class → phylum → kingdom; blank rather than a guess) by the
three import wizards, Data Entry commit and Quick Entry. Old blanks:
`scripts/backfill_taxon_groups.py` (dry run; `--apply`; `--relabel` corrects
labels the suite itself wrote).

- **Stats curves** show the short labels and merges in `CURVE_LABELS` /
  `CURVE_MERGES` (`group_label`, `merge_curve_groups`).
- **Filtering / Mapping** use `group_sql()` / `group_filter_sql()`: the stored
  label, else one from order and family. The Filter Wizard's *Taxon group* box
  (key `group`; shown on a tab only once that tab applies it -- so far Observation
  Data) uses it; its key `taxon_group` is the **Order** box.
- **Not this grouping:** Examen's Pantheon groups (assemblage types from
  `pantheon.db`) and the gamification colour groups.

---

### 4b. Observatum startup: "window early, rest behind" (Round 6, 11 Oct; Round 8, 12 Oct)

| Module (`Observatum/src/views/`) | Job |
|---|---|
| `startup_preload.py` | Under the splash: Home, Observation Data, Contributed, Insect Collection. Record reads in worker threads; the GUI thread pumps events |
| `splash_progress.py` | The splash bar as named steps with typical durations, so it moves evenly |
| `main_window_background.py` | `start_background()` after the window shows; the "Still loading: …" status line; a tab clicked early jumps the queue |
| `background_loader.py`, `background_steps.py` | The steps behind the window, in order: Recording Scheme records, Stats/Reports, Mapping (outlines, coast and border lines, first drawing), Settings (per panel), species-search index. Data work in threads (`InThread`), widget building in short slices (`yield`) |
| `lazy_tab.py` | `LazyTabPage`: build in slices (`build_steps`) or at once (`ensure_built`, the fallback on first opening) |
| `pending_cover.py` | "Finishing loading…" over a tab whose records are not in yet |
| `json_pieces.py` | Parse the big geojson a piece at a time so the GIL is let go |
| `pause_watch.py` | `run.bat --timing` only: a watchdog samples the GUI thread's stack during any pause over 50 ms; prints every pause over 100 ms with where it happened, and GC passes over 20 ms |

Rules learned (Round 8): Python's garbage collector is switched off while loading and the
loaded objects frozen (`gc.freeze`) -- it is always switched back on, including on errors and
early close; a table that resizes columns to contents must be settled (`settle_headers`) before
a background result lands; closing during loading stops and waits for the threads before the
WAL checkpoint.

### 4c. The Mapping tab's map (`shared/maps/`)

`grid_map.py` (`GridMap`) draws, bottom to top (R5 order, `map_layers.py`): sea, land, the
tint of VCs holding records, the coast, the grid, **VC boundaries**, **districts** (thin dashed
grey, when switched on), the **recorded squares** (with the Square opacity, R8), the selected
VC's outline, the **labels**. The same drawing makes the screen and the A4 300 dpi atlas page
(`atlas_sheet.py`), so the PNG shows what the screen shows.

- `vc_topology.py` snaps neighbouring VC rings onto shared points so each border is one line
  (`snap_rings_cached`, keyed on geojson and simplification); `unique_chains` gives every edge once.
- `coast.py` splits the land's ring edges into sea-facing (the coast) and inland (district
  borders) (`split_edges_cached`). **Cache keys:** the land's split is keyed on its source;
  the VC boundary layer on `("vc_topo", geojson, simplification, "r5")`. They once shared a
  key and the boundaries came out doubled after the first paint (F47).
- `vc_labels.py`: labels in device pixels as one path (numbers nationally, names zoomed in),
  nudged off recorded squares; boundary drawing; the selected VC outline.
- `project_many.py`: WGS84 → OSGB on numpy arrays (outlines project in about 1 s).
- Switches remembered in QSettings: VC labels, VC boundaries (on), Districts (off; to be
  renamed "Local authority districts" and sourced from Boundary-Line, Q35/Q39), Square opacity
  (0–100 %, `Observatum/src/views/mapping/display_bar.py`).
- `Observatum/src/services/batch_maps.py` + `scripts/batch_maps.py`: the same query, squares
  and page for many taxa at once, date-class and cumulative spread frames, GIF.

### 4d. Lector (`Lector/`)

| Layer | Modules |
|---|---|
| BHL and engine | `bhl_client.py` (one request a second), `harvest.py` (filters), `engine.py` (run a saved search: name search → filters → pages → text), `names.py` (tolerant name finding), `synonyms.py` (which older names, held back with a reason), `species_source.py` (UKSI) |
| Store | `store.py`, `saved.py`, `schema.py` (**v3**), `upgrade.py` (dry run on an in-memory copy; apply backs up with `conn.backup()` to `data\_backups\lector_pre_v3_<time>.db`, only adds) |
| Service | `service.py` -- **the only API the window uses**, no Qt; documented in `Lector/SERVICE_API.md`. Network methods take `progress` and `cancel` and run in worker threads |
| Exports | `exporting.py`, `dossier.py` (Word + Excel index), `pdf.py` (Word via docx2pdf, or LibreOffice), `export.py` (text), `entries.py`, `excerpts.py` |
| Window | `ui/app.py` (left menu, one screen at a time), `searches.py` (dashboard), `builder*.py` (new/edit search), `history.py` (a search's runs and what changed), `review_screen.py` / `review_panes.py` (reading list), `export_screen.py`, `common.py` (Back button frame), `workers.py`, `style.py` (Observatum theme, Steel Blue accent) |
| Console | `__main__.py`: `gui`, `probe`, `fetch`, `status`, `export`, `synonyms`, `forget`; `fetch` leaves a saved search alone unless `--replace-search` |

Opened by Atrium's Lector tile or `launchers\run_lector_gui.bat`; the console from Atrium's
Tools row or `run_lector.bat`. Your own name decisions: `data\lector_synonyms.txt` (`+`/`-`
lines). Manual: `docs/Lector_User_Manual.md`.

### 4e. One home per rule (added 10–12 Oct)

| Rule | Home | Used by |
|---|---|---|
| What kind of name a record carries (genus, family+, agg., s.l., s.s., hybrid, subsp.) | `shared/record_kinds.py` | counting switches, cleaning report |
| Which records count, per source | `shared/species_counting.py` | Home, Stats, Mapping, Species lookup, achievements, exports, Data Entry map |
| Taxon group | `shared/taxon_groups.py` | imports, Data Entry, filters, Mapping, Stats curves |
| Species search (typo-tolerant, group words) | `shared/species_search.py`, `species_filter.py`, `fuzzy_words.py` | every species box |
| Close spellings in imports | `shared/species_close_spelling.py` | the three import wizards |
| Species lookup in imports | `shared/species_lookup.py`, `species_lookup_entries.py` | the three import wizards (C4 stage 1) |
| iRecord record link | `shared/irecord_links.py` | record details, Mapping square list, cleaning report |
| Specimen ↔ field record | `shared/specimen_links.py`, `record_match.py` | Edit Specimen, link/unlink scripts, reports |
| Grid ref ↔ lat/long | `shared/osgb.py` (+ `maps/project_many.py`) | imports, Data Entry, Mapping |
| Tick mark | `shared/tick_mark.py` | Observatum tick column, Lector check boxes |
| Fit a window to the screen | `shared/fit_to_screen.py` (`fit_to_screen`, `scroll_body`) | Observatum dialogs and wizards, Curator, Munia, standalone Data Entry, Lector |
| Read-only reference connections | `shared/db_open.py` (`connect_ro`) | every app |
| Photo names and matching | `shared/photo_names.py`, `photo_match.py` | `check_media_library.py` (photos not wired in yet) |
| Checklist order within a family | `shared/checklist_order.py` | drawer assignment, batch maps (no checklist files yet) |

---

## 5. Rebuild chains

Order matters. Never rebuild Codex before UKSI or Pantheon — it depends on both.

```
UKSI.mdb → uksi.db → pantheon.db → codex.db → seed
```

### Codex (the one that actually gets run)

```
python scripts/build_codex_db.py     # JNCC spreadsheet → designations,
                                     # status_summary, tvk_bridge, sqs_scores
python scripts/seed_codex.py         # invertebrate filter check
```

`build_codex_db.py` **deletes and recreates** codex.db, preserving
`manual_entries`, `reviews` and `species_profiles` from the old file first.
Schema changes therefore take effect on rebuild with no migration.

Back up first, always:

```powershell
python -c "import sqlite3,paths,os,datetime; d=r'C:\BiologicalSoftware_Backups\reference'; p=os.path.join(d,'codex_pre_X_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'.db'); s=sqlite3.connect(str(paths.CODEX_DB)); t=sqlite3.connect(p); s.backup(t); t.close(); s.close(); print(p)"
```

### JNCC update

New spreadsheet → `data/conservation-designations-YYYYMMDD/` → update `JNCC_DIR`
in `paths.py` → rebuild as above.

### UKSI update

From the NHM Data Portal's **UK Species Inventory – Simplified Copy** (an `.xlsx`,
~42 MB; the portal names the download by resource id). Its NAMES sheet carries
the Nameserver mapping -- every name TVK to its recommended TVK. First done
6 October 2026 (December 2023 → July 2025).

```
python scripts/check_uksi_simplified.py  <xlsx>   # what it resolves (read only)
python scripts/build_uksi_from_release.py <xlsx>  # writes data/uksi_2025.db only
python scripts/check_uksi_2025.py                 # duplicates, lost names, TVK-keyed data
python scripts/lookup_lost_names.py               # current taxa for lost names (read only)
```

The builder keeps `uksi.db`'s schema exactly (copied from the current file),
current taxa only (REDUNDANT_FLAG excluded), every other Latin name a synonym,
English names (July sheet + carried from the old file), `name_map`, a
`tvk_remap` for every old TVK the suite holds, and **kept taxa**: any taxon your
data uses with no replacement, plus `KEEP_BY_REQUEST` (24 beetles). Names stay
plain; qualifiers go to `taxon_qualifiers`. Read its report before switching:
parent links outside the file must be 0; same-name rejections should be only
cross-kingdom homonyms and subgenus/genus pairs.

**Switching:** close every app; back up `uksi.db`, `codex.db`, `observatum.db`;
check `data\*.db-wal` is empty; rename `uksi.db` → `uksi_2023.db` (or the old
release's year) and the new file → `uksi.db`; then the steps below.

### Pantheon rebuild

`scripts/build_pantheon_db.py` (D5, 9 Oct) reproduces `pantheon.db` from the Pantheon 3.7.4
source CSVs in `Observatum\test data\`; species without a TVK are keyed `NOTVK:<name>`.
`--out` builds to a file; `--replace` backs up, retires the old file to `_archive` and swaps
in. Then rebuild Codex. Pantheon has not moved since 2017.

### After a UKSI update

1. **Rebuild Codex** (`build_codex_db.py`, `seed_codex.py`). It translates old
   TVKs -- JNCC's, and the review statuses, accounts and manual SQS it restores --
   through `uksi.tvk_remap` / `name_map`, and reports how many. Account collisions
   are kept-first and listed.
2. **The post-rebuild checks** in `07_Codex.md` §8, and `check_sqi_table.py
   --compare`. Expect cleanup where translation joined a "pro parte" TVK to its
   species (`clear_legacy_detail.py`, `clear_stale_legacy.py`).
3. **Remap records and own profiles:** `remap_record_tvks.py` (dry run), then
   `--apply`. Updates TVK, name and the whole taxonomy block together; refuses
   unless the new file is the live `uksi.db`.
4. Check the app. (Tabella workbooks are retired.)

---

## 6. Version control

Local git at the project root, pushed to the private GitHub repo
`ThePonker/biological-software`. `main` for development, `stable` intended as the
field-season tool. **`stable` has not been updated since June 2026**; Wil decided on 12 Oct
to merge `main` into it now that Round 8 is committed (Q88). Agent rounds are built on
branches in separate clones and merged before delivery; Wil commits on the PC.

Excluded: `data/`, `_archive/`, `_backups/`, test data, `.bak` variants.
Databases are protected by the backup system, not by git.

Known friction: OneDrive locks `.git/objects` during git's post-commit tidy-up,
prompting *"Deletion of directory … failed. Should I try again?"* The commit is
already written; answer `n`. Set `GIT_ASK_YESNO=false` as a user environment
variable to stop the prompt.

`.gitignore` also excludes `_dump/`, the source dump used for code review.

---

## 7. Data protection

| Layer | Covers | When |
|---|---|---|
| WAL + `synchronous=FULL`, per-edit commit | every keystroke | continuous |
| `backup_service` working tier | observatum, munia, examen, gamification | Observatum close |
| `backup_service` pre-commit | observatum | before every Data Entry commit — **blocks the commit if it fails** |
| `backup_service` reference tier | codex, pantheon, uksi, vc_lookup | on demand after a rebuild |
| `staging_backup.csv` (+prev) | all staging jobs | job close, 15-min timer, commit, app close |
| `observations_backup.csv` (+prev) | observations | after commit |
| OneDrive version history | the project folder | continuous |
| **Off-site copy** | project folder + backups folder | **by hand, after sessions that change data** |

Every `.db` copy uses `conn.backup()`, never `shutil.copy2` — copying a WAL-mode
database while open can capture a main file missing recent commits.

**Restore:** `python scripts/restore_database.py`, with the app closed. Tested
end to end 4 September 2026.

### The off-site copy

Close Observatum and Examen first — `robocopy` knows nothing about SQLite, and
copying a WAL-mode database while it is open is the fault fixed in Session 30.

```powershell
$dest = "D:\BiologicalSoftware_Offsite"
robocopy "C:\Users\Wil J. Heeney\OneDrive\Biological Software" "$dest\Biological Software" /MIR /R:1 /W:1 /XD __pycache__ /NFL /NDL /NP
robocopy "C:\BiologicalSoftware_Backups" "$dest\BiologicalSoftware_Backups" /MIR /R:1 /W:1 /NFL /NDL /NP
```

Check **FAILED** reads 0 in both summaries. `/MIR` mirrors, so later runs copy
only what changed — and deletes anything on the destination absent from the
source, so point it at this dedicated folder, never a drive root.

Then verify, rather than assume:

```powershell
python -c "import sqlite3; c=sqlite3.connect(r'D:\BiologicalSoftware_Offsite\Biological Software\data\observatum.db'); print(c.execute('PRAGMA integrity_check').fetchone()[0]); print('specimens:', c.execute('SELECT COUNT(1) FROM specimens').fetchone()[0])"
```

First run 26 September 2026: 3.8 GB in eleven minutes, `ok`, 2,745 specimens.
**Keep the drive away from the computer** — a fire, flood or theft takes both
otherwise.
