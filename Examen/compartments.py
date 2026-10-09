"""Examen -- compartment analysis (backlog E6).

Records carry `sub_location` (a compartment within the site, entered in Data Entry).
For one survey this gives, per compartment and combined:

    Compartment | Records | % of records | Species | Key species | % Key | Scoring | SQI | Note

after H2 Teesside Table 7 and the 2025 Bicester report. Each compartment's figures
come from the same PantheonAnalysisService.analyse that produces the survey's own --
key species by Codex under the same jurisdiction, SQI by Pantheon's divisor -- run on
that compartment's species. Nothing is re-derived here. The Combined row is the
survey's own result: pooling is not averaging, so its SQI can exceed every
compartment's.

A compartment holding fewer than `min_share_pct` (compartment_config.json, default 5)
of the survey's records is flagged. Records with no sub_location go in
"(no compartment)". The section is shown only when there are two or more compartments.

Computed once per analysis (`for_detail`, cached on the SiteDetail); the Overview, the
workbook sheet and the PDF/Word reports all lay out `CompartmentResult.table()`.
"""
from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "compartment_config.json")
DEFAULT_CONFIG = {"min_share_pct": 5}
NO_COMPARTMENT = "(no compartment)"
COMBINED = "Combined"
HEADS = ["Compartment", "Records", "% of records", "Species", "Key species", "% Key",
         "Scoring", "SQI", "Note"]


def config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG, encoding="utf-8") as f:
            cfg.update({k: v for k, v in json.load(f).items() if not k.startswith("_")})
    except (OSError, ValueError):
        pass
    return cfg


def compartment_name(value) -> str:
    """sub_location normalised: NULL, '' and whitespace are all '(no compartment)'."""
    v = " ".join(str(value or "").split())
    return v or NO_COMPARTMENT


# ---- split ------------------------------------------------------------------

def split_records(rows) -> Dict[str, dict]:
    """rows: (sub_location, tvk, species_name, n_records).
    -> {compartment: {"records": n, "tvks": [tvk, ...], "names": {tvk: name}}}

    Records are accumulated, never assigned (two rows can share a compartment and a
    TVK where the name differs). Records without a TVK count as records only.
    """
    out: Dict[str, dict] = {}
    for sub, tvk, name, n in rows:
        c = out.setdefault(compartment_name(sub), {"records": 0, "tvks": [], "names": {}})
        c["records"] += int(n or 0)
        if tvk and tvk not in c["names"]:
            c["tvks"].append(tvk)
            c["names"][tvk] = name or ""
    return out


def load_rows(project_name, client="", survey_year=None, conn=None):
    """(sub_location, tvk, name, records) for one survey -- the scope the survey's own
    figures use (project, client, survey year)."""
    try:
        from Examen.workbook_export import _survey_where
    except ImportError:  # pragma: no cover
        from workbook_export import _survey_where
    where, params = _survey_where(project_name, client, survey_year)
    own = conn is None
    if own:
        import paths
        conn = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
    try:
        return conn.execute(
            f"""SELECT sub_location, species_tvk, species_name, COUNT(1)
                FROM assessment_records WHERE {where}
                GROUP BY sub_location, species_tvk, species_name""", params).fetchall()
    finally:
        if own:
            conn.close()


# ---- analysis ---------------------------------------------------------------

@dataclass
class CompRow:
    name: str
    records: int
    share_pct: float
    species: int
    key: int
    key_pct: float
    sqi: object = None                  # SQIResult from the analysis service
    below_threshold: bool = False

    def sqi_cells(self):
        """(scoring, SQI) -- the SQI withheld below Pantheon's 15 scoring species."""
        s = self.sqi
        n = getattr(s, "species_with_sqs", 0) or 0
        if s is None or not n:
            return 0, "-"
        if not getattr(s, "reliable", False):
            return n, f"({n} spp)"
        return n, int(round(s.sqi))


@dataclass
class CompartmentResult:
    rows: List[CompRow] = field(default_factory=list)       # compartments, most records first
    combined: Optional[CompRow] = None
    threshold_pct: float = 5

    @property
    def shown(self) -> bool:
        return len(self.rows) >= 2

    @property
    def flagged(self) -> List[CompRow]:
        return [r for r in self.rows if r.below_threshold]

    def table(self):
        """(heads, rows, notes) -- the one layout the screen and every export use."""
        t = f"{self.threshold_pct:g}%"
        out = []
        for r in self.rows + ([self.combined] if self.combined else []):
            scoring, sqi = r.sqi_cells()
            out.append([r.name, r.records, f"{r.share_pct:.1f}%", r.species, r.key,
                        f"{r.key_pct:.1f}%", scoring, sqi,
                        f"Below {t} of records" if r.below_threshold else ""])
        notes = [
            f"Compartments holding fewer than {t} of the survey's records are flagged: too few "
            "records for their figures to be compared with the others. Threshold set in "
            "compartment_config.json.",
            "Each compartment is analysed as its own species list, by the same rules as the "
            "survey. The Combined row is the survey's own figure: pooling is not averaging, so "
            "the combined SQI can exceed every compartment's. SQI is withheld below 15 "
            "scoring species and the count shown instead.",
        ]
        if any(r.name == NO_COMPARTMENT for r in self.rows):
            notes.append(f"{NO_COMPARTMENT}: records entered without a sub-location (compartment) "
                         "in Data Entry.")
        return list(HEADS), out, notes


def _pct(a, b) -> float:
    return round(a / b * 100, 1) if b else 0.0


def analyse_compartments(split: Dict[str, dict], analyse: Callable, combined=None,
                         threshold_pct: float = 5) -> CompartmentResult:
    """split: from split_records. analyse(tvks, names) -> an AnalysisResult (needs
    total_species, key_species_count, overall_sqi). combined: the survey's own
    AnalysisResult for the Combined row (None to analyse the pooled list here)."""
    total = sum(c["records"] for c in split.values())
    res = CompartmentResult(threshold_pct=threshold_pct)
    if len(split) < 2:                       # nothing to compare: skip the analyses
        res.rows = [CompRow(n, c["records"], _pct(c["records"], total), len(c["tvks"]), 0, 0.0)
                    for n, c in split.items()]
        return res

    def row(name, records, a, share):
        sp = getattr(a, "total_species", 0) or 0
        key = getattr(a, "key_species_count", 0) or 0
        return CompRow(name, records, share, sp, key, _pct(key, sp),
                       getattr(a, "overall_sqi", None))

    for name, c in split.items():
        a = analyse(list(c["tvks"]), dict(c["names"])) if c["tvks"] else None
        r = row(name, c["records"], a, _pct(c["records"], total))
        r.below_threshold = r.share_pct < threshold_pct
        res.rows.append(r)
    res.rows.sort(key=lambda r: (r.name == NO_COMPARTMENT, -r.records, r.name))

    if combined is None:
        names = {}
        for c in split.values():
            names.update(c["names"])
        combined = analyse(list(names), names)
    res.combined = row(COMBINED, total, combined, 100.0)
    return res


def for_detail(result, detail, project, jurisdiction="England", service=None, conn=None):
    """The compartment analysis for the current survey, computed once and cached on the
    SiteDetail. None for an imported list (no records) or if it cannot be computed."""
    if detail is None:
        return None
    key = (getattr(result, "mode", ""), jurisdiction, id(result))
    cached = getattr(detail, "compartments", None)
    if cached is not None and getattr(detail, "_compartments_key", None) == key:
        return cached
    site = getattr(detail, "site", None)
    name = getattr(project, "project_name", "") or getattr(site, "project_name", "")
    if not name:
        return None
    client = getattr(project, "client", "") or getattr(site, "client", "")
    year = (getattr(project, "survey_year", "") if project is not None
            else getattr(site, "survey_year", "")) or None
    split = split_records(load_rows(name, client, year, conn))
    if service is None and len(split) >= 2:
        service = _default_service()
    try:
        from shared.repositories.codex_repository import AnalysisMode
        mode = AnalysisMode(getattr(result, "mode", "codex_full"))
    except Exception:  # noqa: BLE001
        mode = None

    def analyse(tvks, names):
        if mode is None:
            return service.analyse(tvks, names)
        try:
            return service.analyse(tvks, names, mode, jurisdiction)
        except TypeError:
            return service.analyse(tvks, names, mode)

    res = analyse_compartments(split, analyse, combined=result,
                               threshold_pct=float(config()["min_share_pct"]))
    try:
        detail.compartments = res
        detail._compartments_key = key
    except AttributeError:  # pragma: no cover
        pass
    return res


def _default_service():
    from shared.repositories.codex_repository import CodexRepository
    from shared.repositories.pantheon_repository import PantheonRepository
    from shared.services.pantheon_analysis_service import PantheonAnalysisService
    return PantheonAnalysisService(PantheonRepository(), CodexRepository())
