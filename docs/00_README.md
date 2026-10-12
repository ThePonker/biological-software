# Biological Software — Documentation

## Set v2, started 6 October 2026; brought up to date 12 October 2026
## Replaces the 01–37 series, which had drifted into three append files and
## several documents describing states that lasted hours.

---

## The set (maintained)

| File | Answers |
|---|---|
| `00_README.md` | What is here, and how to keep it honest |
| `01_Architecture.md` | What exists, where it lives, which database holds what; startup, the map, Lector, one home per rule |
| `02_Current_State.md` | Where everything stands today, with figures, startup timings and what Wil has tested |
| `02b_History.md` | One paragraph per session, newest first (split from `02` on 12 Oct) |
| `03_Backlog.md` | The working list: how we work, the next round, the big jobs, decisions, reminders — **check before starting a session** |
| `03b_Backlog_Observatum.md` | Area lists: Insect Collection, Data Entry, imports, infrastructure, mapping, contributed records, Recording Scheme |
| `03c_Backlog_Examen_Codex.md` | Area lists: Examen, Codex data, species profiles, code hygiene, closed decisions |
| `04_Roadmap.md` | Strategy, phases, sequence, estimates, risks |
| `05_Rules.md` | How to work on this codebase without repeating old mistakes |
| `06_Faults.md` | Open faults, and the ones closed since 10 Oct |
| `06b_Faults_Closed.md`, `06c_Faults_Closed_Earlier.md` | Closed faults, for the record |
| `07_Codex.md` | Codex — the conservation authority |
| `08_Examen.md` | Examen — the assemblage assessment tool |
| `09_Data_Entry.md` | Data Entry — the recording grid |
| `Lector_User_Manual.md` | Lector: install, every screen, recipes, console, files, troubleshooting, the automated and manual tests (project note 46) |

`03`, `06` and `02` were split on 12 Oct because each had passed ~600 lines (866, 969,
461 + history). Nothing was dropped; the split points are stated at the top of each file.

## Drafts (design notes awaiting a build; decisions recorded at the top of each)

`drafts/map_layers_survey.md` (map background layers; Q6, Q34–Q40) ·
`drafts/batch_maps_design.md` (batch maps screen; Q41–Q50) ·
`drafts/photos_design_update.md` (photos A8/A8b; Q5, Q13–Q22, Q71) ·
`drafts/map_layers_now_oxon.png` (an illustration for the survey).

Q numbers refer to project note `claude/45_Open_Questions_20261012.md`, whose end holds
Wil's answers of 12 Oct. They are applied in `03_Backlog.md`.

## Test material

`tests/manual_import_files/` — four small made-up CSVs and a README for Wil's manual tests
of the three import wizards (Round 9 tests 30, 31, 34, 35). Every row is marked "TEST".

## Historical (accurate on their day, not maintained)

`38_Report_Survey.md` — the specification for the report layer, drawn from eleven
published reports. Read it before touching the report contents (E3/E7 follow-ups).
`39_Research_Notes.md` (8 Oct research: SQI bands, Welsh S7, saproxylic sources) ·
`40_Code_Sweep_20261008.md` (never-executed paths, write whitelists, silent errors; open
items carried into `03` and `06`) · `41_Groundwork_Notes_20261009.md` (import repair plan,
C4 design, saproxylic groundwork, photos and geo groundwork). Their open items are in `03`
("Gathered 12 Oct") or `06`; the rest is history.

## Retained as background reading, not maintained

`25_Data_Entry_Research.md` (MapMate / Recorder 6 study) ·
`32_Examen_Requirements.md` · `32b_Examen_Requirements_Addendum.md` ·
`33_Pantheon_Deep_Dive.md` · `34_Musgrove_Paper_Analysis.md` ·
`35_SQS_Stored_vs_Derived.md` · `36_Pantheon_Screens_UX.md` ·
`37_Code_Review_Findings.md` (outside the repo's `docs/` folder)

`37_Code_Review_Findings.md`'s claims were checked on 6 October by a full static
analysis -- two real, both fixed; the rest went into the backlog (I7–I10).

⚠️ `35_SQS_Stored_vs_Derived.md` records "DD → rare" as a deliberate reading.
That judgement was **reversed on 6 September** — see `06c_Faults_Closed_Earlier.md`.

These are research, done once, still accurate on their own terms. Nothing in the
maintained set should contradict them without saying so.

## Project notes (claude.ai project, outside the repo)

The working notes of each session (`claude/27` … `claude/46`) live in the claude.ai
project, not in git. The latest: 41 (Round 3), 42 (Rounds 4–6, Sundon), 43 (handover
11 Oct), 44 (Lector and Round 8, 12 Oct tests), 45 (the 97 questions and Wil's answers),
46 (Lector manual). This set is brought up to date from them.

## Retired

`01`–`05`, `10`, `23`, `24`, `26`, `27`, `28`, `29`, and every `*_APPEND*.md`.
Their content is in the set above. Archive them rather than deleting, in case a
figure needs tracing.

---

## How this set is meant to work

**One fact, one home.** The database figures live in `02` and nowhere else. The
work list lives in `03`. If a number appears twice it will diverge — that is the
dominant failure mode in this codebase and its documentation both.

**Files change in place.** No append blocks. When something is superseded, edit
the sentence and say what changed. An append is a promise to reconcile later,
and later does not come.

**Write what was measured, not what was inferred.** The previous set carried a
finding through five documents that ten minutes of running the application
disproved. If something has not been run, say so.

**Record the mistakes.** `05_Rules.md` exists because the same errors recur —
anchors that are not unique, constants defined after the class that uses them,
a rule restated instead of imported. They cost hours each time.

---

## Session routine

Before starting:
1. Read `03_Backlog.md` — the short list at the top
2. Skim `05_Rules.md` if it has been a while
3. Check `06_Faults.md` for anything open in the area being touched

After finishing:
1. Update `02_Current_State.md` if any figure moved
2. Move backlog items, do not annotate them in place
3. Add faults to `06` (next free number at its top), rules to `05`
4. Add one paragraph to `02b_History.md`
5. **Commit** — `git add -A` then `git commit`
6. **Refresh the off-site copy** if data changed — `01_Architecture.md` §7

---

## Conventions

**Patches** go in `scripts/` as `patch_*.py`, print ✓ or ✗ per edit, back the
file up, and **write nothing if any anchor fails**. They import the module
afterwards, not merely compile it.

**Diagnostics** go in `scripts/` as `check_*.py`, are read-only, re-runnable,
and end by saying "Nothing has been changed."

**Backups** before any rebuild or migration, via SQLite's online backup API,
into `C:\BiologicalSoftware_Backups\reference\` with a name saying what it
precedes.
