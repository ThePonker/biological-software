"""display_format -- how dates and analysis modes are shown to a reader.

One home for presentation strings that more than one screen or export needs, so
the Examen screen and the assessment workbook cannot drift apart (05_Rules: a rule
written twice drifts). UI-agnostic: no Qt imports.
"""


def dmy(iso):
    """'2026-05-05' -> '05/05/2026'; anything else is returned unchanged."""
    s = str(iso or "")
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return f"{s[8:10]}/{s[5:7]}/{s[:4]}"
    return s


# AnalysisMode values (shared.repositories.codex_repository) -> reader-facing label
MODE_LABELS = {
    "codex_full": "Codex Full",
    "pantheon_only": "Pantheon Only",
}


def mode_label(mode):
    """'codex_full' or AnalysisMode.CODEX_FULL -> 'Codex Full'; unknown values unchanged."""
    value = getattr(mode, "value", mode)
    return MODE_LABELS.get(str(value or ""), str(value or ""))
