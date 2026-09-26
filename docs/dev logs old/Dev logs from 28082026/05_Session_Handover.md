# Biological Software — Session Handover

## Date: 5 September 2026 (through Session 32)
## Supersedes: 4 September 2026 handover

---

## Executive Summary

A day on Codex and Examen that started with a question about four moths and ended with nine
patches, three Codex rebuilds and a working assessment tool.

**Codex was losing, mis-choosing and hiding conservation facts.** The priority track
collapsed five jurisdictions into one slot per species (2,303 facts missing); collapse ties
were broken by row order rather than by date; and the TVK bridge had never consulted
`uksi.synonyms`, dropping a fifth of Pantheon. All three fixed and verified.

**Examen was inventing one.** The Conservation tab inferred "Section 41" from the key-species
tier, so an English site reported four Species of Principal Importance that are on the
Scottish and NI lists and not on S41 at all. Every other fault this year lost or mis-chose
facts; this one manufactured them.

**Examen runs.** The warning in five documents that it must not be run, and would report zero
key species, was wrong — see `29_Examen_Revival_Assessment.md` §0.

**Key species are now jurisdiction-aware.** Glory Park reports the **8** Wil said it should.

---

## Where Things Stand

| Area | State |
|------|------|
| **Codex** | Rebuilt three times today, verified after each. status_summary 25,426; priority 5,231; bridge 12,314; SQS 6,338. |
| **Examen** | **Runs.** Site Analysis and Species Database both working. Presentation fixes and the report layer remain. |
| Observatum — Data Entry | In production. Unchanged today. |
| Observatum — Insect Collection | Bulk editor still needed. |
| Version control | `main` current. **`stable` stale since June.** |
| Backups | Rebuilt, consolidated, restore tested (Session 31). Two reference copies of codex.db taken today, pre- and post-fix. |

---

## ⚠️ Do this first

**Check Bicester Graven Hill and Derby against what was issued.** Jurisdiction filtering moved
their key-species counts substantially:

| Site | Was | Now |
|---|---:|---:|
| BAM Glory Park | 12 | 8 |
| Badshot Lea | 11 | 10 |
| **Bicester Graven Hill** | **42** | **31** |
| **Derby** | **10** | **5** |
| Fermyn Hall Deadwood | 8 | 8 |

The new figures are the defensible ones. But if a report went out with the old number, it is
worth knowing before someone else notices.

Note also that **any SQI computed before today differs from one computed now** — 551 more
species carry Pantheon scores via the bridge fix, and 296 derived guesses were replaced by
published values. That is a correction, not drift, but it makes the Codex version stamp
meaningful in a way it was not yesterday.

---

## What changed, in one table

| Fix | Effect |
|---|---|
| Priority collapse | 2,303 jurisdiction facts restored; priority rows 2,928 → 5,231 |
| Collapse tiebreak | Precedence first, then date. 12 wrong resolutions → 1 (correct) |
| Bridge synonym pass | 1,153 species recovered; SQS 6,083 → 6,338 |
| Species Database view | Crash fixed; panel had been blank since April |
| Guild casing | Larval predators 37+4 → **41** |
| Conservation tab | Stopped inventing Section 41 |
| Appendix labels | "S41/BAP (2)" → "NI Priority, SBL" |
| Jurisdiction filtering | Key species mean what they say in England |

---

## Immediate

1. **J2 — the 1,847 bridge collisions.** Rule decided (incumbent wins, union the ecology);
   not applied. ~1 day.
2. **D9 — derive gap-filled SQS live.** 525 of 816 don't follow the published rule. 0.5–1 day.
3. **A1 — bulk curatorial editor.** Blocking the collection data.
4. **D2b — external drive copy.** Ten minutes, and the last real backup gap.
5. **G17 — jurisdiction selector in the UI.** The parameter exists and defaults to England;
   there is no control. Needed before a Scottish or Welsh job.

---

## Examen — revised understanding

Supersedes the entry in the previous handover, which was based on a finding that did not
survive contact with the running application.

- The engine and the display tabs are **current and correct**
- `examen_data.py` was **not** the stale file — `species_database_view.py` was
- Examen **works**; the remaining work is presentation and reports, not repair
- **Two report frameworks** still stand: Pantheon (Bicester-type) and saproxylic SQI + IEC
  (Kent Deadwood). The second is entirely absent from the software (G12, ~3 days).
- The main remaining build is the **report renderers** (G7, 2–3 days)

---

## Housekeeping Carried Forward

- **PowerShell writes must not add a BOM** —
  `[IO.File]::WriteAllText($p, $t, (New-Object Text.UTF8Encoding $false))`
- **In `python -c` under PowerShell, single quotes only, and avoid `*` in SQL.** Use
  `COUNT(1)` and `chr(39)`. Cost three failed commands in one session.
- **Line endings are mixed** — prefer single-line anchors or line-based patching.
- **Count your anchors.** A patch refused to write because `_classify(status)` has four call
  sites and the batch line is a substring of the single line. The refusal was correct.
- **Compiling is not importing.** A patch put module constants below the class that used them
  as method defaults; it compiled and raised `NameError` on import. Patch scripts must import
  the module.
- **Check the schema before writing the query.** `PRAGMA table_info` first.
- **Import the rule, don't restate it.** A diagnostic imported the gap-fill table as "the
  published rule" and produced a confidently wrong result.
- **Run the thing before writing that it cannot be run.**
- **Read the whole method before editing it.**
- **Derive, don't copy, anything with a spatial dependency.**
- **Prune by filename, not mtime, inside OneDrive.**
