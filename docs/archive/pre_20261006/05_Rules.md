# Rules

## Updated 5 October 2026
## Every rule here was paid for. Read this before a long session.

---

## The dominant failure mode

**When the same rule is written down twice, it drifts.** Nine instances found:

| Duplication | What it cost |
|---|---|
| `examen_data.py`'s Codex track mirror | Two analysis modes classifying tiers by different rules |
| `species_database_view.py`'s 8-track names | A blank status panel for five months, and a crash |
| `SRC_SETTING_KEYS` in the Data Entry info panel | A `KeyError` on legend toggle |
| The import-notes combining | Every warning doubled, 175 rows |
| `shared/sqs_derivation.py` vs `scripts/sqs_derivation.py` | Had drifted; the second deleted 26 September |
| Four `theme.py` files | Defensible — the satellite apps started standalone |
| **Three grid-ref implementations** | **Not yet cost anything. Would produce wrong vice-counties, silently.** |
| The SQI arithmetic in four places | Now one call to `compute_sqi` |
| `status_detail` applied to `legal_protection` but not `priority` | 2,303 conservation facts lost |

That last one is a variant worth naming separately: **written once, applied to
one case, forgotten for the other, in the same dictionary in the same file.**
When a design says two things go in the same place, verify both got there.

**The rule:** move it to one place. A comment saying "keep in sync" is a
prediction that it will not be.

Applied from the start for specimen sex: five displays, one formatter
(`shared/sex_summary.py`), so `♂3 ♀4` cannot come out differently in two places.

---

## Two numbers side by side

**Put a second, independently-derived number next to an existing one, and the
wrong one declares itself.** The Insect Collection tree had been under-reporting
for six months — 338 specimens missing — and looked entirely plausible
throughout. It was exposed only when a sex breakdown, counted a different way,
sat beside the totals and failed to add up. The sex figures were right; the
counts were not.

Nothing else would have found it. Worth doing deliberately: wherever a figure
matters, show how it was arrived at alongside it.

### Validate against an independent figure — every figure

**A validation that compares some numbers proves only those numbers.** Glory Park
was "validated" in September: same 128 species, same eight key species as the
issued report. The SQI was never compared. Examen said 134; the report, from the
Pantheon website, said 117 — and had said so the whole time. Two faults
(4,026 dropped scores, the wrong divisor) sat behind that gap for six months.

When an independent figure exists — an issued report, the Pantheon website, a
published table — compare **every** figure it gives, and write down which ones
matched. Glory Park now matches on species analysed, key species, SQI and two
habitat SQIs; the one residual is recorded rather than smoothed over.

### A figure should carry its own arithmetic

**If a reader cannot recompute a number from the sheet, they cannot trust it, and
neither can you.** The workbook said "SQI 118 — from 174 scoring species";
217 ÷ 174 is 125. The real divisor was 184. Show the sum and the divisor beside
the result.

### A blank should say why

An empty cell reads as missing data. "No Pantheon data", "(derived)", "research
only" — a few words turn a hole into a fact, and **the labels are what exposed the
4,026 dropped scores**: "no Pantheon data" against the 7-spot Ladybird could not be
true.

---

## Conservation statuses: which one stands

**Each species takes its status from the newest review that assessed it.** A
newer review supersedes an older one for every species it assessed: changed
statuses replace the old, removed statuses are cleared. Where only a pre-IUCN
review exists (Falk 1991 aculeates, Hyman 1992/94 beetles), its RDB / Na / Nb /
Notable statuses stand and count as Key under Telfer.

**Exclusion by judgement is an assessment; exclusion by scope is not.** A newer
review that leaves a species out *because it judged it not scarce or threatened*
withdraws the old status (NECR234: *Phaonia siebecki*, "neither scarce nor
threatened enough"). One that leaves a group out of its *scope* does not
(NECR234 left the Tachinidae for a later volume, so *Cistogaster globosa*'s RDB1
stands; NECR265 covered only the Tachyporinae, so other rove beetles keep
Hyman's statuses). Read every review's front matter for an excluded-species list.

**JNCC's spreadsheet does not enforce this.** It kept old designations beside
newer ones (71 species) and carried only part of the provisional fly reviews.
After loading any review, run `check_legacy_conflicts.py`,
`check_newest_review.py` and `check_old_names.py`.

**Where a report contradicts itself, the data sheet wins over the summary
table.** The sheet is where the assessment and its reasoning are made (NECR234:
4 of 300 disagreed).

**Withdraw by exact name only.** Matching through UKSI synonyms is right when
*adding* a review's statuses (it finds the current name); when *removing*, it
can land on a current species the same review assessed. NECR217's 'Taxonomy'
exclusions resolved to four valid species and cleared their new NS (4 Oct,
restored). `withdraw_statuses.py` now refuses any name that resolves to a
different species.

**Old statuses hide in the detail field.** JNCC stores some legacy statuses with
a qualifier (RDBK / 'Insufficiently Known', '1994 IUCN', 'Indeterminate',
'Pre-1994 RDB'). Any check or clearance on threat/rarity tracks must include rows
*with* a detail -- and a clearance must record that detail, or a rebuild restores
it to the wrong row. `clear_legacy_detail.py`.

**Old names carry old statuses.** A species assessed under its current name
leaves its old name's status behind (*Hercostomus nigrocoerulea* -> *Ortochile*).
UKSI's synonym table finds them.

## Species accounts from reviews

**Take a review's account verbatim, or not at all.** Extract with code, never
retype or summarise; check every sentence against an independent extraction of
the same file (`pdftotext` raw mode). Only rationale/justification columns are
not accounts and are not loaded.

**Check the licence at the publisher, not only on the PDF.** "Copyright JNCC 2014"
on the report; "Available under the Open Government Licence 3.0" on JNCC's own
record. "All rights reserved" (NRW spiders 2017) means internal reference only.

**Licence decides publication, not storage.** OGL accounts are quoted in the
workbook with their citation; others (the sawfly reports) are stored as internal
reference and the workbook shows a pointer instead.

**Where JNCC already holds a review's statuses, load its accounts only.**
Reloading statuses duplicates JNCC and the loader's legacy-clearing could undo
its precedence. Load statuses only where Codex lacks them (Dolichopodidae, the
provisional fly reviews).

**When a PDF's citation page is an image, confirm the citation from publication
records** (Pantheon's bibliography, Natural England's catalogue) -- never from
memory.

## Patching

**Anchors must be unique, and a substring of a longer identifier is not.** A
guard on `"_sqi_text"` matched the local variable `h_sqi_text` and skipped the
whole patch. Guard on a definition — `def x`, `class X` — or on a comment.

**Count your anchors before writing the patch.** One refused to write because
`_classify(status)` has four call sites, and the batch line is a *substring* of
the single line, so counting one inside the other double-counted. The refusal was
correct behaviour.

**A patch that reverts an earlier patch must anchor on what the revert left**,
not on the original text. Otherwise the later edits can never match.

**Compiling is not importing.** A patch placed module constants immediately
before the function that used them — at the bottom of the file — while method
default arguments referencing them sit in the class above. Default arguments are
evaluated when the class body runs. It compiled cleanly and raised `NameError` on
import. **Patch scripts must import the module afterwards.**

**Once a script has started changing files, any failure must restore** -- not
only the failures it anticipated. Wrap everything after the first change.

**Close what you read before you move it.** openpyxl's read-only workbooks hold
the file open on Windows until `wb.close()`; the move then fails.

**A child Python with captured output needs `PYTHONIOENCODING=utf-8`** and
decoding as UTF-8, or a ✓ printed at import crashes the print (cp1252 pipe).

**Test against the real constant, not a guessed one.** A mock's invented CLEAR
marker failed where the real `'none'` would not -- read the real value first.

**Unique within the function, not just the file.** A line that occurs once in
the function you mean may occur again elsewhere: `repo.delete_row(conn, row["id"])`
appeared twice in `commit_service.py`, once where `new_id` and `kwargs` do not
exist. The guard refused. Locate the function by parsing (`ast`) and search only
inside it.

**A re-run guard must look for what the patch actually writes.** One guard
checked for "Animalia"; the inserted code said `'animalia'`. A second run would
have inserted the block again. Guard on a distinctive token from the inserted
text itself.

**Write nothing if any anchor fails.** All-or-nothing beats a half-applied patch
every time. This has saved us twice.

**Prefer line-based patching for anything multi-line.** Split, locate markers,
replace ranges, rejoin with the original ending. Line endings are mixed across
this codebase and multi-line string anchors fail unpredictably.

**A failed replacement is silent.** Verify with `Select-String` or a re-read,
not just a syntax check.

**After a line-based edit, re-read the region — don't trust the index.** With
mixed line endings the file splits on `\r\n`, so runs of LF-only lines collapse
into one "line" and the count goes wrong. One patch reported inserting at line
358 when the target was at 420. It landed correctly; a patch that *trusted* its
line number could have inserted anywhere.

**A patch that refused has not been applied.** The jurisdiction patch was run,
reported as done, and sat unapplied for weeks — it had refused on a missing
import and written nothing. Read the output every time; "I ran it" is not "it
worked". The only proof is seeing the change in the running application.

**Don't import a view module to test a static method.** It drags in the whole
application's import chain — Observatum's config expects `src/` on the path —
and fails for reasons unrelated to the change. Compile the file and exercise the
logic separately.

---

## Diagnostics

**Import the rule, do not restate it.** A diagnostic imported
`seed_codex.SQS_DEFAULTS` as "Pantheon's published rule" and reported 52%
agreement and 408 bad merge incumbents. Both figures were artefacts —
`SQS_DEFAULTS` is the *gap-fill* table, on a partly different scale, mapping
single pairs where the real rule is a function of two variables. The right module
was `shared/sqs_derivation.py`. Re-run: 85% and 8%.

**Check the schema before writing the query.** Two diagnostics in one session
guessed column names and failed. `pantheon.db.conservation_status` has
`reporting_category`, not `category`. `PRAGMA table_info` first.

**Read the column order before indexing a row.** A check compared `r[1]` with a
TVK in Pantheon's `sqs_scores`; the table is `(tvk, sqs)`, so it compared scores
with TVKs and returned empty whatever the data held. Name columns, or `PRAGMA
table_info` first — the existing rule, broken again.

**Run the thing before writing that it cannot be run.** A finding written from
reading is a hypothesis. One such finding was carried through five documents and
gated the Examen revival for a week; ten minutes of running the application
disproved it.

**Verify a write by reading the row back.** `AddSpecimenDialog` was patched to
compute the sort key. It compiled; its formula reproduced all 2,566 existing keys;
it had **no effect at all**, because `SpecimenRepository` was discarding the
column one layer down. Only saving a real specimen and querying the row showed
it. A compile, a unit check and a code review all passed a change that did
nothing.

**Test your own assertion, don't assume it.** "J2 is now moot" was asserted from
reasoning and turned out to be wrong — the read layer could not see taxa that
were never in the bridge. The measurement also shrank the job from 1,847 merges
to about 90 that mattered.

**Check the authority, not the reports that cite it.** Four published reports
describe Pantheon's SQS scale; none states what Near Threatened scores, because
all of them defer to Pantheon's own scoring-systems page. Reasoning from the
reports would have given a plausible answer — NT is a Key Species, so score it as
notable — that the actual rule contradicts. When several sources cite one
authority, read the authority.

**A module's docstring is evidence.** `sqs_derivation.py` documented the correct
rule — "there is no score of 2 in the published rule", "returns 0, 1, 4, 8, 16 or
32" — and implemented a different one. Where code and its own documentation
disagree, that is a finding, not noise.

---

## PowerShell

**`-Encoding UTF8` writes a BOM** in Windows PowerShell 5.1, which breaks
direct-text parsing of Python source. Use:

```powershell
[IO.File]::WriteAllText($path, $text, (New-Object Text.UTF8Encoding $false))
```

**In `python -c`, use only single quotes inside, and avoid `*` in SQL.** Escaped
double quotes and asterisks are both intercepted by the shell before Python sees
them. Use `COUNT(1)`, and build a needed quote with `chr(39)`. This cost three
failed commands in one session — put anything with quotes in a small file
instead.

**`chr()` is Python; `char()` is SQLite.** Dodging one quoting problem created
another. Twice.

**Inline Python with nested quotes is fragile in PowerShell.** A `python -c`
with escaped double quotes silently arrived broken. Ship a small script instead.

**Never put `<placeholder>` in a command.** PowerShell reads `<` as a redirect and
stops before Python starts. Give the real values, or a word like `TVK_HERE` that
the script will reject.

**`Out-File` from `>` writes UTF-16.** Use `| Out-File -Encoding utf8` when the
output is going to be read by anything else.

**Don't paste illustrative Python into the shell.** Code shown to explain a fix
is not a command. Mark it clearly or put it in a file.

**No `head`, no `-B` in `Select-String`, no range in `Select-Object -Index`.**
Use `$content[-10..-1]`, `Select-String -Context 1,2`,
`(Get-Content file)[699..719]`.

**Use `powershell -ExecutionPolicy Bypass -File`** rather than running `.ps1`
directly.

**OneDrive locks `.git/objects` during git's post-commit tidy-up**, producing
*"Deletion of directory '.git/objects/01' failed. Should I try again?"* The
commit has already been written; answer `n`. To stop the prompt:
`[Environment]::SetEnvironmentVariable("GIT_ASK_YESNO", "false", "User")`.

**Clipboard contents go to whichever window has focus.** Pasting a Python file
into PowerShell runs each line as a command — harmless, since every one fails,
but alarming. Attach files rather than pasting them.

**Do not write to `QSettings` from the command line.** A bare `QSettings()` may
not reach the store the app uses, and may reach something else.

---

## Databases

**Never `shutil.copy2` a WAL-mode database.** Copying the main file while it is
open can capture a database missing recent commits, or one whose main file and
`-wal` are out of step. Use `conn.backup()`. Three mechanisms did this wrongly
while the one correct method had no callers at all.

**Back up before any rebuild**, with a name saying what it precedes.

**Any join between Pantheon and anything else goes through the TVK bridge.**
`pantheon.db` is keyed on 2017 TVKs; everything else on current UKSI TVKs.
Ignoring that lost the ecology of 3,666 species silently.

**A whitelist that silently drops unknown keys turns a correct caller into a
no-op.** `SpecimenRepository.create()`, `update()` and `create_many()` each
filtered writes through a field list that had never included
`taxonomic_sort_key` or `superfamily`. No error, no warning. Any repository with
an `allowed_fields` set is worth checking against its table's columns.

**Accumulate, don't assign, when rows can share a key.** `build_tree` did
`d[species] = count`. When NULL and `''` subfamily split one species into two
query rows, the second silently overwrote the first — 94 specimens gone. `+=`
would have been correct regardless of what the query returned.

**NULL and `''` are different groups to SQL.** Normalise with
`NULLIF(TRIM(COALESCE(col,'')),'')` before grouping on any column that might
hold either.

**A filter keyed on a proxy silently deletes data.** The Codex build decided
"invertebrate" by "has a conservation designation". Common species have none, so
4,026 Pantheon scores were thrown away as "non-invertebrate collisions" — and the
log line reported it every build, with a plausible name. Decide a category from
the authority for that category (UKSI taxonomy), and treat a large "filtered"
count as a question, not a statistic.

**Two kinds of value in one field must be marked.** Pantheon-published and
derived SQS shared one dict; the SQI mixed them while the stamp claimed one basis.
When a value can come from two sources, carry the source with it.

**Derive, don't copy, anything with a spatial dependency.** Vice-county always
comes from the grid reference, never carried down from the row above — a
different reference can mean a different county.

**Adding a column means a per-table audit of the reset scripts.** Extract each
`CREATE TABLE` independently and check within that block. A whole-file search
once reported "ALL OK" when `superfamily` was present in one definition and
missing from two others.

**Prune by filename, not mtime, inside OneDrive.** Sync rewrites modification
times, so timestamps there are not a record of when a file was made.

---

## Reading code

**Read the whole method before editing it.** Several detours have come from
working off a grep hit rather than the surrounding code.

**Check imports before using a name.** A fix referencing `QSettings` in a file
that did not import it would have crashed on first use.

**A filename search returns the shim and the implementation.** The shim is the
small one — three lines, re-exporting from `shared/`.

---

## Never-executed code paths — a standing risk

**Seven found this year**, every one of which would have failed on first real
use:

1. `mark_synced()` column mismatch
2. `sorted(..., QMessageBox)`
3. The missing `set_selected_count` branch
4. `_restore_database`'s `Path + str`
5. `species_database_view._display_codex_status` — crashed on any legally
   protected species
6. and 7. Two more claimed by static analysis, unverified

The pattern: code written alongside working code, never exercised, never found.
Worth a periodic sweep of rarely-used handlers, dialogs and repository methods.

---

## Reproducibility

Reports are stamped with a Codex version on the premise that the same version
reproduces the same figures. Two order-dependencies have already broken that
promise — the collapse tiebreak and the SQS import. Both are fixed, neither was
caught by anything but chance.

**A build-twice-and-compare check would catch the whole class in a minute.** It
is the same move that turned six backup layers from hypotheses into tested paths.

---

## Coding conventions

1. Design system first
2. Import, don't copy
3. Single source for constants
4. Files under 400 lines *(97 currently exceed it; the newer code honours it)*
5. Consistent patterns
6. No hardcoded colours — use `theme()` *(~120 hex literals outside theme files)*

Rules 4 and 6 are aspirations the older core does not meet. That is recorded
rather than pretended otherwise.

---

## Working practice

**Confirm understanding before execution**, especially before anything
destructive.

**"Proceed"** means continue with the plan as stated.

**Small fixes:** targeted edits — show the file, replace surgically. **Larger
deliveries:** a complete file, backed up first, rather than fifteen anchors.

**One file at a time for sensitive operations.**

**Estimate in exchanges, not effort.** When the code involved has been read, a
clean step is two or three minutes; each unfamiliar file adds one exchange. A
single readback up front (`scripts/show_funcs.py`) turned a two-hour estimate
into ten minutes.

**Diagnostic queries before and after every change.** The numbers are the proof;
"it still launches" is not.
