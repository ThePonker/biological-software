# Roadmap

## Updated 10 October 2026

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

---

## Where the phases stand

| Phase | State |
|---|---|
| Hygiene -- git, WAL, backups, paths | ✅ Complete, June 2026 |
| Data integrity -- schema, taxonomy refresh, backup audit, `build_pantheon_db.py` (D5), rebuild-twice check (D7) | ✅ Complete (D5, D7 on 9 Oct) |
| **Codex correctness** | ✅ Complete. Kept current: JNCC June 2026, UKSI July 2025, 35 status reviews + 28 atlases (63 reviews, 6,566 accounts, 10 Oct) |
| **Species profiles** | ✅ Review and atlas accounts; 141 of your own. Five survey species still to write |
| **Examen** | ✅ Analysis validated; Excel, PDF and Word reports; compartments (E6); saproxylic SQI + IEC (E7); taxonomic summary (E8b) |
| Insect Collection curation | ✅ Bulk "Drawer in hand" editor. Checklist order open |
| Data Entry | ✅ In production |
| Suite review (9 Oct, ~140 findings) | ✅ Tier 1 fixed 9 Oct; Tier 2 and the three Tier 3 builds (one search, one taxon grouping, mapping selection) 10 Oct |
| **Now: polish and consistency** | 🔄 Counting switches everywhere, cleaning report, small wins (backlog A-F, L) |
| Final Recording Scheme dataset | Design next (backlog M1) |
| Report contents (methods, effort, limitations) | Winter -- decisions first |
| Import wizard merge (C4), stages 3+ | Winter |
| Photos (A8/A8b) | Discussion |
| Lector UI | Parked by Wil |
| Distributable suite | Winter or later -- partner's machine first; decide D8 before |
| Web Examen | Future, if reach ever justifies it |

---

## Sequence

### Now

**1. Commit, push, refresh the `D:\` copy** after each data-changing session.

**2. The note-36 decisions** -- about 30 minutes, one at a time, so they go into the next build.

**3. Counting switches everywhere + cleaning report** (backlog A, B) -- about 6 h with testing.
Settles OBS-18: every figure agrees with the table it came from.

**4. Small wins** (backlog C-F, L) -- about 6 h with testing.

**5. Final scheme dataset** (M1) -- questions, then 1-2 sessions.

### Winter

**Report contents** -- the 15 decisions in `claude/30` Part 4, then the methods layer (survey
effort, visits, limitations, taxonomic coverage, data-sharing sentence).

**Merge the import wizards** -- stages 3+ of C4, ~4-7 days with testing against real imports.

**Photos** -- ~3 days linking + 1.5-2.5 days for the inbox, once P1-P9 are decided.

**Lector UI** -- ~8-10 h, plus restoring the lost Word dossier / excerpts work.

**Distributable suite** -- ~5-6 days Observatum + 3-5 Examen: module registry, first-run wizard,
de-personalisation, PyInstaller, licence screens. First install: Wil's partner's machine.

### Future

**Shared Longhorn dataset with a second user** (M2) -- after D8.

**Web Examen** -- 10-15 focused days, soft estimate on a new stack. Not foreclosed, not needed.

---

## Estimates

| Build | Focused time |
|---|---|
| ~~Excel, PDF, Word renderers; compartments; presentation; bulk editor; saproxylic; code hygiene; species profiles~~ | ✅ done |
| ~~Shared search, filter wizard, taxon groups, mapping selection, Tier 2 review~~ | ✅ done 10 Oct |
| Counting switches + cleaning report | 5-7 h + 2 h testing |
| Small wins (C-F, L) | 6-8 h + 2 h testing |
| Final scheme dataset | 1-2 sessions |
| Merge the import wizards (rest) | 4-7 days |
| Photos | 4.5-5.5 days |
| Lector UI | 8-10 h |
| Distributable suite | 8-11 days |
| Web Examen | 10-15 days |

**These are focused days.** Done in evenings and on rainy days, each multiplies
into weeks of calendar time. One major build per winter is realistic for a solo
developer; agent-built rounds with Wil testing (as on 10 Oct) move the small and
medium items much faster.

---

## Risk register

| Risk | Severity | State |
|---|---|---|
| Single machine, no off-site copy | — | ✅ **Closed 26 September.** Verified external copy. Refresh after sessions that change data. |
| **`stable` stale since June** | Medium | Open (D3). Four months of work on `main` only. |
| **Counts differ between screens** | Medium | Open (OBS-18, fault F45). Fixed by backlog A. |
| **Curatorial fields empty across the collection** | Medium | Bulk editor built (A1); filling is ongoing. |
| Unsourced verdict in generated prose | — | ✅ Closed 8 Oct (E16): the verdict sentence removed. |
| **Silent write whitelists** | Medium | One found and fixed (`SpecimenRepository`). The pattern — a layer that drops unknown fields without error — is worth a sweep of the other repositories. |
| `build_pantheon_db.py` missing | — | ✅ Closed 9 Oct (D5). |
| Reference databases writable from anywhere | — | ✅ Closed 9 Oct (D9): `connect_ro()` everywhere; a stray write fails. |
| **UKSI disagrees with you on 24 British beetles** | Low | Kept at your request; raise with NHM (F11). |
| Never-executed code paths | Low | Swept 8 Oct (D6); ruff pre-commit hook since 9 Oct. |
| **Duplicated rules drifting** | Medium | **The dominant failure mode.** Ten instances found. Grid-ref maths in three places is the one that could produce silently wrong data (I3); species lookup in three import wizards is the most expensive to maintain (C4). |
| Rebuild reproducibility | — | ✅ Proven 9 Oct (D7): two builds identical. |
| Tabella bakes Codex at generation time | Low | Reduced — Tabella paused, workbooks migrated. Import wizards should still re-enrich (C1). |
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
