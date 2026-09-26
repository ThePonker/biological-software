# Roadmap

## Updated 6 September 2026

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
| Hygiene — git, WAL, backups, paths | ✅ Complete, June 2026 |
| Data integrity — schema, taxonomy refresh, backup audit | ✅ Complete |
| **Codex correctness** | ✅ Complete, 5 September 2026 |
| **Examen — analysis** | ✅ Working and validated |
| **Examen — reports** | Excel ✅ delivered. **PDF next**, then Word |
| Examen — saproxylic framework | Not started, ~3 days |
| Insect Collection curation | Bulk editor outstanding |
| Distributable Observatum | Winter or later |
| Web Examen | Future, if reach ever justifies it |

---

## Sequence

### Now

**1. Wire the workbook to a button** — small. The exporter works and is
validated; it is reachable only from a script.

**2. Jurisdiction selector** — small, but it gates any non-English work.

**3. Bulk curatorial editor** — 0.5–1 day. Blocking 2,549 specimens' worth of
collection data.

**4. External drive copy** — 10 minutes, and it closes the last real backup gap.

### Then

**PDF and Word renderers** — 1.5–2.5 days together. Both render the same computed
result the workbook already assembles, so the analysis work is done. PDF is the
document that gets attached to a report; Word is for pasting into templates.

**Compartment analysis** — 0.5 day. The 2025 Bicester report is a worked
specification: seven compartments, each with its own species count, key count,
percentage, and a stated 5% threshold.

**Presentation pass** — ~1 day. The accumulated E8–E11 items.

### Winter

**Saproxylic SQI + IEC** — ~3 days. The Kent Deadwood report uses a framework the
software has never contained. Until it exists, that class of work stays manual.

**Species profiles** — 1–2 days after the store decision. ~100 already written
across ~10 Word documents.

**Distributable Observatum** — ~5–6 days: module registry, conditional
dependents, first-run wizard, de-personalisation, PyInstaller, licensing screens.
Shares most of its work with a distributable Examen.

### Future

**Web Examen** — 10–15 focused days, soft estimate on a new stack. Gating items
already researched: hosting ~£4–7/month, accounts declined in favour of a mailing
list, donations likely within the £1,000 trading allowance. Not foreclosed, not
needed.

---

## Estimates

| Build | Focused days |
|---|---|
| ~~Excel renderer~~ | ✅ done |
| PDF renderer | 1–1.5 |
| Word renderer | 0.5–1 |
| Compartment analysis | 0.5 |
| Presentation pass | ~1 |
| Bulk curatorial editor | 0.5–1 |
| Saproxylic SQI + IEC | ~3 |
| Species profiles | 1–2 |
| Distributable Observatum | ~5–6 |
| Web Examen | 10–15 |

**These are focused days.** Done in evenings and on rainy days, each multiplies
into weeks of calendar time. One major build per winter is realistic for a solo
developer.

---

## Risk register

| Risk | Severity | State |
|---|---|---|
| **Single machine, no off-site copy** | **Medium** | **Open.** OneDrive is sync, not backup — a deletion propagates. Ten minutes to close (D2). |
| **`stable` stale since June** | Medium | Open. Four months of work on `main` only. |
| **Curatorial fields empty across 2,549 specimens** | Medium | Open (A1). |
| **Two build scripts missing** | Medium | Open. `uksi_extractor.py` and `build_pantheon_db.py`, both lost in the March restructure. Neither database is at risk — both are backed up — but a UKSI release would find us unable to rebuild. |
| **Never-executed code paths** | Medium | Seven found this year, all crash-on-first-use. Sweep outstanding (D6). |
| **Duplicated rules drifting** | Medium | **The dominant failure mode.** Nine instances found. Grid-ref maths in three places is the one that could produce silently wrong data (I3). |
| Rebuild reproducibility | Low–medium | Two order-dependencies found and fixed; a build-twice-and-compare check would prove the rest (D7). |
| Tabella bakes Codex at generation time | Low | Reduced — Tabella paused, workbooks migrated. Import wizards should still re-enrich (C1). |
| Stale TVKs in `observatum.db` | Low, compounding | Diagnostic exists; re-run after UKSI updates. |
| SQLite over a syncing folder from two machines | Medium *if attempted* | Needs a decision before anyone tries it (D8). |
| Doc drift | Low | Set rewritten 5 September; `00_README.md` says how to keep it. |

---

## What "done" looks like

Examen produces a defensible assessment from a species list, in Excel, PDF and
Word, stamped with its Codex version and stating which SQS basis it used; it
handles both the Pantheon and saproxylic frameworks; and a colleague can be given
a copy with a `codex.db` and run it on their own machine.

Observatum captures records fast, keeps them safe, and hands them to Examen
without a spreadsheet in between.

Neither needs to be finished to be useful. Both already are.
