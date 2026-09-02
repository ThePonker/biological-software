DOC REWRITE BUNDLE — 29 August 2026
===================================
Full rewrite covering Sessions 27, 28 and 29, plus two new files. Replaces both the
2 July and 27 August bundles — apply this one instead of either, not on top of them.

BEFORE OVERWRITING: timestamped-copy docs\ first.
  Copy-Item docs\dev_logs\*.md docs\_backup_20260829\ -Force

DROP-IN REPLACEMENTS (full-file rewrites)
-----------------------------------------
  01_Development_History.md     through Session 29; Session 27 reconstructed from code
  02_Current_Session_Summary.md Sessions 28-29 in full
  03_Development_Plan.md        status roll-up; defers to 24 and 28
  04_Current_State_Analysis.md  current DB figures, DataEntry added, staging noted
  05_Session_Handover.md        current handover + data-protection table
  10_Infrastructure_Issues.md   CONSOLIDATED - open issues, closed register, rules learned
  24_Phase_Plan.md              reconciled: Data Entry delivered, Tabella paused,
                                new Phase 3c for Insect Collection curation

NEW FILES
---------
  27_Data_Entry_State.md        what the Data Entry View actually is, as built.
                                Architecture, grid behaviour, banner, data protection,
                                migration tooling, what is not yet built, known constraints.

  28_Development_Backlog.md     THE ITEMISED TO-DO LIST. Everything raised across these
                                sessions, grouped A-F with sizes and triggers. This is the
                                file to check before starting a session.

NO CHANGE NEEDED
----------------
  06_Software_Suite_Overview.md   (though Tabella's status is now "paused")
  07_Codex_Design_Spec.md         (see open item below)
  08_Examen_Design_Spec.md        superseded banner already applied
  08_Examen_Web_Design_Spec.md    still the definitive web design
  09_Restructure_Plan.md          historical
  11_Parallel_Development_Plan.md single-bot mode, unchanged
  23_Rebuild_Procedures.md        still accurate
  25_Data_Entry_Research.md       the research stands; 26 is the design; 27 is now the state
  26_Data_Entry_Design.md         retained as the design of record - 27 records the delta

WHAT THIS BUNDLE FIXES
----------------------
  - 24_Phase_Plan listed Data Entry as an unbuilt winter project at 4-6 days. It has been
    in production use all week.
  - 03 and 04 described Data Entry as pending and carried pre-migration DB figures.
  - 10 had grown into an original plus two append blocks with overlapping numbering.
  - Requests raised mid-session (bulk curatorial editor, staging map layer, label
    composition, drawer rename) had no home. They are now in 28.
  - Tabella's pause was never recorded anywhere.

STILL OPEN AFTER THIS
---------------------
  - Session 27 (the Data Entry build itself) is reconstructed from the code, not from a
    development log. 01 and 27 flag what is inferred. Fill in from your own notes if you
    have them - specifically which of the seven build steps in 26 section 7 were done.
  - 07_Codex_Design_Spec.md "Contents" table still shows status_summary 21,112 /
    sqs_scores 15,663 against the clean baseline 23,123 / 6,082. Unreconciled since July.
    Left alone because 07 is a design spec, not a state doc, but it misleads.
  - 06_Software_Suite_Overview.md predates Data Entry entirely - it lists six apps plus a
    launcher and does not mention the staging model.

DECISIONS RECORDED
------------------
  - Tabella development paused; Data Entry supersedes the desk workflow.
  - specimen_code will not be used; no retro-labelling of the collection.
  - Personal records stay on the spreadsheet -> iRecord -> Observatum path, NOT through
    Data Entry staging.
  - Common names follow UKSI's preferred flag, accepting its occasional odd choices.
  - CSV backups live outside OneDrive by design.
  - Local Site Name removed from the Add Specimen dialog; column retained.
