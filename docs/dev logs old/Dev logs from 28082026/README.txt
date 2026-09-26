DOC UPDATE BUNDLE - 5 September 2026 (Session 32)
=================================================
Follows the 4 September bundle; apply that first if you have not already.

BEFORE OVERWRITING: timestamped-copy docs\ first.
  Copy-Item "docs\*.md" docs\_backup_20260905\ -Force


DROP-IN REPLACEMENTS
--------------------
  02_Current_Session_Summary.md   Session 32 in full
  05_Session_Handover.md          current handover - READ THE WARNING AT THE TOP
  10_Infrastructure_Issues.md     CONSOLIDATED. Folds in the Sessions 30-31 append
                                  block and adds items 56-69. After applying this,
                                  DELETE 10_Infrastructure_Issues_APPEND.md.
  28_Development_Backlog.md       CONSOLIDATED. Sections A-J; new section J (Codex
                                  data integrity); G rescoped throughout.
  29_Examen_Revival_Assessment.md CORRECTED. Its central finding was wrong - see the
                                  correction notice at section 0.

SURGICAL ADDITION (paste at the end of the existing file)
---------------------------------------------------------
  01_Development_History_APPEND_s32.md    Session 32

ALREADY SUPPLIED THIS SESSION (save if you have not)
----------------------------------------------------
  37_Code_Review_Findings.md      independent static analysis, UNVERIFIED


WHAT THIS BUNDLE RECORDS
------------------------
Codex was losing, mis-choosing and hiding conservation facts. Examen was inventing one.

  - PRIORITY COLLAPSE: five jurisdictions competed for one slot per species.
    2,303 facts missing; UK BAP at 12% of true coverage. Fixed; 2,928 -> 5,231 rows.
  - COLLAPSE TIES resolved by row order, not by date. 12 wrong; now 1 (correct).
    Rule: precedence first, date as tiebreak.
  - TVK BRIDGE never consulted uksi.synonyms. 3,000 of 3,068 unmatched species
    resolve through it. 1,153 recovered; SQS 6,083 -> 6,338. 1,847 collisions remain.
  - SPECIES DATABASE VIEW carried the stale 8-track names - blank panel since April,
    crashing for legally protected species. The seventh never-executed path this year.
  - GUILD COUNTS split by Pantheon's casing. Larval predators were 37 and 4; they are 41.
  - CONSERVATION TAB WAS INVENTING SECTION 41. Glory Park (Northamptonshire) reported
    four S41 species; none is on Section 41. They are on the Scottish and NI lists.
    The only fault this year that could have put a false statement in a client report.
  - APPENDIX labelled every priority listing "S41/BAP". Now names the jurisdiction.
  - KEY SPECIES ARE NOW JURISDICTION-AWARE. Glory Park 12 -> 8.

  - EXAMEN RUNS. The "must not be run, reports zero key species" warning in five
    documents was wrong. See 29 section 0.


*** CHECK THIS BEFORE ANYTHING ELSE ***
---------------------------------------
Jurisdiction filtering moved key-species counts on every site:

    BAM Glory Park          12 -> 8
    Badshot Lea             11 -> 10
    Bicester Graven Hill    42 -> 31     <-- check against what was issued
    Derby                   10 -> 5      <-- check against what was issued
    Fermyn Hall Deadwood     8 -> 8

The new figures are the defensible ones. Also note that any SQI computed before
5 September differs from one computed now, because 551 more species carry Pantheon
scores and 296 derived guesses were replaced by published values.


NEW CODE (all in scripts\)
--------------------------
Patches - each backs up, verifies, and refuses to write on any failed anchor:
  patch_priority_detail.py        jurisdiction into status_detail
  patch_status_tiebreak.py        precedence first, then date
  patch_bridge_synonyms.py        third pass on uksi.synonyms
  patch_species_db_view.py        11-track status panel
  patch_guild_casing.py           normalise guild casing
  patch_key_species_tracks.py     structured tracks on KeySpeciesEntry
  patch_conservation_tab.py       read tracks, stop inferring S41
  patch_display_status.py         name the jurisdiction, not "S41/BAP"
  patch_jurisdiction.py           jurisdiction-aware key species

Diagnostics - read-only, re-runnable:
  check_summary_loss.py           what the collapse drops, per track
  check_priority_impact.py        facts restored per jurisdiction
  check_contested_status.py       ties, and what a date rule would change
  check_bridge_collisions.py      the 1,847, sorted by kind
  check_sqs_vs_status.py          stored SQS vs the published rule
  check_pantheon_casing.py        case variants per Pantheon table
  check_research_only.py          the 71 BC research-only moths

DELETE: scripts\check_bridge_gap.py - superseded. It re-derives the unmatched set
from the pre-fix logic and now reports every recovery as a collision.


BACKUPS TAKEN
-------------
  C:\BiologicalSoftware_Backups\reference\codex_pre_priority_fix_20260905_095839.db
  C:\BiologicalSoftware_Backups\reference\codex_post_priority_fix_20260905_103537.db
  C:\BiologicalSoftware_Backups\reference\codex_pre_bridge_fix_20260905_110646.db
Plus .bak_fix* alongside every patched source file.


STILL OPEN AFTER THIS
---------------------
  - J2: the 1,847 bridge collisions. Rule decided, not applied. ~1 day.
  - D9: derive gap-filled SQS live. 525 of 816 don't follow the published rule.
  - G17: jurisdiction selector in the UI. Parameter exists, defaults to England,
    no control. Needed before a Scottish or Welsh job.
  - A1: bulk curatorial editor. D2b: external drive copy. D7: merge main -> stable.
  - Session 27 still reconstructed from code, not logged.
  - 06 and 07 still stale; 23 gives codex.db as 18 MB - it is 44.5 MB.


NEXT TASK
---------
  J2 - apply the bridge collision merges (incumbent wins, union the ecology),
  separating the 986 spelling variants and 26 subgenus reformattings from the
  835 genuine merges first. Then D9.
