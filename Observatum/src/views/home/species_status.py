"""Conservation status and SQS for Home > Species Info (R17 B4). Read-only, no Qt.

Uses the suite's own reader, CodexRepository.get_status_summary (the one the Insect Collection
sidebar and Examen use): display_status for the statuses, sqs for the Species Quality Score
(Pantheon's published score, else the published rule applied to current Codex statuses).
Nothing is written to codex.db.
"""
from typing import Optional, Tuple

NO_STATUS = "None"
NO_SQS = "–"

_repo = None


def _default_repo():
    global _repo
    if _repo is None:
        from shared.repositories.codex_repository import CodexRepository
        _repo = CodexRepository()
    return _repo


def lookup(tvk: Optional[str], repo=None) -> Tuple[str, str]:
    """(statuses, SQS) as display text. ("None", "-") when there is none or Codex cannot be read."""
    if not tvk:
        return NO_STATUS, NO_SQS
    try:
        summary = (repo or _default_repo()).get_status_summary(tvk)
    except Exception as e:
        print(f"[species_status] Codex lookup for {tvk}: {e}")
        return NO_STATUS, NO_SQS
    status = (summary.display_status or "").strip() or NO_STATUS
    sqs = int(summary.sqs or 0)
    sqs_text = NO_SQS if sqs <= 0 else f"{sqs} (derived)" if summary.sqs_derived else str(sqs)
    return status, sqs_text
