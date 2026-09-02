DOC UPDATE BUNDLE — 2 July 2026 reconciliation
================================================
Brings the stale session/state logs up to the current June (Session 26) state,
folding in the three field-season chats (Codex widening, iRecord recovery,
observation-edit + Tabella fixes).

BEFORE OVERWRITING: timestamped-copy your existing docs/ first (your usual habit),
e.g.  Copy-Item docs\NN_*.md docs\_backup_20260702\  -Force

DROP-IN REPLACEMENTS (full-file rewrites):
  01_Development_History.md      history through Session 26; suite table + metrics refreshed
  02_Current_Session_Summary.md  now Session 26 (was stuck on Session 25); codex 7,612 -> 14,395
  03_Development_Plan.md         defers to 24_Phase_Plan; statuses updated
  04_Current_State_Analysis.md   DB figures + component statuses corrected; Examen retired
  05_Session_Handover.md         current handover + forward plan

SURGICAL ADDITIONS (originals preserved, new sections appended):
  10_Infrastructure_Issues.md    +items 25-31 (obs update() fix, mark_synced, refresh_records,
                                 iRecord bug, Phase 0, line endings, future-dated record)
  23_Rebuild_Procedures.md       Codex section notes the widened 11-track build behaviour
  08_Examen_Design_Spec.md       superseded/reference-only banner added

NO CHANGE NEEDED (already current): 06, 07, 08_Web, 09 (historical), 11, 24, 25, 26

STILL OPEN AFTER THIS:
  - Future-dated commercial record (2026-07-10) — eyeball
  - 07_Codex_Design_Spec.md "Contents" table shows status_summary 21,112 / sqs_scores 15,663,
    which differ from the clean baseline (23,123 / 6,082). Left untouched (design spec, not a
    state doc) but worth reconciling next time you touch 07.
