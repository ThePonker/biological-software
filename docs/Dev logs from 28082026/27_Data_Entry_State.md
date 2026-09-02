# Data Entry View — Current State

## Created 29 August 2026 (Session 29)
## Companions: `25_Data_Entry_Research.md` (MapMate / Recorder 6 study),
## `26_Data_Entry_Design.md` (the agreed design)

> This file records what the Data Entry View **actually is**, as opposed to what was
> designed. It was built across July–August 2026 in chats that were not logged, so parts of
> this are reconstructed from the code rather than from a development record.

---

## 1. What it is now

A production data-entry tool inside Observatum, replacing the Tabella Excel round-trip for
desk work. As of 29 August it holds **11 jobs / ~1,787 records** migrated from the season's
workbooks, with identification and tidying in progress.

Built as `DataEntry/` — a self-contained drop-in package of 23 modules, embedded by
Observatum as a tab and openable standalone via `launchers/run_entry.bat`.

## 2. Architecture

**Staging model.** Two tables in `observatum.db`:

- `entry_jobs` — id, name, mode (Personal/Commercial), client, project, embargo_until,
  status (`active` / `committed` / `discarded`), notes, timestamps
- `entry_staging` — one row per record in progress, carrying species and taxon fields,
  the three Session-26 survey columns, context fields, and job-level fields

Typing writes through to `entry_staging` immediately — `staging_repo` commits on every
insert, update and delete. Commit into `observations` is a separate deliberate act.

**Preview vs go-live.** `embed.py` takes `go_live`:

- `False` (the default) — points at the newest `observatum_dev_*.db`, commit disabled
- `True` — points at the live `observatum.db`, enables commit, takes a pre-live `.db`
  snapshot first

`main_window.py` calls it with `go_live=True`. The standalone `python -m DataEntry` launcher
deliberately selects a **dev copy** unless given `--db`, so the embedded tab and the
standalone window can point at different databases. **Use the Observatum tab for real work.**

**Write path.** `commit_service.commit_job()` builds an `Observation` per eligible staging
row and writes it via Observatum's canonical `ObservationModel.create()`, then a
supplementary UPDATE sets `sub_location`, `trap_number`, `visit_number` and the batch stamp.
Rows without a species or date are left in staging and reported.

## 3. The grid

**Columns** (`COLUMNS` in `entry_grid.py`, 19 as of Session 29, in Wil's order):
Species, No., Sex, Stage, Grid ref, Method, Date, Sub-location, Trap, Visit, Comment,
VC No., VC, Recorder, Determiner, Common Name, Order, Family, Site.

Header order and widths are drag-adjustable and saved to QSettings, with a column-count
guard so a change to `COLUMNS` resets the layout rather than crashing.

**Excel-isms implemented:** type-to-overwrite; Delete clears a cell; Tab off the last cell
adds a row; Ctrl+D fill-down; Ctrl+C/V with a rich in-app buffer that preserves species
dicts; paste-to-selection (a single value fills a multi-cell selection); a dashed copy
marker cleared by Escape rather than by paste; Ctrl+Plus / Ctrl+Minus row insert and delete
with a right-click menu; Ctrl+Arrow jumps; Enter commits and wraps to the Species column of
the next row.

**Sorting** is view-only: it reorders the model's rows in place, always sending blanks last,
and an "Entry order" button re-reads from the database to restore. Copy-context auto-disables
while sorted, because "the row above" means something different, and re-enables on restore.
Nothing is written, so the blank spacer rows that carry Wil's date and trap structure survive.

**Species entry** uses a cell-tailored `QListWidget` popup (the proven Session-25 pattern),
not `QCompleter`. Picking a species expands the whole taxon block at once. Clearing the
species cell now clears the taxon block with it.

**Copy-context** fills empty context cells from the nearest filled row above on a species
match. `vice_county` and `vc_number` are deliberately **excluded** — VC is always derived
from the grid ref, never copied, because a different ref can mean a different county.

## 4. The banner

Four cards plus maps, all fixed-height:

- **Species readout** — name, family/order, conservation chips, and count pills.
  Pills show committed records suite-wide with staged rows in brackets, spanning **all**
  jobs, split by job mode.
- **This workbook** — records / species / individuals, plus a per-order breakdown showing
  distinct species with record count in brackets.
- **Traps** — distinct sub-location / trap / grid-ref combinations for the job, grouped
  under bold parcel headings, click-to-copy the grid ref. Filtered to rows with a trap.
- **Location map** (raster OS tiles, vector VC outline fallback) and **distribution map**
  with per-source legend toggles.

The banner is width-constrained: on a 1920px display the cards plus the grid's minimum
column widths can exceed the screen, which clips the maps and legend. If that happens, Qt
prints a `setGeometry` warning and the fix is to trim card widths or column widths.

## 5. Data protection

| Layer | Covers | When |
|---|---|---|
| WAL + `synchronous=FULL`, per-edit commit | every keystroke | continuous |
| `staging_backup.csv` (+prev) | all staging jobs | job close, 15-min timer, commit, app close |
| `observations_backup.csv` (+prev) | observations | after commit |
| Pre-live `.db` snapshot | whole database | per launch, keep 2, 4-hour minimum |

CSVs go to `C:\BiologicalSoftware_Backups\` — outside OneDrive by design, to avoid sync
churn on files rewritten every fifteen minutes.

**Undo.** Every committed row carries `DataEntry batch <ISO timestamp>` in `import_notes`.
`scripts/entry_batches.py` lists batches and removes one by exact stamp after a typed
confirmation.

## 6. Migration tooling

`scripts/load_workbook_to_staging.py` — reads a Tabella `.xlsm` (headers row 4, data row 5,
matched by name), creates one job and its staging rows, normalises dates to ISO, derives VC
from the grid ref, keeps in-data blank spacers and drops the trailing tail. `--dry-run`
reports without writing; `--sheet personal` reads the other sheet.

Written as a one-off for the 2026 season. Retained in case it is wanted again.

## 7. Not yet built

From `26_Data_Entry_Design.md`: **clicker count-mode** (§3.3) and the **repeat key** for
sex splits (§3.1). Both matter for trap-sample processing under the microscope. See
`28_Development_Backlog.md` B2 and B3.

## 8. Known constraints

- Pasting species names from outside the app stores text with no TVK, and commit lets those
  rows through with only a count as warning (backlog B5).
- The standalone launcher points at a dev copy by default — easy to type into the wrong
  database if the distinction is forgotten.
- Personal records are **not** routed through staging by decision: the established path is
  spreadsheet → iRecord → Observatum, and staging them locally would invert which system is
  authoritative and risk duplicates on sync-back.
