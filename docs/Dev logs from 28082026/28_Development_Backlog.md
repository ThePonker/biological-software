# Development Backlog

## Created 29 August 2026 (Session 29)
## Purpose

A single itemised list of everything outstanding, so that requests raised mid-session stop
getting lost between chats. `24_Phase_Plan.md` holds the strategic sequence and the big
winter builds; this file holds everything, including the small things.

Each item has a size estimate and a trigger — the thing that makes it worth doing now
rather than later.

---

## A. Insect Collection

### A1. Bulk curatorial editor — **HIGH**
**Size:** 0.5–1 day
**Trigger:** blocking. Six curatorial columns are empty across all 2,549 specimens.

Select many specimens and set Preparation, Condition, Storage Location and Drawer Number
across them in one action, without touching biological data. Session 29 added these fields
to the Add Specimen dialog so new specimens capture properly, but the existing collection
cannot realistically be backfilled one record at a time.

Design notes: filter to a selection (by family, order, date range or the existing filter
bar), show what will change, confirm with a count. Should refuse to touch species, date,
grid ref or determiner.

### A2. Edit curatorial fields on an existing specimen — **HIGH**
**Size:** small, may already be covered
**Trigger:** raised directly — "I have no way of adding this information at the moment."

The Add Specimen dialog doubles as the edit dialog and now carries the curatorial fields, so
this may be closed by Session 29's work. **Verify** by editing an existing specimen and
confirming the values save and reload. If the Insect Collection tab has a separate detail or
edit path that bypasses the dialog, that needs the same fields.

### A3. `label_data` composition
**Size:** 0.5 day
**Trigger:** none pressing; deferred by decision.

Compose specimen label text from the record rather than typing it. Format undecided —
needs a sample of Wil's actual labels to design against.

### A4. `drawer_unit` → `drawer_number` rename
**Size:** 0.5 day
**Trigger:** cosmetic; do it alongside another schema change.

UI label already reads "Drawer Number". Renaming the column touches `specimen.py`,
`specimen_repository.py`, `specimen_table_model.py` and the reset scripts. Column is empty,
so no data risk. Per-table audit rule applies.

### A5. `specimen_code` — **CLOSED, will not do**
Decision taken: no retro-labelling of the collection. Column retained but unused.

---

## B. Data Entry

### B1. Staging layer on the distribution map — **MEDIUM**
**Size:** 0.5 day
**Trigger:** raised directly. Would show this season's uncommitted work on the map.

The Records legend already has Personal / Commercial / Insect Collection / Recording scheme
toggles. Add a fifth for staged rows, sourced from `entry_staging` rather than
`observations`, in a distinct colour.

### B2. Clicker count-mode
**Size:** 0.5 day
**Trigger:** trap-sample processing under the microscope.

From `26_Data_Entry_Design.md` §3.3 — a configurable keystroke increments Qty, a second
decrements, with a large glanceable counter. Works from spacebar, an on-screen button, or a
USB foot pedal programmed to that keystroke. Not yet built.

### B3. Repeat key for sex splits
**Size:** small
**Trigger:** same-species sex splits (3♂ then 2♀) are common in spiders and Diptera.

Clone the just-entered row and land on Sex. From `26_Data_Entry_Design.md` §3.1.

### B4. Reject `?` and other placeholder TVKs on load
**Size:** trivial
**Trigger:** two rows slipped through the workbook migration with `species_tvk = '?'`.

`load_workbook_to_staging.py` treats any non-empty string as a valid TVK, so the "no TVK"
count under-reported. Treat `?`, `#N/A` and similar as absent.

### B5. Species-name paste resolution
**Size:** 0.5 day
**Trigger:** latent. Pasting names from outside the app stores them as text with no TVK,
and `commit_job` commits them anyway with only a count as warning.

Either resolve pasted names against UKSI on the way in, or make a missing TVK an eligibility
failure at commit. Low urgency now the workbooks are loaded with their TVKs intact, but the
hole is still open.

---

## C. Import wizards

### C1. Doubled import notes — **MEDIUM**
**Size:** small
**Trigger:** visible in the data.

Warnings appear twice: `[Warning: Non-standard Sex: adult] | [Warning: Non-standard Sex: adult]`.
The import-notes combine pattern appends the same note twice. Affects 175 rows so far.

### C2. Re-enrich conservation columns from live Codex — **MEDIUM**
**Size:** 0.5–1 day
**Trigger:** Phase 1 item 6, still open. Reinforced by the workbook migration — generated
workbooks bake in Codex data that may predate the April 11-track widening.

### C3. Route wizards through `_get_preferred_common_name()`
**Size:** small
**Trigger:** now safe to do, after the Session 28 fix to that method.

---

## D. Infrastructure & data integrity

### D1. Test a restore — **HIGH**
**Size:** 1 hour
**Trigger:** no restore has ever been tested from any backup layer.

Six layers now exist. None has been proven. Restore a pre-live `.db` snapshot to a scratch
location and open it; re-import a staging CSV into a scratch database.

### D2. Reconfigure the offline server — **MEDIUM**
**Size:** unknown; documentation lost
**Trigger:** everything is currently on one machine. OneDrive is sync, not backup.

Old desktop machine, currently offline, setup documentation lost. Likely a rebuild rather
than a recovery.

### D3. Reconstruct `build_pantheon_db.py` + rebuild-all chain
**Size:** ~1 day
**Trigger:** unverifiable link in the rebuild chain. Open since March.

### D4. `.gitattributes` for line endings
**Size:** trivial
**Trigger:** every `git add` prints CRLF warnings.

### D5. Sweep for never-executed code paths — **MEDIUM**
**Size:** 0.5 day
**Trigger:** three found so far (`mark_synced` column mismatch, `sorted(..., QMessageBox)`,
the missing `set_selected_count` branch). All would have crashed on first real use.

Grep for rarely-used toolbar actions, dialogs and repository methods with no callers.

### D6. Eyeball the future-dated commercial record
**Size:** minutes
**Trigger:** open since July. One row dated `2026-07-10`.

---

## E. Documentation

### E1. Fill in Session 27 — **MEDIUM**
The Data Entry build itself is only partially documented, reconstructed from code rather
than from a log. Needs Wil's own notes.

### E2. Reconcile `07_Codex_Design_Spec.md` figures
Contents table shows status_summary 21,112 / sqs_scores 15,663 against the clean baseline
23,123 / 6,082. Carried over unreconciled since July.

---

## F. Paused / closed

- **Tabella** — development paused Aug 2026. Sheet protection and the Active Record Books
  path in Settings are no longer being pursued; Data Entry supersedes the workflow.
- **`specimen_code`** — will not be used.
- **Local Site Name** — removed from the Add Specimen dialog; column retained because 16
  files reference it and iRecord sync protects it.
