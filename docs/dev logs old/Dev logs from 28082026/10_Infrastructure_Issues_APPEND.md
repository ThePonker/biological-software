## Sessions 30–31 Additions (4 September 2026)

> Continues from item 46. Items 45–47 were filed in the 29 August block; 45 and 46 are
> updated below rather than repeated.

---

### 45. `stable` branch stale since June — STILL OPEN
Unchanged. The Data Entry build, both August sessions and both September sessions sit on
`main` only. **Action:** merge once the staging jobs are committed and proven.

### 46. No tested restore — ✅ CLOSED (Session 31)
Tested 4 Sept. A `current/observatum.db` copy passed `PRAGMA integrity_check` with all
record counts intact (24,034 / 2,552 / 110,510 / 2,373), opened correctly in Observatum via
Settings → Databases → Change, and the path was restored afterwards. Six backup layers are
now tested rather than assumed.

### 47. Single machine — STILL OPEN
Unchanged and now the largest remaining gap. OneDrive is sync, not backup. **Action:**
external drive copy of `data\` and `C:\BiologicalSoftware_Backups\`; the offline server
later.

---

### 48. Unsafe database copies throughout — ✅ FIXED (Session 30–31)

`observatum.db` runs in WAL mode. A raw `shutil.copy2` of the main file can capture a
database missing recent commits, or whose main file and `-wal` are out of step. Three
mechanisms did exactly that:

- `DataEntry/embed.py` pre-live snapshot
- `database_panel._backup_database`
- `database_panel._restore_database` (including its own safety copy)

Meanwhile `DatabaseManager.backup_main()` used SQLite's online backup API correctly and had
**no callers**.

All database copies now go through `conn.backup()`. `shared/backup_service.py` is the single
routine; the Backup button calls `backup_main()`; the pre-live snapshot is retired.

### 49. Restore button had never worked — ✅ FIXED (Session 31)

```python
safety = self.db_manager.main_db_path + ".pre_restore"
```

`main_db_path` returns a `Path`. `Path + str` raises `TypeError`, so the restore failed at
the safety copy before touching anything. **The fourth never-executed code path found this
year**, after `mark_synced()`, `sorted(..., QMessageBox)` and the missing
`set_selected_count` branch.

Replaced with a dialog directing the user to `scripts/restore_database.py`, which runs with
Observatum closed: refuses if the database is in use, verifies the chosen backup with
`integrity_check` **before** touching anything, takes a safety copy via the backup API,
clears stale `-wal`/`-shm`, copies in, and verifies the result.

### 50. Pre-live snapshots: 3.9 GB — ✅ FIXED (Session 30)
35 files at 114 MB each, all inside OneDrive, no pruning. Retired in favour of the
before-commit backup, which fires at the moment that matters. Cleared to two.

### 51. `pantheon.db` unprotected and unrebuildable — ✅ MITIGATED (Session 30)
Backed up outside OneDrive. The build script remains missing (item 5).

### 52. `uksi_extractor.py` missing — **NEW, OPEN**

Referenced by `Observatum/src/models/uksi.py` (*"from UKSI.mdb via uksi_extractor.py"*) and
by `scripts/__init__.py` (*"uksi_extractor.py: Converts UKSI.mdb to uksi.db"*), but not
present anywhere. Searched: the whole C: drive including hidden files, all of OneDrive, and
git history. Not found.

Most likely lost in the March restructure, the same event that lost `build_pantheon_db.py`
(item 5) — and the same event in which `paths.py` was itself accidentally deleted for
"looking like a temp utility script".

**Consequence:** `23_Rebuild_Procedures.md` documents a UKSI rebuild that cannot be
performed. **Two build scripts are now missing, not one.**

Not urgent — `uksi.db` works, and both it and the 781 MB `UKSI.mdb` source are backed up
outside OneDrive — but a rewrite will be needed when NHM next release. The v5 extractor
handled `sort_code`/`sort_order` from `ORGANISM_MASTER`, the `LANGUAGE='en'` filter and the
preferred flag; `uksi.db` itself is the specification.

### 53. Import wizard doubled every warning — ✅ FIXED (Session 30)

The insert path built `notes_parts` and **wrote back** to `row.import_notes`, then
`_row_to_observation_dict` called `_combine_import_notes(row)`, which read that value into
`parts` and appended the same warning again:

`[Warning: Non-standard Sex: adult] | [Warning: Non-standard Sex: adult]`

The duplicate block was removed; `_combine_import_notes` is non-mutating and correct. 175
existing rows retain doubled notes — cosmetic, a one-line UPDATE whenever it matters.

### 54. Stored SQS does not follow Pantheon's published rule — **NEW, INFORMATIONAL**

Not a fault in this codebase, but it governs every SQI figure produced.

Pantheon publishes its scoring rule (0/1/4/8/16/32 by rarity × threat). Applying that rule
to current Codex statuses agrees with the stored score for **79.8%** of species. The
remaining 20% has three causes:

1. **Genuine review updates** — 172 species stored as 8 that current statuses put at 4
2. **Undocumented overrides** — 274 Notable species stored as 1 where the rule gives 4
3. **Pantheon not applying its own rule** — 89 species with `NR` + `Endangered` stored as 8
   where the rule says 16; Data Deficient stored as both 8 and 16

`shared/sqs_derivation.py` implements the published rule; `scripts/check_sqs_derivation.py`
is the diagnostic. **Decision: compute both, state the basis on every SQI, do not switch by
default.** Comparability with published SQIs and site rankings is the point of a standard
index. Full analysis in `35_SQS_Stored_vs_Derived.md`.

### 55. Obsolete databases in `data/` — ✅ CLEARED (Session 31)
568 MB removed: four superseded snapshots plus `observatum_dev_20260706_220900.db`. The last
was a hazard — `python -m DataEntry` opens the newest `observatum_dev_*.db` by default, so a
standalone launch would have written into a two-month-old database.

---

## Rules Added

### Never-executed code paths — a standing risk
Four found this year, all of which would have failed on first real use:
`mark_synced()` column mismatch, `sorted(..., QMessageBox)`, the missing
`set_selected_count` branch, and `_restore_database`'s `Path + str`.

The pattern: code written alongside working code, never exercised, and therefore never
found. Worth a periodic sweep of rarely-used handlers, dialogs and repository methods.

### Duplicated rules drift — four instances now
`examen_data.py`'s Codex track mirror, `SRC_SETTING_KEYS` in the info panel, the
import-notes combining, and the two SQS sources. When something must be "kept in sync", it
will not be. Move it to one place instead.
