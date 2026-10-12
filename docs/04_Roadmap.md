# Roadmap

## Updated 12 October 2026

---

## Strategic decisions

**1. Evolve, don't rewrite.** The current codebase is the final software.
Development continues in place, protected by git branching.

**2. Examen desktop, web later if ever.** The desktop build costs ~5–8 focused
days against ~10–15 for web, runs on the stack already in use, and carries no
hosting, privacy, tax or operational burden. Because the analysis lives in the
UI-agnostic `shared/` engine, building desktop forecloses nothing.

*Revised 5 September: most of the desktop build turned out to already exist. See
`08_Examen.md`.*

**3. Modularisation is a registry layer, not a rebuild.** Observatum's tabs
become config-driven modules so a distributed copy can omit Recording Scheme or
ship Mapping as a preview.

**4. Pilot distribution to 2–3 trusted colleagues**, not public release.

**5. Codex updates ship as a file.** Wil maintains Codex centrally; to update
another user's conservation data, send them a fresh `codex.db` to drop in. No
update server, no fetch logic, no version-check infrastructure. Works day one.

**6. The frozen record is the downloaded report**, stamped with its date and
Codex version — not a stored assessment. Reproducibility lives with the user,
which deletes the whole storage and privacy problem.

**7. Compute both SQS bases, state which was used.** Pantheon's published scores
are what make an SQI comparable with the literature; the published rule applied
to current Codex statuses is arguably more correct. Neither is discarded and
every figure says which it is.

**8. ## Where the phases stand

| Phase | State |
|---|---|
| Hygiene -- git, WAL, backups, paths | ✅ Complete, June 2026 |
| Data integrity -- schema, taxonomy refresh, backup audit, `build_pantheon_db.py` (D5), rebuild-twice check (D7) | ✅ Complete (D5, D7 on 9 Oct) |
| **Codex correctness** | ✅ Complete. Kept current: JNCC June 2026, UKSI July 2025, 63 reviews, 6,566 accounts |
| **Species profiles** | ✅ Review and atlas accounts; 141 of your own. Five survey species still to write |
| **Examen** | ✅ Analysis validated; Excel, PDF (passed 12 Oct) and Word reports; compartments; saproxylic SQI + IEC; taxonomic summary |
| Insect Collection curation | ✅ Bulk "Drawer in hand" editor; field-record links (11 Oct). Checklist order for drawers open |
| Data Entry | ✅ In production; Check before commit passed 12 Oct |
| Suite review (9 Oct, ~140 findings) | ✅ Tiers 1–2 and three Tier 3 builds done; leftovers swept in the small-fixes round |
| Polish and consistency (counting switches, cleaning report, small wins) | ✅ Rounds 2–3, 10–11 Oct, tested |
| Maps (labels, boundaries, districts, borders once, opacity) | ✅ Rounds 3–5 and 8, tested |
| Startup and laptop sizes | ✅ Rounds 4–6 and 8: window 5.7 s, ready 12 s, longest pause 106 ms; dialogs fit 1280×720 |
| **Lector in the suite** | ✅ Rounds 7–8 (window, saved searches, exports); tested 9 of 9. **Paused** |
| **Now: small-fixes round** | 🔄 13 items agreed 12 Oct (`03`) |
| Next big job | Q1, Wil's to decide (recommended: specimens → records) |
| Final Recording Scheme dataset | Questions straight after the next big job (Q4) |
| Photos (A8/A8b) | Decided (Q5, Q13–Q22, Q71); about 3 sessions |
| Partner's laptop install | Winter, after photos and the scheme dataset (Q2) |
| Report contents (methods, effort, limitations) | Winter; decisions Q74–Q83 taken |
| Import wizard merge (C4), stages 3+ | Winter; Q84–Q87 taken (Q85 to confirm) |
| Map background layers | Optional; decisions Q6, Q34–Q40 taken |
| Web Examen | Future, if reach ever justifies it |

---

## Sequence

### Now

**1. Small-fixes round** (`03`, items 1–13), then test, commit, push, refresh `D:\`.

**2. Merge `main` into `stable`** (Q88; 15 minutes).

**3. The next big job** (Q1). Suggested order, one at a time:
1. **Specimens → records** (about half a day; every decision answered).
2. **Final scheme dataset** (about an hour of questions, then 2 sessions).
3. **Photos** (about 3 sessions: linking and viewing, then the Inbox; microscope captures
   once the camera and stacking software are known).
4. **Partner's laptop install** (winter; 8–11 days with packaging).

**Optional slots** between them, each one round: map background layers (3–4 days), Atrium
icons and restyle (with Munia's look), splash and loading redesign.

**Lector** is paused; it resumes with the Q94/Q95/Q97 changes and its manual tests.

### Winter

**Report contents** -- Q74–Q83 answered; then the methods layer (ISIS compliance field,
data-sharing sentence and sensitive-species flag, CIEEM validity bands, survey effort).

**Merge the import wizards** -- stages 3+ of C4, ~4-7 days with testing against real imports.

**Distributable suite** -- module registry, first-run wizard, de-personalisation, PyInstaller,
licence screens. First install: Wil's partner's laptop, the full suite (Q68), her own empty
database plus an optional practice database (Q69).

### Later

**Batch maps screen** (the script works now; Q41–Q50 answered). **Final manuals** for Lector
and Observatum from annotated screenshots. **Shared Longhorn dataset with the partner** (M2).
**Web Examen** -- 10-15 focused days, not foreclosed, not needed.

---

## Estimates

| Build | Focused time |
|---|---|
| ~~Counting switches, cleaning report, small wins, maps, startup, laptop sizes, Lector window~~ | ✅ done 10–12 Oct |
| Small-fixes round (13 items) | about 1 round (build) + 1 test sitting |
| Specimens → records | about half a day |
| Final scheme dataset | 1 h of questions + 2 sessions |
| Photos | about 3 sessions (~2.25 days linking + 2–2.5 days Inbox) |
| Map background layers | 3-4 days |
| Atrium icons and restyle | about 1 session |
| Batch maps screen | about 1 session |
| Merge the import wizards (rest) | 4-7 days |
| Report contents | 2-3 sessions |
| Distributable suite | 8-11 days |
| Web Examen | 10-15 days |

On 11 Oct the remaining work was estimated at about 18–20 sessions at the current pace.
**These are focused days.** Agent-built rounds with Wil testing move small and medium items
fast; the limit is Wil's testing time, which is why one main line at a time.

---

## Risk register

| Risk | Severity | State |
|---|---|---|
| Single machine, no off-site copy | — | ✅ Closed 26 September. Refresh after sessions that change data. The 45 GB media library is not yet in the mirror (Q13); the backup may move to a larger drive |
| **`stable` stale since June** | Medium | Open (F2, D3). Decided: merge now Round 8 is committed (Q88) |
| Counts differ between screens | — | ✅ Closed 10 Oct (F45, counting switches) |
| **Curatorial fields empty across the collection** | Medium | Bulk editor built (A1); filling is ongoing |
| Unsourced verdict in generated prose | — | ✅ Closed 8 Oct (E16). The table colour bands stay by Wil's choice (Q81) |
| **Silent write whitelists** | Medium | One found and fixed (`SpecimenRepository`); latent cases listed in `03` Gathered |
| Reference databases writable from anywhere | — | ✅ Closed 9 Oct (D9) |
| **UKSI disagrees with you on 24 British beetles** | Low | Kept at your request; raise with NHM (F11) |
| **Duplicated rules drifting** | Medium | **The dominant failure mode.** New shared homes since 10 Oct: `record_kinds`, `species_counting`, `irecord_links`, `specimen_links`, `record_match`, `tick_mark`, `fit_to_screen` |
| **Spread too thin** | Medium | Agreed 12 Oct: one main line at a time, test and commit before the next round |
| Rebuild reproducibility | — | ✅ Proven 9 Oct (D7) |
| Stale TVKs in `observatum.db` | Low, compounding | 28 records wait for the next UKSI (Q61) |
| SQLite over a syncing folder from two machines | — | Decided 12 Oct: separate databases, export/import (Q3) |
| Caches keyed on too little | Low | One found 12 Oct (F47): a cache key must name every input (`05`) |
| Doc drift | Low | Docs brought up to 12 Oct after three days of rounds; update `02`/`03`/`06` with each round's commit |

---

izards should still re-enrich (C1). |
| Stale TVKs in `observatum.db` | Low, compounding | Diagnostic exists; re-run after UKSI updates. |
| **SQLite over a syncing folder from two machines** | Medium *if attempted* | Needs a decision (D8) **before the partner install / shared scheme dataset**. |
| Doc drift | Low | Set rewritten 5 September, kept current since; `00_README.md` says how. |

---

## What "done" looks like

Examen produces a defensible assessment from a species list, in Excel, PDF and
Word, stamped with its Codex version and stating which SQS basis it used; it
handles both the Pantheon and saproxylic frameworks; and a colleague can be given
a copy with a `codex.db` and run it on their own machine.

Observatum captures records fast, keeps them safe, and hands them to Examen
without a spreadsheet in between.

Neither needs to be finished to be useful. Both already are.
