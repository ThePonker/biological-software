# Code Review Findings — Static Analysis

## Created 5 September 2026 (Session 32)
## Source: independent review by a second model (Claude Fable), working from a
## 14-part source dump — 379 files, ~105k lines
## Status: **findings recorded, not acted on.** Nothing in this document has been
## verified against the live codebase.

---

## 1. What this is, and how to treat it

An independent static-analysis pass over a snapshot of the whole suite, followed
by reading the flagged sites in context. It is a **findings list, not a patch**.

Three cautions on using it:

- **The reviewer worked from a dump, not the repository.** It cannot see what is
  in flight, which files are dead versus not-yet-deleted, or why a given method
  was added.
- **The snapshot predates 5 September.** `build_codex_db.py` has since taken two
  patches (`bak_fix1`, `bak_fix2`) and codex.db has been rebuilt twice. Take a
  fresh dump before acting on any deletion.
- **Each crash claim is a claim, not a fact.** Two are testable in seconds; see
  §2. Where this codebase's own history contradicts a finding, the history wins
  until the finding is reproduced.

---

## 2. Claimed crash bugs (four NameErrors) — UNVERIFIED

| # | Location | Claim | Prior assessment |
|---|---|---|---|
| 1 | `DataEntry/entry_grid.py:1562` | `_header_menu` references `real`, undefined in that method. Right-clicking a column header raises. Probably a list-comprehension from the sort method (line 224) that was meant to be reused. | **Plausible.** Right-clicking a header is exactly the sort of path nobody walks. Would be the fifth never-executed path found this year. |
| 2 | `observations/observation_filter_mixin.py:131` | Client-side fallback calls `set_observations_fast(observations)` where it should pass `filtered`. Only bites when `_obs_repo` is None. | **Plausible.** A dead-branch bug, consistent with the pattern. |
| 3 | `services/vc_lookup_service.py:417` | `get_vc_batch` annotated `List[str]`; only `Optional, Tuple, Dict, Any` imported. Annotations evaluate at definition time, so the class body would raise on import. | **Doubtful as stated.** Data Entry derives VC from the grid ref on every row, across 1,787 staged records. If this module could not import, it would have been hit. Expect a `from __future__ import annotations`, a wildcard import, or a gap in the dump. **Check first — a negative result is informative.** |
| 4 | `Tabella/grid_ref.py:12` | `OS_GRID_LETTERS` merges the 500 km first-letter table into the 5×5 second-letter table; seven keys silently overwritten. Currently unused — code validates against `BNG_SQUARES`. | **Harmless today, landmine later.** Tabella is paused. Delete or split when touched. |

**How to handle:** verify each individually when between tasks. Give them to
whoever holds the session history as *verifiable claims*, not instructions. A
"this can't raise, the module imports fine" answer is worth more than a patch.

---

## 3. Duplicated rules — the dominant failure mode, again

The review independently found three more instances of the pattern already
recorded in `10_Infrastructure_Issues.md`:

| Duplication | Detail |
|---|---|
| `shared/sqs_derivation.py` vs `scripts/sqs_derivation.py` | **Already drifted.** The shared copy has grown `DD → rare` and `NT → 2`; the scripts copy has not. Nothing imports the scripts copy. |
| Four `theme.py` files | Codex, DataEntry, Munia, gamification — alongside Observatum's `themes/` package |
| Three grid-ref implementations | `grid_ref_service.py`, `DataEntry/osgb.py`, `Tabella/grid_ref.py` |

**Running total of the "written twice, then drifts" pattern: eight.**
Previously: `examen_data.py`'s Codex track mirror; `SRC_SETTING_KEYS`; the
import-notes combining; the two SQS sources; and (Session 32) `status_detail`
applied to `legal_protection` but not `priority`.

**Grid-ref maths is the one that matters most.** A subtle disagreement between
three implementations produces *wrong vice-counties*, not a crash — and VC is
derived, never typed, so nothing downstream would question it.

The satellite apps having their own themes is defensible (they started as
standalones). Three grid-ref modules is not.

### Dead code
- Five files / ~1,700 lines of pre-split specimen wizard
  (`wizard_*_mixin.py` + `validation_worker.py`). Only
  `species_match_report_dialog.py:398` still imports `RowStatus` from the old
  worker — repoint, then remove the set.
- `DataEntry/species_dist_map.py` defines `has_data` twice (line 255 dead).
- `scheme_dashboard.py` defines `set_data` / `apply_theme` twice (970/981 dead).
- Duplicate `"import_notes"` key in
  `specimen_import_wizard/validation_worker.py:283`.

---

## 4. Coding rules, measured

| Rule | Measured |
|---|---|
| Files under 400 lines | **97 files exceed it.** Worst: `scheme_dashboard.py` (1,978), `entry_grid.py` (1,585), the two `validation_worker.py`s (1,355 / 1,236), `observation_repository.py` (1,287) |
| No hardcoded colours — use `theme()` | **~120 hex literals** outside theme files. `gamification/renderer.py` (27) and `launcher.py` (19) are the bulk; `splash_screen.py` (12) likely intentional |
| — | **One test file** for ~105k lines |

The mixin-split used for the wizards is the right shape; the dashboards and
validation workers are the obvious next targets. The pure functions — grid-ref
parsing, SQS derivation, date utils, VC lookup — are cheap to test and are
exactly where the claimed bugs live.

---

## 5. Error handling and noise

- **153 bare `except:` / `except Exception:`** and **86 `try/except: pass`**,
  concentrated in the validation workers and `vc_lookup_service.py`. In an import
  wizard this is where a swallowed exception becomes a wrong species match. At
  minimum, log them.
- **239 `print()` calls** in Observatum's `src`. A logging setup with a file
  handler would also help when others report problems.
- **408 unused imports, 132 f-strings without placeholders, 62 unused variables** —
  auto-fixable, with the caveat in §7.

---

## 6. What the review found sound

Worth recording, because it is the other half of an honest assessment:

- The **169 "SQL injection" flags are false positives** — everything is
  parameterised; only column names are interpolated, from internal dicts.
- `database.py` opens a fresh connection per call with WAL and
  `foreign_keys=ON`, so the QThread workers are safe.
- The **repository / service / view layering is consistent and readable**, and
  the re-export shims (`repositories/codex_repository.py` → `shared/`) are the
  right way to do "import, don't copy".

**Overall verdict given: a solid B+.** Architecture sound and consistently
applied; domain modelling strong. The debt is "things get added faster than old
versions get removed" — the cheap kind. A day or two of pruning would take it to
A− without touching functionality.

---

## 7. Risk stratification — what is safe to act on

| Risk | Work | Notes |
|---|---|---|
| **Low** | The four crash fixes | One line each, verifiable by reading ten lines of context. No design judgement. |
| **Medium** | Dead-code deletions | Verified as unimported *in a snapshot*. A launcher or `.bat` running a script copy directly would not show up. "It still launches" is not proof — the failure surfaces weeks later. |
| **Highest** | Bulk `ruff --fix` | 408 unused imports is where real breakage lives. PySide6 codebases carry side-effect imports, names re-exported via `__init__.py`, and — here — the shim pattern that exists *precisely* to re-export apparently-unused names. Small batches, launch test between each. |

---

## 8. Suggested sequence (rainy day, own session)

1. Verify the four crash claims individually. Start with `vc_lookup_service` —
   the fastest to disprove.
2. Fix whichever are real, as a patch script in the usual ✓/✗ form.
3. Delete `scripts/sqs_derivation.py` (drifted, unimported).
4. Repoint the `RowStatus` import; remove the stale wizard set.
5. Consolidate grid-ref maths to one module. **The highest-value item here** —
   it is the one duplication that can produce silently wrong data.
6. `ruff.toml` + pre-commit hook, so the lint counts stop growing.
7. Tests for the pure functions.

Items 1–4 are an afternoon. Item 5 deserves care. Items 6–7 are the ones that
stop this document being rewritten in a year.
