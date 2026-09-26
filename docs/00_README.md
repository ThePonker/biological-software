# Biological Software — Documentation

## Set v2, updated 6 September 2026
## Replaces the 01–37 series, which had drifted into three append files and
## several documents describing states that lasted hours.

---

## The set

| File | Answers |
|---|---|
| `00_README.md` | What is here, and how to keep it honest |
| `01_Architecture.md` | What exists, where it lives, which database holds what |
| `02_Current_State.md` | Where everything stands today, with figures |
| `03_Backlog.md` | What to do next — **check before starting a session** |
| `04_Roadmap.md` | Strategy, phases, estimates, risks |
| `05_Rules.md` | How to work on this codebase without repeating old mistakes |
| `06_Faults.md` | Open faults, and closed ones for the record |
| `07_Codex.md` | Codex — the conservation authority |
| `08_Examen.md` | Examen — the assemblage assessment tool |
| `09_Data_Entry.md` | Data Entry — the recording grid |

## Retained as background reading, not maintained

`25_Data_Entry_Research.md` (MapMate / Recorder 6 study) ·
`32_Examen_Requirements.md` · `32b_Examen_Requirements_Addendum.md` ·
`33_Pantheon_Deep_Dive.md` · `34_Musgrove_Paper_Analysis.md` ·
`35_SQS_Stored_vs_Derived.md` · `36_Pantheon_Screens_UX.md` ·
`37_Code_Review_Findings.md` · `38_Report_Survey.md`

`38_Report_Survey.md` is the specification for the report layer, drawn from
eleven published reports. Read it before touching E3 or E7.

⚠️ `35_SQS_Stored_vs_Derived.md` records "DD → rare" as a deliberate reading.
That judgement was **reversed on 6 September** — see `06_Faults.md`.

These are research, done once, still accurate on their own terms. Nothing in the
maintained set should contradict them without saying so.

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
3. Add faults to `06`, rules to `05`
4. Add one paragraph to the history section of `02`

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
