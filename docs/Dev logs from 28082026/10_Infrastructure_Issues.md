# Biological Software — Infrastructure Issues

## Updated 29 August 2026 (Session 29)
## Supersedes: 25 March 2026 original + July and August append blocks

> Consolidated. Closed items are kept in brief for the record; open items carry an action.
> Itemised future work now lives in `28_Development_Backlog.md` — this file is for
> infrastructure faults, and for the rules learned from them.

---

## Open Issues

### 4. UKSI.mdb path not in paths.py
The UKSI Access file lives outside the project (moved to save 781 MB of OneDrive sync);
the extractor hardcodes its location. **Action:** add `UKSI_MDB` to paths.py. Open since March.

### 5. `build_pantheon_db.py` location unknown
Was at project root pre-restructure, not found during migration. **Action:** search backups;
if lost, reconstruct from the NERC download instructions. Blocks the rebuild-all chain.

### 12. Game.bat orphaned
Points at `gamification/game_launcher.py`, which may not exist. **Action:** verify, delete
if absent.

### 30. Mixed line endings
Some files LF, some CRLF. Confuses Git diffs and — more practically — makes multi-line
string replacements fail unpredictably during editing sessions. **Action:** `.gitattributes`.

### 31. Future-dated commercial record
One row dated `2026-07-10`. Typo or scheduled survey. **Action:** eyeball. Open since July.

### 38. Curatorial fields empty across the collection
`preparation_type`, `storage_location`, `drawer_unit`, `condition`, `label_data`,
`specimen_code` are empty across all 2,549 specimens; Curator does not write them. Session 29
added four to the Add Specimen dialog, which serves new specimens only. **Action:** bulk
curatorial editor — backlog A1.

### 39. `drawer_unit` column name
UI reads "Drawer Number"; column is `drawer_unit`. Rename touches four files plus reset
scripts. Column empty, no data risk. **Action:** backlog A4.

### 43b. Wizards double-append import notes
`[Warning: Non-standard Sex: adult] | [Warning: Non-standard Sex: adult]` — the combine
pattern appends twice. 175 rows affected. **Action:** backlog C1.

### 45. `stable` branch stale since June — **NEW**
The entire Data Entry build and both August sessions exist only on `main`. The branching
discipline was set up precisely so `stable` could be the field-season tool. **Action:** merge
once the staging jobs are committed and proven.

### 46. No tested restore — **NEW**
Six backup layers exist; none has ever been restored from. **Action:** backlog D1.

### 47. Single machine — **NEW**
Everything lives on one computer with OneDrive underneath. OneDrive is sync, not backup: a
deletion propagates. The offline server would close this. **Action:** backlog D2.

---

## Closed Issues (for the record)

| # | Issue | Resolution |
|---|---|---|
| 1 | Codex → Pantheon build order | Documented in `23_Rebuild_Procedures.md` |
| 2 | Examen depended on Observatum/src | `shared/` extracted |
| 3 | Manual Codex entries not portable | JSON storage + GUI editor |
| 6 | paths.py single point of failure | Permanent banner; run.bat checks |
| 7 | examen.db / munia.db unbacked | Added to backup-on-close (Session 26) |
| 8 | Concurrent database access | WAL + `PRAGMA query_only` on readers |
| 9 | Tabella generator location | Moved into `Tabella/` |
| 10 | Tabella VBA macro missing | `vba_source.py` written |
| 11 | Broken reset launchers (6) | Repaired |
| 13 | MUNIA_DB not in paths.py | Added (Session 26) |
| 14 | Shared library | Extracted |
| 15 | Rebuild procedures | Documented |
| 16 | Atrium redesign | Complete |
| 17 | Species search | QCompleter → QListWidget popup |
| 18 | Specimen date migration | 2,454 dates → ISO |
| 19 | Observation edit lock | Narrowed to `irecord_id` |
| 20 | CSV backup conditional | Always offered |
| 21 | Tabella pending records | Complete (Tabella now paused) |
| 22, 23 | Tabella sheet protection / Settings path | **Cancelled** — Tabella paused |
| 24 | Data Entry View | **Built** — see `27_Data_Entry_State.md` |
| 25 | `update()` signature mismatch | Direct SQL in the mixin |
| 26 | `mark_synced()` column mismatch | `synced_at` → `last_synced` |
| 27 | `refresh_records.py` double-count | TVK column + `--skip` |
| 28 | iRecord `irecord_id` nulled | Fixed; 180 IDs recovered |
| 29 | Phase 0 hygiene | Done |
| 32 | 9 UTF-8 BOMs | Stripped (Session 28) |
| 34 | Observations toolbar mojibake | Repaired (Session 28) |
| 35 | `sorted(..., QMessageBox)` | Second argument removed |
| 36 | Delete Selected | Delivered |
| 37 | Common-name filter excluded 38% | See below — the most consequential fix to date |
| 40 | Hardcoded ISO date in record detail | Reads `general/date_format` |
| 41 | Pre-live backups: 3.9 GB, 35 files | Keep 2, 4-hour minimum |
| 42 | Staging had no CSV coverage | `DataEntry/csv_backup.py` |
| 44 | Header state vs column changes | Column-count guard |

### 37 in detail — UKSI common-name filter
`_get_preferred_common_name()` filtered on a GLOB class ending `...ŵŷwy`. The bare ASCII
`w` and `y` excluded **7,997 of 20,897** common names — every name containing a w or a y —
instead of the 22 accented ones intended; excluded names fell through to an arbitrary
`LIMIT 1`. The filter was then found obsolete (extractor v5 already filters to English, and
the 22 "accented" names are legitimate English eponyms). Replaced with
`ORDER BY preferred DESC` against UKSI's own flag, which is populated for every one of the
16,351 TVKs. Accepted consequence: UKSI's canonical name is occasionally not the familiar
one (*Lumbricus terrestris* → "Lob").

---

## Rules Learned

### Schema Change Rule (Session 22)
When adding columns to multi-table reset scripts, run a **per-table audit** — extract each
CREATE TABLE independently and verify the column within that block. A whole-file search once
reported "ALL OK" when `superfamily` was present in one table's definition and missing from
two others.

### VBA Encoding Rule (Session 23)
VBA injected via `AddFromString` must be pure ASCII with explicit `\r\n`. No em-dashes, no
`Attribute VB_Name`. Store as concatenated string literals, not triple-quoted blocks.

### PowerShell Encoding Rule (Session 28)
`Set-Content` / `Add-Content` / `Out-File` with `-Encoding UTF8` write a **BOM** in Windows
PowerShell 5.1, which breaks direct-text parsing of Python source. Always:

```powershell
[IO.File]::WriteAllText($path, $text, (New-Object Text.UTF8Encoding $false))
```

Related: `$text.Replace([char]0xE2 + [char]0x2013, [char]0x25B4)` resolves to the
single-`char` overload and throws. Build multi-character patterns as `[string]` variables.

### Editing Rules (Session 29)
- **Multi-line string anchors fail unpredictably** on CRLF/LF mismatch. Prefer single-line
  anchors, or a Python patch script for anything larger. A failed replacement is silent —
  always verify with `Select-String` afterwards, not just a syntax check.
- **Read the whole method before editing it.** Several detours this session came from working
  off a grep hit rather than the surrounding code — including reaching for the wrong settings
  keys when `DEFAULT_RECORDER` already existed.
- **Check imports before using a name.** A fix that referenced `QSettings` in a file that
  didn't import it would have crashed on first use.
- **Don't write to `QSettings` from the command line.** A bare `QSettings()` may not reach
  the store the app uses, and may reach something else.

### Data Rules (Session 29)
- **Derive, don't copy, anything with a spatial dependency.** VC must always come from the
  grid ref, never be carried down from the row above — a different ref can mean a different
  county.
- **Prune by filename, not mtime, inside OneDrive.** Sync rewrites modification times, so
  timestamps there are not a reliable record of when a file was made.
