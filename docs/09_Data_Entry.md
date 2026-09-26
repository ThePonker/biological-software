# Data Entry

## The recording grid
## Updated 5 September 2026
## Consolidates `26_Data_Entry_Design.md` (the design) and
## `27_Data_Entry_State.md` (what was built). The research behind it is in
## `25_Data_Entry_Research.md`, which remains worth reading.

---

## 1. What it is

A fast, keyboard-driven observation-entry grid writing directly to
`observatum.db`. It replaces the Tabella Excel round-trip for desk work.

Built as `DataEntry/` — a self-contained package of 23 modules, embedded by
Observatum as a tab and openable standalone via `launchers/run_entry.bat`.

**In production.** 13 jobs, 12 active, ~2,373 staged rows, nothing yet committed
to `observations`.

It captures **observations only**, Personal and Commercial. Specimens go through
the Insect Collection tab. Conservation and taxonomy are shown read-only as a
confirmation aid, never captured — inspection of a live workbook found the
conservation columns 0–6% filled, which is proof they were glance-aids rather
than data.

---

## 2. Why it exists

The central use case is **trap-sample processing**: working down a pitfall or
flight-interception sample under the microscope, entering many species that share
date, site, grid reference, parcel, trap and visit, and differ only in species,
sex and quantity. A single trap can be 30–40 determinations.

Inspection of a 218-record workbook showed the pattern: species, sex and quantity
reordered to the front by hand; date, recorder, determiner, method, stage and
certainty identical down a session; vice-county never typed.

The strategic gap, from studying MapMate and Recorder 6: MapMate's entry speed
without its dead Access-97 runtime; Recorder 6's data integrity without its
weight; a spreadsheet's immediacy without its error-proneness. No current product
occupies that space for a serious specialist recorder.

---

## 3. Architecture

**Staging model.** Two tables in `observatum.db`:

- `entry_jobs` — id, name, mode, client, project, embargo_until, status
  (`active` / `committed` / `discarded`), notes, timestamps
- `entry_staging` — one row per record in progress, carrying species and taxon
  fields, the three survey columns, context fields and job-level fields

Typing writes through to `entry_staging` **immediately** — `staging_repo` commits
on every insert, update and delete. Commit into `observations` is a separate,
deliberate act.

**Preview versus go-live.** `embed.py` takes `go_live`:

- `False` (default) — points at the newest `observatum_dev_*.db`, commit disabled
- `True` — points at the live database and enables commit

`main_window.py` calls it with `go_live=True`. The standalone launcher
deliberately selects a **dev copy** unless given `--db`.

> ⚠️ **Use the Observatum tab for real work.** A stale dev copy was found in
> `data/` in September that the standalone launcher would have opened by default
> — typing into a two-month-old database. It has been removed, but the trap
> remains.

**Write path.** `commit_service.commit_job()` builds an `Observation` per
eligible staging row and writes it through Observatum's canonical
`ObservationModel.create()`, then a supplementary UPDATE sets `sub_location`,
`trap_number`, `visit_number` and the batch stamp. Rows without a species or date
stay in staging and are reported.

**Schema addition** (June 2026): `sub_location`, `trap_number`, `visit_number` on
`observations`. Internal, excluded from iRecord export, available to filtering
and to Examen's compartment analysis. "Run the assessment for Parcel 4 only"
becomes a structured filter rather than a free-text grep.

---

## 4. The grid

**Columns** (19, in Wil's order): Species, No., Sex, Stage, Grid ref, Method,
Date, Sub-location, Trap, Visit, Comment, VC No., VC, Recorder, Determiner,
Common Name, Order, Family, Site.

Header order and widths are drag-adjustable and saved to `QSettings`, with a
column-count guard so a change to `COLUMNS` resets the layout rather than
crashing.

**Excel-isms implemented:** type-to-overwrite; Delete clears a cell; Tab off the
last cell adds a row; Ctrl+D fill-down; Ctrl+C/V with a rich in-app buffer
preserving species dicts; paste-to-selection; a dashed copy marker cleared by
Escape; Ctrl+Plus / Ctrl+Minus row insert and delete; Ctrl+Arrow jumps; Enter
commits and wraps to the Species column of the next row.

**Sorting is view-only.** It reorders the model's rows in place, blanks last, and
an "Entry order" button re-reads from the database to restore. Copy-context
auto-disables while sorted, because "the row above" means something different,
and re-enables on restore. Nothing is written, so the blank spacer rows carrying
date and trap structure survive.

**Species entry** uses a cell-tailored `QListWidget` popup — the proven pattern
from the Session 25 rewrite, not `QCompleter`. Picking a species expands the
whole taxon block; clearing the cell clears the block with it.

**Copy-context** fills empty context cells from the nearest filled row above on a
species match. `vice_county` and `vc_number` are **deliberately excluded** — VC
is always derived from the grid reference, never copied, because a different
reference can mean a different county.

---

## 5. The banner

Four fixed-height cards plus maps:

- **Species readout** — name, family and order, conservation chips, count pills.
  Pills show committed records suite-wide with staged rows in brackets, across
  all jobs, split by mode.
- **This workbook** — records, species, individuals, and a per-order breakdown
  showing distinct species with record counts.
- **Traps** — distinct sub-location / trap / grid-ref combinations for the job,
  grouped under bold parcel headings, click-to-copy the grid reference.
- **Location map** (raster OS tiles, vector VC outline fallback) and
  **distribution map** with per-source legend toggles, built from
  martinjc/UK-GeoJSON reprojected.

The banner is width-constrained: on a 1920px display the cards plus the grid's
minimum column widths can exceed the screen, clipping the maps and legend. Qt
prints a `setGeometry` warning; the fix is to trim card or column widths.

---

## 6. Data protection

| Layer | Covers | When |
|---|---|---|
| WAL + `synchronous=FULL`, per-edit commit | every keystroke | continuous |
| `staging_backup.csv` (+prev) | all staging jobs | job close, 15-min timer, commit, app close |
| `observations_backup.csv` (+prev) | observations | after commit |
| `backup_service` pre-commit | whole database | before every commit — **blocks the commit if it fails** |

CSVs go outside OneDrive, to avoid sync churn on files rewritten every fifteen
minutes.

**Undo.** Every committed row carries `DataEntry batch <ISO timestamp>` in
`import_notes`. `scripts/entry_batches.py` lists batches and removes one by exact
stamp after a typed confirmation.

---

## 7. Migration tooling

`scripts/load_workbook_to_staging.py` reads a Tabella `.xlsm` (headers row 4,
data row 5, matched by name), creates one job and its staging rows, normalises
dates to ISO, derives VC from the grid reference, keeps in-data blank spacers and
drops the trailing tail. `--dry-run` reports without writing; `--sheet personal`
reads the other sheet.

Written as a one-off for the 2026 season; retained in case it is wanted again.

---

## 8. Not yet built

**Clicker count-mode** (backlog B1). A configurable keystroke increments the
current quantity; a second decrements for corrections. Works from the spacebar,
an on-screen button, or a **USB foot pedal programmed to emit that keystroke** —
so it needs no hardware, and a pedal is an optional improvement. A large,
glanceable counter lets the total be checked without leaving the eyepieces. The
flow is ID-first: species and sex set, then count-mode on quantity, then Enter.

**Repeat key** (B2). Clones the just-entered row and lands on Sex — for
same-species sex splits, three males then two females, common in spiders,
Diptera and Hymenoptera. Four keystrokes for the second row.

Both matter for microscope work and neither is hard; they have simply not been
reached.

---

## 9. Known constraints

**Pasted species names store as text with no TVK**, and commit lets those rows
through with only a count as warning (B4).

**The standalone launcher points at a dev copy by default.** Easy to type into
the wrong database if the distinction is forgotten.

**Row insert below the new-row marker does not work** (B5). Committed, incomplete,
there is a workaround.

**Personal records are deliberately not routed through staging.** The established
path is spreadsheet → iRecord → Observatum, and staging them locally would invert
which system is authoritative and risk duplicates on sync-back.

---

## 10. Out of scope, by decision

**Specimens** — entered via the Insect Collection tab.

**The iRecord round-trip** — export, upload, sync-back, verification, keys. All
existing Observatum infrastructure; records from this tool flow into it
unchanged.

**Comment stripping** — comment is plain pass-through. Survey structure lives in
the structured fields, not in free text.

**Per-parcel mapping** — a possible future, but the `sub_location` TEXT column
covers the analysis need.
