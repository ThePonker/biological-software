# Architecture

## Updated 8 October 2026

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
| **Lector** | "reader" | Biodiversity Heritage Library harvester (BHL API v3) gathering literature for species profiles; writes `data\lector.db`. Joined 7 Oct 2026 |
| **Munia** | "duties" | Capacity planner |
| **Atrium** | "entrance hall" | System-tray launcher |

Codex is infrastructure, not a product: nobody uses it directly, and its measure
of success is whether Observatum, Examen and Tabella always get accurate
conservation data.

---

## 2. Folder structure

```
Biological Software/
├── paths.py                 Suite-wide path registry — PERMANENT, never delete
├── run.bat                  Observatum launcher
├── CLAUDE.md                Instructions for Claude Code (rules, safety, where things are)
├── .claude/settings.json    Claude Code deny rules: no deletion, no destructive git
├── .git/  .gitattributes    main (development) / stable (field-season tool)
├── shared/                  UI-agnostic library — the analysis engine
│   ├── db_config.py         Per-app path resolution for standalone use
│   ├── backup_service.py    The single database-copy routine
│   ├── sqs_derivation.py    Pantheon's published SQS rule
│   ├── sex_summary.py       The one formatter for specimen sex (♂3 ♀4 +2)
│   ├── display_format.py    Dates dd/mm/yyyy and analysis-mode labels for screens and exports
│   ├── species_rank.py      Species search ranking (Data Entry and Add Specimen)
│   ├── repositories/        CodexRepository · PantheonRepository
│   └── services/            PantheonAnalysisService
├── Observatum/              Main app; src/ re-exports from shared/ via shims
├── DataEntry/               Drop-in package, 23 modules — see 09
├── Examen/                  Assessment tool — see 08
│   └── workbook_export.py   Multi-sheet Excel assessment workbook
├── Codex/                   Conservation manager GUI
├── Curator/  Munia/  Atrium/
├── Lector/                  BHL literature harvester; launcher in launchers\run_lector.bat
├── data/                    The databases, incl. lector.db (git-excluded, backup-protected)
├── scripts/                 Build, reset, import, patch and check scripts
│   ├── build_gb_basemap.py  Builds the GB basemap for Data Entry — keep (moved here 7 Oct)
│   └── _oneoff/             One-off data-changing scripts, git-ignored, archived later
├── launchers/               All .bat files
├── _archive/                Retired code, dated
└── docs/                    This set, plus the research documents

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
| `pantheon.db` | Ecology — biotopes, habitats, SATs, guilds, fidelity | `build_pantheon_db.py` **(missing)** |
| `vc_lookup.db` | Vice-county boundaries | Shapefile import |
| `examen.db` | Frozen assessments -- **retired 9 Oct 2026** (E13); nothing reads or writes it now. Export: `scripts/export_examen_snapshots.py` | none (still backed up) |
| `munia.db` | Project allocations, day logs | Munia |
| `gamification.db` | Achievements | Observatum |

### Which app reads what

| | observatum | codex | uksi | pantheon | vc_lookup |
|---|---|---|---|---|---|
| Observatum | read/write | read | read | read | read |
| Examen | read | read | read | read | — |
| Curator | read | — | read | — | — |
| Tabella | — | read | read | — | read |
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

### Pantheon update — CANNOT CURRENTLY BE PERFORMED

`build_pantheon_db.py` is missing (fault 5), lost in the same March restructure.
Pantheon has not been updated since 2017 v3.7.4, so this is not pressing.

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
4. Check the app; regenerate any Tabella workbook in use.

---

## 6. Version control

Local git at the project root. `main` for development, `stable` intended as the
field-season tool. **`stable` has not been updated since June 2026** — the whole
Data Entry build and four months of work sit on `main` only.

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
