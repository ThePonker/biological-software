### Session 30 (2 Sept 2026) — Backup system rebuilt

Prompted by Wil asking whether he had over-complicated his backups. The layers were sound;
three of them copied the live 114 MB `observatum.db` with `shutil.copy2` while it was open in
WAL mode, while `DatabaseManager.backup_main()` did it correctly with SQLite's online backup
API and had no callers.

**`shared/backup_service.py`** written — one routine, `current`/`previous` rotation, fixed
footprint, `C:\BiologicalSoftware_Backups\` outside OneDrive. Two tiers: working databases
on close and before every commit, reference databases on demand. A failed pre-commit backup
blocks the commit.

The `embed.py` pre-live snapshot was retired (3.9 GB / 35 files at discovery, pruned to two).
`pantheon.db` — protected by nothing, and unrebuildable since its build script was lost —
was backed up for the first time.

Also: import wizard doubled every warning (`row.import_notes` mutated, then re-combined
downstream); stray duplicated `return` in `observation_stats_service`; vulture pass across
the suite returned 26 findings, almost all trivial.

### Session 31 (4 Sept 2026) — Restore tested; Examen researched

**Restore proven end to end** for the first time. A backup copy passed `integrity_check`
with all record counts intact, opened correctly in Observatum via Settings → Databases, and
the path was restored. Six backup layers went from hypotheses to tested paths.

The **Restore button** was found to have never worked — it built its safety path as
`Path + str`, raising `TypeError` before touching anything. The fourth never-executed code
path found this year. Replaced with `scripts/restore_database.py`, which runs with the app
closed and verifies before and after. The **Backup button** now calls `backup_main()`.

**568 MB of obsolete databases removed** from `data/`, including a July dev copy that the
standalone Data Entry launcher would have opened by default.

**⚠️ `uksi_extractor.py` found to be missing** — searched the whole C: drive, OneDrive and
git history. Lost, most likely in the March restructure alongside `build_pantheon_db.py`.
Two build scripts missing, not one. `UKSI.mdb` (781 MB) backed up outside OneDrive in
consequence.

**Examen research — six documents, no code.** Reading the archive, Wil's reports, the wider
literature and Pantheon itself. Findings: the archive is sound and only `examen_data.py` is
stale; the reports use two frameworks (Pantheon, and saproxylic SQI + IEC) of which only one
is implemented; `sat_thresholds.json` exists and matches Pantheon's own output; compartment
analysis is standard practice; and **one stored SQS in five does not follow Pantheon's own
published scoring rule**.

`shared/sqs_derivation.py` implements the published rule against current Codex statuses,
with `scripts/check_sqs_derivation.py` as a diagnostic. Decision: compute both, state the
basis, do not switch by default — comparability with the literature matters.

`Examen/` restored from the archive. Not yet run.
