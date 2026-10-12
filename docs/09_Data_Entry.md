# Data Entry

## The recording grid
## Updated 12 October 2026 (§5 banner, §8 built since, §9 constraints)
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
  (`active` / `committed` / `discarded` / `exported`, and for Personal jobs
  `awaiting_irecord` / `irecord_returned` — §7b), notes, timestamps
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

**Species account** -- the same dialog the other tabs open (published accounts
above, yours below): double-click the **row number**, right-click → *Species
account…*, or **Ctrl+I**. A double-click on a cell still edits it, so the
species picker is unchanged. A row with no species says so; a staged name with
no TVK opens read-only. Standalone, outside Observatum, a short message instead.

**Column-header right-click** shows and hides columns -- broken until 6 October
by stray row-menu lines (`NameError`).

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
  all jobs, split by mode. The specimen pill carries the sex of held specimens —
  `Spec. 13 (♀1 +12)` — so "do I need to keep this male?" is answerable at the
  scope. Card widened from 272 to 316px to fit it.
- **This workbook** — records, species, individuals, and a per-order breakdown
  showing distinct species with record counts.
- **Traps** — distinct sub-location / trap / grid-ref combinations for the job,
  grouped under bold parcel headings, click-to-copy the grid reference.
- **Location map** (raster OS tiles, vector VC outline fallback) and
  **distribution map** with per-source legend toggles, built from
  martinjc/UK-GeoJSON reprojected.

**Narrower windows (R9-8, Round 3, 11 Oct).** The banner measures its cards at runtime:
on a narrower window Traps steps aside first, then This workbook; the legend is never cut
off; a scroll bar under the banner is the last resort; buttons are no longer clipped. Data
Entry never forces the window wider than it is (it had forced 1,563 px on Wil's PC). The
conservation chips read S.41 / SBL / S7 / Protected, with the full label on hover, and fold
into "+n" when they don't fit. Standalone Data Entry opens fitted to the screen (Round 5).

**Short screens.** At 1280×720 (a laptop at 150 %) the grid shows about 7 rows. Decided
12 Oct (Q54): a toggle that folds the cards to one line. In the small-fixes round.

---

## 6. Data protection

| Layer | Covers | When |
|---|---|---|
| WAL + `synchronous=FULL`, per-edit commit | every keystroke | continuous |
| `staging_backup.csv` (+prev) | all staging jobs | job close, 15-min timer, commit, app close |
| `observations_backup.csv` (+prev) | observations | after commit (connected 9 Oct 2026 — it never ran before) |
| `backup_service` pre-commit | whole database | before every commit — **blocks the commit if it fails** |

CSVs go outside OneDrive, to avoid sync churn on files rewritten every fifteen
minutes. The staging CSV is also written **before** Delete job, Discard job and
Export-and-clear; if it cannot be written, Data Entry asks before going on (9 Oct 2026).

**A commit that fails part-way** stops at the failing row and says how many records were
written (they are in Observatum under the batch stamp; the rest stay in staging), and
Observation Data is refreshed. A record written whose follow-up fields failed is still
taken out of staging, so a retry cannot double it.

**What a commit writes (9 Oct 2026).** Besides the grid's fields: `taxon_group`,
`kingdom`, `taxon_rank`, `superfamily` and `taxonomic_sort_key` from UKSI for the TVK
(`shared/taxon_groups.py`; before this, 1,440 committed records had no taxon group), and
the date type from what was typed. A year alone ("2026") commits as 2026-01-01 with date
type `Y`; a month and year ("06/2026", "Jun 2026") as the 1st with `O`. Dates that cannot
be read ("31/02/2026", "summer") are tinted in the cell, listed by Check before commit and
left in staging. Check before commit also lists future dates, rows with no recorder and
rows with no vice-county. The VC clears when the grid ref is cleared or cannot be read.

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

## 7a. Commercial jobs after commit (8 October 2026)

A commercial job's records are grouped everywhere -- Examen, Commercial Reports, the
iRecord export -- by the **exact** Project and Client strings. So:

- **New job:** Project and Client are pickers of every name already used (committed
  records and jobs). Typing a name that differs from an existing one only by case or
  spacing is snapped to the existing spelling. Picking an existing project fills its
  client when it has only one.
- **Adding to a finished job:** when every row of a commercial job is committed the
  job is marked `committed` and drops out of the list. Tick **Show committed** and
  **Reopen** it (or Open it, which asks). The grid starts empty -- earlier records stay
  in Observatum -- and the next commit is a new batch under the same project and
  client, so `check_data_entry_batches.py` checks only the new rows.
- **From Commercial Reports:** a project's **Add records** does the same in one step,
  creating a job when the project came in by import, and carries the project's current
  embargo -- the commit's embargo dialog then offers that date.
- Editing or deleting committed records is done in Observation Data (Commercial
  Reports' **View / edit** opens it filtered to the project).
- **Comments** typed in the grid are written on commit from 8 October; before that
  they were dropped (fault F31).

## 7b. Personal jobs go to iRecord (9 Oct 2026)

Personal records are iRecord-first, so a Personal job has no Commit. Its button is
**Export for iRecord**: a CSV in iRecord's import layout — Species, TVK (only when it is a
current UKSI taxon), Date (05/06/2026, Jun 2026 or 2026), Grid reference, Location name,
Recorder(s), Determiner, Abundance, Stage, Sex ("Not recorded" left blank), Sample
method, Comment. A row with a species but no readable date blocks the export. The job is
then **exported – awaiting iRecord**: its rows are kept, it stays on the Jobs list, and the
standing Personal job is renamed "Personal – exported dd/mm/yyyy" so a fresh one takes its
place.

After importing the file into iRecord and running Observatum's iRecord sync, select the
job and choose **Check iRecord return**. Each row is matched to an observation that now
carries an iRecord ID: same TVK (or name), date and grid ref, and recorder — a second pass
without the recorder catches names iRecord writes differently, and says how many. When
all are back the job can be closed (`irecord_returned`; rows kept, no longer counted as
staged); otherwise the missing rows are listed. Commercial jobs commit as before.

## 8. Built since 8 October

- **Count mode (F9)** (B1, 9 Oct): Space / + / F13 add one to the current row's No., - takes
  one off, Enter moves on; a large counter; keys in QSettings (`DataEntry/countUpKeys`,
  `countDownKeys`), so a USB foot pedal works.
- **Repeat key, Ctrl+R** (B2, 9 Oct): copies species, stage and context into a new row below
  and lands on Sex.
- **Paste and common names** (B4, B6, 9 Oct): pasted names go through the typing rules and are
  never guessed; a single hit reached only through part of a common name asks first.
- **Check before commit** (B8, built 8 Oct, **passed Wil's test 12 Oct**): missing site,
  grid ref, doubles, unreadable or future dates, no recorder, no VC, listed before writing;
  default "Go back and fix".
- **Round 2 (10 Oct, tested 12 Oct):** a **count of 0** is pink in the cell, named by Check
  before commit and blocks that row (decision 8); "Showing: entry order" / "sorted by …
  (view only)" with **Back to entry order** (L21; the stored order never changes); sorting
  keeps the Copy context tick but copies nothing while sorted (Round 3); the "All my records"
  map leaves out records the counting switches exclude.
- **Quick Entry** (Observatum): the Commercial project is a pick-only list of existing
  projects, with the hint "New projects start in Data Entry" (decision 7). *12 Oct:* its
  popup is see-through (fault F50, small-fixes round).

## 9. Known constraints

**Pasted names that can't be matched** stay as text with no TVK; Check before commit lists
them (B4, B8).

**The standalone launcher points at a dev copy by default.** Easy to type into
the wrong database if the distinction is forgotten.

**Row insert below the new-row marker does not work** (B5). Committed, incomplete,
there is a workaround.

**Personal records are never committed from staging.** The established path is
spreadsheet → iRecord → Observatum; a Personal job is exported for iRecord and checked
back instead (§7b), so the sync-back cannot duplicate it.

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
