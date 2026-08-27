# Biological Software — Session Handover

## Date: 27 August 2026 (Session 28)
## Supersedes: 2 July 2026 handover

---

## Executive Summary

Field-season maintenance continues on `main`. Since the July reconciliation the **Data
Entry View has been built** (it now runs, writes a pre-live backup on launch, and has a
working keyboard entry grid) — that build spans chats not logged in these docs and needs
its own write-up. Session 28 itself was a short Observations-tab session: a Delete
Selected action was added, and two pre-existing defects were found and fixed while doing
it.

The authoritative forward plan remains `24_Phase_Plan.md`.

---

## Where Things Stand

| Area | State |
|------|-------|
| Version control | Git live: `main` + `stable`. Session 28 work committed to `main`, not yet merged to `stable`. |
| Observatum — Observations tab | Delete Selected live. Mark as Commercial crash fixed. Toolbar glyphs repaired. |
| Observatum — Data Entry View | **Built and running** (was "designed, winter"). Go-live backup on launch. State otherwise undocumented here — see gap note in `02`. |
| Codex | 11-track, clean baseline, 14,395 species. Unchanged. |
| Examen | Desktop retired; rebuild = winter. Unchanged. |
| Tabella | Pending-records system live. Pending hour still outstanding. |
| Curator / Munia / Atrium | Unchanged. |

---

## Immediate / Field-Season-Safe

- **Strip BOMs from 9 source files** (list in `02` and Infrastructure item 32). One
  commit, low risk, prevents recurring tooling confusion.
- **Tabella pending hour** (~1 hr): sheet protection (`UserInterfaceOnly:=True`) +
  Active Record Books path into Observatum Settings.
- **Import wizards re-enrich** conservation columns from live Codex.
- **Reconstruct `build_pantheon_db.py`**; rebuild-all chain script.
- **Eyeball** the future-dated commercial record (`2026-07-10`) — open since July.
- **Document the Data Entry View's current state** while it is fresh.

---

## Winter Projects (unchanged)

1. **Desktop Examen** (~5–8 days) — first.
2. **Data Entry View** — largely delivered ahead of schedule; remaining scope to be
   reassessed against `26_Data_Entry_Design.md`.
3. **Distributable Observatum** (~5–6 days).
4. Deferred: Codex display integration, mapping polish, gamification, web Examen.

---

## Housekeeping Carried Forward

- **PowerShell file writes must not add a BOM.** `Set-Content`/`Add-Content -Encoding UTF8`
  in Windows PowerShell 5 writes one; Python then rejects the file on direct text reads.
  Use `[IO.File]::WriteAllText($p, $text, (New-Object Text.UTF8Encoding $false))`.
- Mixed line endings (LF/CRLF) — normalise via `.gitattributes` if diffs get noisy.
- OneDrive locks `.git/objects` during `gc` — pause sync or `taskkill OneDrive.exe`.
- Recorder-name normalisation — deferred.
