"""
Pantheon Analysis Service (v3 — mode-aware)

Supports AnalysisMode.CODEX_FULL and AnalysisMode.PANTHEON_ONLY.
Ecology (biotopes, habitats, SATs, guilds) always from Pantheon.
Conservation + SQS from Codex in the selected mode.

Usage:
    service = PantheonAnalysisService(pantheon_repo, codex_repo)
    result = service.analyse(tvks)                                # enriched
    result = service.analyse(tvks, mode=AnalysisMode.PANTHEON_ONLY)  # strict
    comparison = service.compare(tvks)                             # side-by-side
"""

from dataclasses import dataclass, field
from collections import Counter

try:
    from shared.repositories.codex_repository import AnalysisMode
except ImportError:
    from enum import Enum
    class AnalysisMode(Enum):
        CODEX_FULL = "codex_full"
        PANTHEON_ONLY = "pantheon_only"


@dataclass
class SQIResult:
    label: str
    species_total: int = 0
    species_with_sqs: int = 0
    sqs_sum: int = 0
    sqi: float = 0.0
    reliable: bool = True

    def calculate(self):
        if self.species_with_sqs > 0:
            self.sqi = round(self.sqs_sum / self.species_with_sqs * 100)
        self.reliable = self.species_with_sqs >= 15


@dataclass
class KeySpeciesEntry:
    tvk: str
    species_name: str
    family: str
    status_display: str
    short_status: str
    tier: str
    sqs: int
    broad_biotope: str
    habitat: str


@dataclass
class AnalysisResult:
    total_species: int = 0
    species_in_pantheon: int = 0
    species_with_sqs: int = 0
    mode: str = "codex_full"

    overall_sqi: SQIResult = None
    biotope_sqi: list = field(default_factory=list)
    habitat_sqi: list = field(default_factory=list)
    sat_sqi: list = field(default_factory=list)

    key_species: list = field(default_factory=list)
    key_species_count: int = 0
    key_species_pct: float = 0.0
    rare_count: int = 0
    scarce_count: int = 0
    priority_count: int = 0

    biotope_counts: dict = field(default_factory=dict)
    habitat_counts: dict = field(default_factory=dict)
    sat_counts: dict = field(default_factory=dict)
    larval_guild_counts: dict = field(default_factory=dict)
    adult_guild_counts: dict = field(default_factory=dict)


@dataclass
class ComparisonResult:
    codex: AnalysisResult = None
    pantheon: AnalysisResult = None
    sqi_delta: int = 0
    key_count_delta: int = 0
    key_pct_delta: float = 0.0
    sqs_species_delta: int = 0
    codex_only_key: list = field(default_factory=list)


class PantheonAnalysisService:

    def __init__(self, pantheon_repo, codex_repo=None):
        self._pantheon = pantheon_repo
        self._codex = codex_repo

    def analyse(self, tvks, species_names=None,
                mode=AnalysisMode.CODEX_FULL):
        if not tvks:
            return AnalysisResult()

        unique_tvks = list(set(tvks))
        names = species_names or {}
        result = AnalysisResult(total_species=len(unique_tvks), mode=mode.value)

        # Conservation + SQS (mode-dependent)
        if self._codex:
            sqs_scores = self._codex.get_sqs_scores(unique_tvks, mode)
            codex_statuses = self._codex.get_statuses_batch(unique_tvks, mode)
        else:
            sqs_scores = self._pantheon.get_sqs_scores(unique_tvks)
            codex_statuses = None

        # Ecology (always Pantheon, mode-independent)
        biotopes = self._pantheon.get_broad_biotopes(unique_tvks)
        habitats = self._pantheon.get_habitats(unique_tvks)
        sats = self._pantheon.get_sats(unique_tvks)
        guilds = self._pantheon.get_feeding_guilds(unique_tvks)

        result.species_in_pantheon = len(
            set(sqs_scores.keys()) | set(biotopes.keys())
        )
        result.species_with_sqs = len(sqs_scores)

        # SQI
        result.overall_sqi = self._calc_sqi("Overall", unique_tvks, sqs_scores)

        for label, tvk_set in self._group_by(biotopes).items():
            result.biotope_sqi.append(self._calc_sqi(label, tvk_set, sqs_scores))
        result.biotope_counts = {b: len(s) for b, s in self._group_by(biotopes).items()}

        for label, tvk_set in self._group_by(habitats).items():
            result.habitat_sqi.append(self._calc_sqi(label, tvk_set, sqs_scores))
        result.habitat_counts = {h: len(s) for h, s in self._group_by(habitats).items()}

        for label, tvk_set in self._group_by(sats).items():
            result.sat_sqi.append(self._calc_sqi(label, tvk_set, sqs_scores))
        result.sat_counts = {s: len(t) for s, t in self._group_by(sats).items()}

        # Key species
        if codex_statuses:
            for tvk in unique_tvks:
                cs = codex_statuses.get(tvk)
                if not cs or not cs.is_key:
                    continue
                sp_name = names.get(tvk, "")
                family = ""
                if not sp_name:
                    profile = self._pantheon.get_species_profile(tvk)
                    if profile:
                        sp_name = profile.species_name
                        family = profile.family
                tvk_bios = biotopes.get(tvk, [])
                tvk_habs = habitats.get(tvk, [])
                result.key_species.append(KeySpeciesEntry(
                    tvk=tvk, species_name=sp_name, family=family,
                    status_display=cs.display_status,
                    short_status=cs.short_status,
                    tier=cs.tier.value, sqs=cs.sqs,
                    broad_biotope=", ".join(tvk_bios[:2]),
                    habitat=", ".join(tvk_habs[:2]),
                ))
        else:
            statuses = self._pantheon.get_conservation_statuses(unique_tvks)
            for tvk in unique_tvks:
                status = statuses.get(tvk, "")
                if not status or status in ("None", "Unknown", "Not reviewed"):
                    continue
                profile = self._pantheon.get_species_profile(tvk)
                if not profile:
                    continue
                result.key_species.append(KeySpeciesEntry(
                    tvk=tvk, species_name=names.get(tvk, profile.species_name),
                    family=profile.family, status_display=profile.gb_status,
                    short_status=profile.gb_status, tier="Scarce",
                    sqs=profile.sqs,
                    broad_biotope=", ".join(profile.broad_biotopes[:2]),
                    habitat=", ".join(profile.habitats[:2]),
                ))

        result.key_species.sort(key=lambda k: (-k.sqs, k.species_name))
        result.key_species_count = len(result.key_species)
        result.rare_count = sum(1 for k in result.key_species if k.tier == "Rare")
        result.scarce_count = sum(1 for k in result.key_species if k.tier == "Scarce")
        result.priority_count = sum(1 for k in result.key_species if k.tier == "Priority")

        if result.species_in_pantheon > 0:
            result.key_species_pct = round(
                result.key_species_count / result.species_in_pantheon * 100, 1)

        # Guilds
        larval = Counter()
        adult = Counter()
        for tvk, g in guilds.items():
            if "larval guild" in g and g["larval guild"]:
                larval[g["larval guild"]] += 1
            if "adult guild" in g and g["adult guild"]:
                adult[g["adult guild"]] += 1
        result.larval_guild_counts = dict(larval.most_common())
        result.adult_guild_counts = dict(adult.most_common())

        return result

    def compare(self, tvks, species_names=None):
        c = self.analyse(tvks, species_names, AnalysisMode.CODEX_FULL)
        p = self.analyse(tvks, species_names, AnalysisMode.PANTHEON_ONLY)
        p_tvks = {k.tvk for k in p.key_species}
        codex_only = [k for k in c.key_species if k.tvk not in p_tvks]
        c_sqi = c.overall_sqi.sqi if c.overall_sqi else 0
        p_sqi = p.overall_sqi.sqi if p.overall_sqi else 0
        return ComparisonResult(
            codex=c, pantheon=p,
            sqi_delta=c_sqi - p_sqi,
            key_count_delta=c.key_species_count - p.key_species_count,
            key_pct_delta=round(c.key_species_pct - p.key_species_pct, 1),
            sqs_species_delta=c.species_with_sqs - p.species_with_sqs,
            codex_only_key=codex_only,
        )

    def analyse_by_site(self, site_species, mode=AnalysisMode.CODEX_FULL):
        return {site: self.analyse(tvks, mode=mode)
                for site, tvks in site_species.items()}

    def _calc_sqi(self, label, tvks_or_set, sqs_scores):
        tvk_set = tvks_or_set if isinstance(tvks_or_set, set) else set(tvks_or_set)
        sqi = SQIResult(label=label)
        sqi.species_total = len(tvk_set)
        for tvk in tvk_set:
            if tvk in sqs_scores:
                sqi.species_with_sqs += 1
                sqi.sqs_sum += sqs_scores[tvk]
        sqi.calculate()
        return sqi

    def _group_by(self, multi_dict):
        groups = {}
        for tvk, values in multi_dict.items():
            for v in values:
                groups.setdefault(v, set()).add(tvk)
        return groups
