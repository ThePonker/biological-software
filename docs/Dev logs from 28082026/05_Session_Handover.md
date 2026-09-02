# Biological Software — Session Handover

## Date: 29 August 2026 (through Session 29)
## Supersedes: 27 August 2026 handover

---

## Executive Summary

Two working sessions since the last handover. The **Data Entry View is in production use**:
eleven Tabella workbooks (1,787 records) were migrated into staging, and Wil is now working
through them doing identifications and filling in grid refs, traps and parcels. Development
has been driven by that use — sorting, row insert/delete, the Traps card, VC derivation —
rather than by a plan.

Alongside that, a **CSV safety net** was built and the backup position was audited properly
before real data went in. The single most valuable find was a one-character bug that had
been suppressing 38% of common-name lookups.

The authoritative forward plan remains `24_Phase_Plan.md`, though it now understates what
Data Entry has become.

---

## Where Things Stand

| Area | State |
|------|-------|
| Version control | `main` current. Session 28–29 work committed. **Not merged to `stable`.** |
| Observatum — Data Entry | In production. 11 jobs / ~1,787 rows staged, nothing committed to `observations` yet. |
| Observatum — Observations tab | Delete Selected live; two latent crashes fixed. |
| Observatum — Insect Collection | Add Specimen rebuilt two-column with map + curatorial fields. |
| UKSI common names | Filter bug fixed; now uses UKSI's `preferred` flag. Behaviour change — watch it. |
| Codex / Examen / Curator / Munia / Atrium | Unchanged. |
| Tabella | Development **paused** by decision. |

---

## Data Protection (established Session 29)

| Layer | Covers | When |
|---|---|---|
| WAL + `synchronous=FULL` | every keystroke | continuous |
| `staging_backup.csv` (+prev) | all staging jobs | job close, 15 min, commit, app close |
| `observations_backup.csv` (+prev) | observations | after each commit |
| Observatum CSV backup-on-close | observations, specimens, recording_scheme, examen.db, munia.db | on close, if accepted |
| Pre-live `.db` snapshot | whole database | per Data Entry launch, keep 2, min 4h apart |
| OneDrive version history | everything in the folder | continuous |

CSV backups live at `C:\BiologicalSoftware_Backups\` — outside OneDrive by design.

**Gaps**: no restore has ever been tested; everything is on one machine.

---

## Immediate

- **Commit / merge to `stable`** once the current staging work is committed and proven.
- **Commit the staging jobs** as each workbook's identifications are finished.
- **Bulk curatorial editor** — the blocker for populating 2,549 specimens.
- **Fix the wizards' doubled import notes.**
- Eyeball the future-dated commercial record.
- Test a restore, from any layer.

---

## Winter Projects (unchanged in priority)

1. **Desktop Examen** (~5–8 days) — still first.
2. **Distributable Observatum** (~5–6 days).
3. Deferred: Codex display integration, mapping polish, gamification, web Examen.

Data Entry has effectively been delivered outside the plan; its remaining scope is the
clicker count-mode and repeat-key from `26_Data_Entry_Design.md`, neither yet built.

---

## Housekeeping Carried Forward

- **PowerShell writes must not add a BOM** — use
  `[IO.File]::WriteAllText($p, $text, (New-Object Text.UTF8Encoding $false))`.
- **Multi-line string anchors in PowerShell replacements fail unpredictably** on line-ending
  mismatch. Prefer single-line anchors, or a Python patch script for anything larger.
- **Read the whole method before editing it.** Several detours this session came from
  working off a grep hit rather than the surrounding code.
- **Avoid writing to `QSettings` from the command line** — the store a bare `QSettings()`
  reaches may or may not be the app's.
- Mixed line endings — `.gitattributes` if diffs get noisy.
- OneDrive locks `.git/objects` during `gc`.
