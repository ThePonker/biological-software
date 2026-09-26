# Biological Software — Infrastructure Issues

## Updated 5 September 2026 (Session 32)
## Supersedes: 29 August consolidation + the Sessions 30–31 append block
## (both are folded in here — delete `10_Infrastructure_Issues_APPEND.md`)

> Open items carry an action. Closed items are kept in brief for the record.
> Itemised future work lives in `28_Development_Backlog.md`; this file is for
> infrastructure faults and the rules learned from them.

---

## Open Issues

### 4. UKSI.mdb path not in paths.py
The UKSI Access file lives outside the project (moved to save 781 MB of OneDrive sync); the
extractor hardcoded its location. **Action:** add `UKSI_MDB` to paths.py. Open since March.

### 5. `build_pantheon_db.py` missing
Not found during the March restructure. **Action:** reconstruct from the NERC download
instructions — backlog D3. Blocks the rebuild-all chain.

### 12. Game.bat orphaned
Points at `gamification/game_launcher.py`, which may not exist. **Action:** verify, delete.

### 30. Mixed line endings
Some files LF, some CRLF. `.gitattributes` added, but existing files are unconverted, so
multi-line string anchors still fail unpredictably. **Action:** prefer line-based or
single-line patching.

### 31. Future-dated commercial record
One row dated `2026-07-10`. **Action:** eyeball. Open since July.

### 38. Curatorial fields empty across the collection
Six columns empty across all 2,549 specimens. Session 29 added four to the Add Specimen
dialog, which serves new specimens only. **Action:** bulk editor — backlog A1.

### 39. `drawer_unit` column name
UI reads "Drawer Number". Column empty, no data risk. **Action:** backlog A4.

### 45. `stable` branch stale since June
The Data Entry build and four months of work sit on `main` only. **Action:** merge once the
staging jobs are committed and proven.

### 47. Single machine
OneDrive is sync, not backup: a deletion propagates. The largest remaining gap.
**Action:** external drive copy of `data\` and `C:\BiologicalSoftware_Backups\` — backlog
D2b, ten minutes.

### 52. `uksi_extractor.py` missing
Referenced by `Observatum/src/models/uksi.py` and `scripts/__init__.py`, but not present
anywhere — searched the whole C: drive, all of OneDrive, and git history. Most likely lost
in the March restructure, the same event that lost `build_pantheon_db.py` (item 5) and in
which `paths.py` was itself accidentally deleted for "looking like a temp utility script".

**Two build scripts are missing, not one.** `23_Rebuild_Procedures.md` documents a UKSI
rebuild that cannot be performed. Not urgent — `uksi.db` works and both it and the 781 MB
source are backed up outside OneDrive — but needed when NHM next release. `uksi.db` itself
is the specification. **Action:** backlog D3b.

### 54. Stored SQS does not follow Pantheon's published rule — INFORMATIONAL
Not a fault in this codebase, but it governs every SQI produced. Applying the published rule
to current Codex statuses agrees with the stored score for **85%** of Pantheon-sourced
invertebrate scores (re-measured Session 32; was 79.8% before this session's Codex fixes
improved the inputs). The remainder has three causes: genuine post-2017 review updates,
undocumented Pantheon overrides, and Pantheon not applying its own arithmetic (*Phengaris
arion* stored at 8 while Critically Endangered; *Anastrangalia sanguinolenta* NR + CR stored
at 8 where the rule gives 32).

**Decision: compute both, state the basis on every SQI, do not switch by default.**
Comparability with published SQIs is the point of a standard index. See
`35_SQS_Stored_vs_Derived.md` and backlog G13.

### 58. TVK bridge collisions — 1,847 species unbridged — **OPEN**
See the fix below; the clean recoveries are applied, the collisions are not. UKSI has
synonymised two Pantheon taxa into one current species; each carries its own SQS and ecology,
and `sqs_scores` is keyed on `tvk` alone so one would silently overwrite the other.

Rule decided: **incumbent wins, union the ecology.** Evidence: only 18 of 835 genuine merges
disagree on SQS, and merge incumbents differ from the published rule at 8% against 15%
overall — merged species are not a special population. **Action:** backlog J2.

Two cases want an entomologist's eye: the *Hylaeus annularis* group (three segregates stored
at 8, incumbent at 1 while carrying RDB 3) and — resolved — *Sigara striata* → *dorsalis*,
confirmed from NBN as a misapplied name rather than a true synonym.

### 59. SQS not fully stable across rebuilds — **OPEN, LOW**
A rebuild with no source change produced a net +1 (*Omonadus bifasciatus*). Order-dependence
in the Pantheon SQS import or the bridge, both resolving collisions by first-seen. Item 57
fixed the equivalent in `status_summary`. Would be removed as a side effect of D9.

### 60. England assessments routed to the GB threat track — **OPEN, LOW**
2014 England vascular plant entries carry GB abbreviations (`RedList_GB_post2001-EX`) despite
an England source, so they route to `threat_iucn_2001` rather than `red_list_england`. JNCC's
labelling, not a fault here. Vascular plants only.

### 61. Gap-filled SQS computed by the wrong rule — **OPEN, was D9**
`seed_codex.SQS_DEFAULTS` is not Pantheon's published rule. It scores RDB3 at 16 "per Fowles
original SQI" — a different index — and maps single `(track, value)` pairs taking the
maximum, where the published rule is a function of rarity **and** threat together
(*Nationally Rare with RDB K* is capped at 4 by the rule, 8 under max-of-pairs).

**525 of 816 gap-filled scores (64%) do not match the published rule**, and they sit in
`sqs_scores` indistinguishable from Pantheon's except by a `source` column nothing is obliged
to check.

**Decision (Wil, Session 32): compute live.** The 4,971 Pantheon scores are worth storing —
not as cached arithmetic but as a record of *what Pantheon published*, which is what makes an
SQI comparable. The gap-fill has no provenance and should be derived on demand from
`shared/sqs_derivation.py`. Removes item 59 as a side effect. **Action:** backlog D9.

### 62. Two different key-species percentages on one screen — **OPEN, SMALL**
The project table shows key ÷ total species (Glory Park 6.2%); the Overview card shows key ÷
species-in-Pantheon (8.0%). Same quantity, same screen, two answers, because the table comes
from `examen_data` and the card from `PantheonAnalysisService`. A report needs one.

### 63. Generated Overview sentence has stray punctuation — **OPEN, TRIVIAL**
"128 species recorded. across 4 visits." and "conservation value..". It is prose that would
be read straight into a report.

### 64. Parallel enrichment paths in Examen — **OPEN**
`site_analysis_view` imports `load_all_projects` from `examen_data` **and** takes
`analysis_service`. The project table and the detail tabs are populated from different
sources; item 62 is the visible symptom. The appendix has the same split — key rows from
`KeySpeciesEntry`, non-key rows from `examen_data`'s own enrichment.

Also in `examen_data`: `_classify_tier` duplicates `CodexRepository._classify` and has
already drifted (RDB3/RDBK scarce here, treated differently there), so Codex-full and
Pantheon-only modes classify by different rules — which makes mode comparison unsound. And
the SQI arithmetic `round(sqs_total / sqs_count * 100)` appears in **four** places rather
than calling `compute_sqi`. **Action:** backlog G1, rescoped.

---

## Closed Issues

| # | Issue | Resolution |
|---|---|---|
| 1 | Codex → Pantheon build order | Documented in `23_Rebuild_Procedures.md` |
| 2 | Examen depended on Observatum/src | `shared/` extracted |
| 3 | Manual Codex entries not portable | JSON storage + GUI editor |
| 6 | paths.py single point of failure | Permanent banner; run.bat checks |
| 7 | examen.db / munia.db unbacked | Backup-on-close (Session 26) |
| 8 | Concurrent database access | WAL + `PRAGMA query_only` on readers |
| 9–11 | Tabella generator / VBA / reset launchers | Fixed Sessions 22–23 |
| 13–16 | MUNIA_DB, shared library, rebuild docs, Atrium | Done |
| 17–21 | Species search, dates, edit lock, CSV backup, Tabella pending | Session 25 |
| 22, 23 | Tabella sheet protection / Settings path | **Cancelled** — Tabella paused |
| 24 | Data Entry View | **Built** — see `27_Data_Entry_State.md` |
| 25–28 | `update()`, `mark_synced()`, refresh double-count, iRecord IDs | Fixed |
| 32, 34–36 | BOMs, mojibake, `sorted(..., QMessageBox)`, Delete Selected | Session 28 |
| 37 | Common-name filter excluded 38% | See below |
| 40–44 | Date format, pre-live backups, staging CSV, header guard | Sessions 28–29 |
| 46 | No tested restore | ✅ Session 31 — see below |
| 48 | Unsafe database copies throughout | All copies now `conn.backup()` |
| 49 | Restore button had never worked | `Path + str`; replaced with a script |
| 50 | Pre-live snapshots 3.9 GB | Retired; rolling 2 |
| 51 | `pantheon.db` unprotected | Backed up outside OneDrive |
| 53 | Import wizard doubled every warning | Mutating write-back removed |
| 55 | Obsolete databases in `data/` | 568 MB cleared |
| **56** | **Priority track collapse** | **✅ Session 32 — see below** |
| **57** | **Collapse ties by row order** | **✅ Session 32 — see below** |
| **58a** | **Bridge never used `uksi.synonyms`** | **✅ Session 32 — 1,153 recovered** |
| **65** | **Species Database view stale 8-track** | **✅ Session 32 — see below** |
| **66** | **Feeding guild counts split by casing** | **✅ Session 32** |
| **67** | **Conservation tab invented Section 41** | **✅ Session 32 — see below** |
| **68** | **Appendix labelled all priority "S41/BAP"** | **✅ Session 32** |
| **69** | **Key species not jurisdiction-aware** | **✅ Session 32 — see below** |

### 37 in detail — UKSI common-name filter
A GLOB class ending `...ŵŷwy`; the bare ASCII `w` and `y` excluded **7,997 of 20,897** common
names instead of the 22 accented ones intended. Replaced with `ORDER BY preferred DESC`
against UKSI's own flag.

### 46 in detail — restore tested (Session 31)
A `current/observatum.db` copy passed `integrity_check` with all counts intact
(24,034 / 2,552 / 110,510 / 2,373), opened in Observatum via Settings → Databases → Change,
and the path was restored. Six backup layers became tested rather than assumed.
`scripts/restore_database.py` runs with the app closed and verifies before and after.

### 56 in detail — the priority collapse (Session 32)
`key = (track, detail or "")` with all five jurisdictions mapping to `detail = None`. They
competed for one slot per species, all scoring the default 10, winner by row order.
**2,303 facts missing**; UK BAP at 12% of true coverage; NI Priority intact only because it
sorted first.

Fixed by writing the jurisdiction to **both** `status_value` and `status_detail` — value
unchanged so nothing downstream breaks, detail making the primary key discriminate.
Verified: priority 2,928 → 5,231 rows, all five jurisdictions reconciling exactly, key
species and SQS unchanged.

### 57 in detail — the date tiebreak (Session 32)
```python
if (key not in best
        or (prio, date_d or "") > (best[key][6], best[key][4] or "")):
```
Precedence first, date second. Fixes 11 vascular plants (2014 England EX/EW → 2021 GB RE)
and correctly leaves *Cercyon nigriceps* at the specific `Nb` rather than the newer generic
`Notable`, because `Notable-B` (40) outranks `Notable` (30) before the date is consulted.

### 65 in detail — the Species Database view (Session 32)
`_display_codex_status` read the pre-April 8-track attribute names. All but one return `""`
and were skipped silently — the panel showed **nothing for any species**. `legal_protection`
does exist and is a **list**, so it was truthy, reached `QLabel(val)` and raised. Blank or
crashing since April; found only because a legally protected species was selected.

### 67 in detail — the invented Section 41 (Session 32)
`_parse_status` reverse-engineered codes from `short_status`, which for a priority species is
the literal `"Priority"` — matching no token, falling through to a tier fallback that stamped
**S41** on all of them. Glory Park (Northamptonshire) reported "Section 41: 4"; its four
priority species are on the Scottish and NI lists and **none is on Section 41**.

**Every other fault this year lost or mis-chose facts. This one manufactured them** — and it
is the only one that could have put a false statement in a client report.

Fixed by carrying structured tracks on `KeySpeciesEntry` and reading them directly.

### 69 in detail — jurisdiction-aware key species (Session 32)
`_classify` conferred Priority for any priority listing or legal protection regardless of
where the site was, so English sites gained key species on Scottish and NI listings —
including *Osmia bicornis*, the Red Mason Bee.

Section 41 requires a list of species of principal importance **in England**, and the section
40 duty points public bodies at that list; reviewed English EcIAs scope S41 and never cite
the SBL; JNCC's UK BAP invertebrate list is published with per-country Y/N columns. Rarity
and threat are GB-wide and untouched. Every designation is still stored and displayed — it
simply does not confer key status outside its jurisdiction.

Glory Park 12 → **8**; Bicester 42 → 31; Derby 10 → 5; Fermyn Hall unchanged at 8.
Default is England; `jurisdiction=` parameter threads through both analysis modes. **No UI
control yet.**

---

## Rules Learned

### Schema Change Rule (Session 22)
Adding columns to multi-table reset scripts needs a **per-table audit** — extract each
CREATE TABLE independently. A whole-file search once reported "ALL OK" when `superfamily` was
present in one definition and missing from two others.

### VBA Encoding Rule (Session 23)
VBA injected via `AddFromString` must be pure ASCII with explicit `\r\n`.

### PowerShell Encoding Rule (Session 28)
`-Encoding UTF8` writes a **BOM** in Windows PowerShell 5.1. Use
`[IO.File]::WriteAllText($path, $text, (New-Object Text.UTF8Encoding $false))`.

### PowerShell one-liners (Session 32)
In `python -c` under PowerShell, use **only single quotes inside**, and avoid `*` in SQL —
escaped double quotes and asterisks are intercepted by the shell before Python sees them.
Use `COUNT(1)`, and build a needed quote with `chr(39)`. Cost three failed commands in one
session.

### Editing Rules (Sessions 29, 32)
- **Read the whole method before editing it.**
- **Multi-line anchors fail unpredictably** on CRLF/LF mismatch. Prefer single-line anchors
  or **line-based patching** (splitlines, locate markers, replace ranges, rejoin with the
  original ending).
- **Count your anchors.** A patch that anchored on `_classify(status)` refused to write
  because there are four call sites, and the batch line is a *substring* of the single line,
  so counting one inside the other double-counted. The refusal was correct behaviour.
- **Compiling is not importing.** A patch placed module constants immediately before the
  function that used them — at the *bottom* of the file — while method default arguments
  referencing them are in the class above. It compiled cleanly and raised `NameError` on
  import, because defaults evaluate when the class body runs. **Patch scripts must import
  the module, not just `py_compile` it.**
- **Check the schema before writing the query.** Two diagnostics in one session guessed
  column names and failed; `pantheon.db.conservation_status` has `reporting_category`, not
  `category`. `PRAGMA table_info` first.
- **Import the rule, do not restate it.** A diagnostic imported `seed_codex.SQS_DEFAULTS` as
  "the published rule" and produced a confidently wrong 52% / 408 result. It is the *gap-fill*
  table, on a partly different scale. The right module was `shared/sqs_derivation.py`.

### Data Rules (Session 29)
- **Derive, don't copy, anything with a spatial dependency.** VC always from the grid ref.
- **Prune by filename, not mtime, inside OneDrive.** Sync rewrites timestamps.

### Never-executed code paths — a standing risk
**Seven found this year**, all of which would have failed on first real use: `mark_synced()`
column mismatch; `sorted(..., QMessageBox)`; the missing `set_selected_count` branch;
`_restore_database`'s `Path + str`; `species_database_view._display_codex_status`; and two
more claimed by the September code review (`entry_grid._header_menu`,
`observation_filter_mixin`) that remain unverified.

The pattern: code written alongside working code, never exercised, never found. **Action:**
periodic sweep of rarely-used handlers, dialogs and repository methods — backlog D5.

### Duplicated rules drift — eight instances
`examen_data.py`'s Codex track mirror · `SRC_SETTING_KEYS` · the import-notes combining ·
the two SQS sources · two `sqs_derivation.py` copies (already drifted) · four `theme.py`
files · three grid-ref implementations · and (Session 32) `status_detail` applied to
`legal_protection` but not `priority`.

The last is a **variant**: written once, applied to one track, forgotten for the other, in
the same dictionary in the same file. **When a design says two things go in the same place,
verify both actually got there.**

Grid-ref maths is the one that matters most — a subtle disagreement between three
implementations produces *wrong vice-counties*, not a crash, and VC is derived rather than
typed so nothing downstream would question it.

### Reproducibility must be tested, not assumed (Session 32)
Items 57 and 59 are both order-dependence in code that looked correct. Reports are stamped
with a Codex version on the premise that the same version reproduces the same figures. A
build-twice-and-compare check would catch the whole class in a minute and would have caught
57 in April — the same move that turned six backup layers from hypotheses into tested paths.
**Action:** backlog J5.
