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


_HAB_BIO = None


def _habitat_biotopes():
    """{habitat: {biotope, ...}} from Pantheon's own hierarchy.

    habitat_traits holds the tree: each habitat row's parent_trait_id is its
    broad biotope. Wet woodland sits under both tree-associated and wetland.
    Cached. Empty if pantheon.db cannot be read -- pairing then falls back to
    every combination rather than failing.
    """
    global _HAB_BIO
    if _HAB_BIO is not None:
        return _HAB_BIO
    out = {}
    try:
        import sqlite3
        import paths
        c = sqlite3.connect(f"file:{paths.PANTHEON_DB}?mode=ro", uri=True)
        bio_names = {str(tid): str(name).strip().lower() for tid, name in c.execute(
            "SELECT DISTINCT trait_id, trait_name FROM habitat_traits "
            "WHERE trait_type = 'broad biotope'")}
        for name, parent in c.execute(
                "SELECT DISTINCT trait_name, parent_trait_id FROM habitat_traits "
                "WHERE trait_type = 'habitat'"):
            bio = bio_names.get(str(parent))
            if bio:
                out.setdefault(str(name).strip().lower(), set()).add(bio)
        c.close()
    except Exception:
        out = {}
    _HAB_BIO = out
    return out


@dataclass
class SQIResult:
    label: str
    species_total: int = 0
    species_with_sqs: int = 0
    sqs_sum: int = 0
    sqi: float = 0.0
    reliable: bool = True
    species_analysed: int = 0     # Pantheon's denominator

    def calculate(self):
        if self.species_with_sqs > 0:
            # Pantheon's definition: divide by every species analysed, scored
            # or not (Glory Park: 144 / 123 = 117, the issued report).
            _denom = self.species_analysed or self.species_with_sqs
            self.sqi = round(self.sqs_sum / _denom * 100)
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

    # Structured tracks, so consumers do not have to parse display strings.
    # Empty by default -- PANTHEON_ONLY mode fills only `rarity`.
    rarity: str = ""
    threat: str = ""
    threat_legacy: str = ""
    priority: list = field(default_factory=list)
    legal: list = field(default_factory=list)
    # "status held at sensu lato" when the status is the broad group's, not the
    # species' own; RECORDED_SL_SS when the survey recorded both TVKs.
    status_note: str = ""
    recorded_note: str = ""


# The note a report gives a species recorded under its own TVK and its s.l. /
# aggregate counterpart, counted once (EXA14).
RECORDED_SL_SS = "recorded as s.l. and s.s."


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

    # The jurisdiction the key-species filter used. Carried on the result so a
    # report can state it: S41 confers key status in England, the Scottish
    # Biodiversity List does not, and the figure is meaningless without saying
    # which rule produced it.
    jurisdiction: str = "England"

    key_species: list = field(default_factory=list)
    key_species_count: int = 0
    key_species_pct: float = 0.0
    rare_count: int = 0
    scarce_count: int = 0
    priority_count: int = 0

    biotope_counts: dict = field(default_factory=dict)
    habitat_counts: dict = field(default_factory=dict)
    sat_counts: dict = field(default_factory=dict)

    # Real pairs from THIS sample -- {biotope: {habitat: count}} and the
    # matching SQI per pair. Without these the habitat tree is a cross-product
    # of every pair in Pantheon, carrying site-wide counts.
    biotope_habitat_counts: dict = field(default_factory=dict)
    biotope_habitat_sqi: dict = field(default_factory=dict)
    larval_guild_counts: dict = field(default_factory=dict)
    adult_guild_counts: dict = field(default_factory=dict)
    # SQS basis (patch_sqs_basis.py): which scores were derived from the rule
    # rather than published by Pantheon, the SQI on Pantheon's scores alone, and
    # species Pantheon holds no data for at all.
    derived_sqs_tvks: set = field(default_factory=set)
    overall_sqi_published: object = None
    no_pantheon_tvks: set = field(default_factory=set)

    # "Analysed" (EXA5): species_in_pantheon is the species Pantheon holds (any
    # ecology or SQS row through the bridge); species_analysed is the SQI's
    # divisor -- those plus any species scored from current status only.
    species_analysed: int = 0
    in_pantheon_tvks: set = field(default_factory=set)
    # Distinct species in at least one SAT (EXA4) -- not the sum of sat_counts.
    stenotopic_count: int = 0
    # {broad_tvk: species_tvk}: one species recorded under two TVKs (EXA14).
    merged_tvks: dict = field(default_factory=dict)
    # Per-species figures after the merge, for the species list.
    sqs_by_tvk: dict = field(default_factory=dict)
    statuses: dict = field(default_factory=dict)
    biotopes_by_tvk: dict = field(default_factory=dict)
    habitats_by_tvk: dict = field(default_factory=dict)
    sats_by_tvk: dict = field(default_factory=dict)


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
                mode=AnalysisMode.CODEX_FULL, jurisdiction="England"):
        """Analyse a species list.

        jurisdiction  which country's rules decide key status. Section 41 is
                      England's list, made under English law; a Scottish
                      Ministers' list carries no weight in an English planning
                      determination, and the reverse. Rarity and threat are
                      GB-wide and unaffected.

        One species recorded under two TVKs -- the species and its sensu-lato /
        aggregate counterpart (EXA14) -- is counted once, under the species TVK:
        ecology unioned, the stronger status, the species' own SQS else the
        counterpart's (J2: the species is the incumbent). result.merged_tvks
        records {broad_tvk: species_tvk}. Different species stay separate.
        """
        if not tvks:
            return AnalysisResult(jurisdiction=jurisdiction)

        all_tvks = list(dict.fromkeys(t for t in tvks if t))
        names = species_names or {}
        merged = {}
        if self._codex is not None and hasattr(self._codex, "sensu_lato_pairs"):
            merged = self._codex.sensu_lato_pairs(all_tvks)
        unique_tvks = [t for t in all_tvks if t not in merged]
        result = AnalysisResult(total_species=len(unique_tvks), mode=mode.value,
                                jurisdiction=jurisdiction)
        result.merged_tvks = dict(merged)

        # Conservation + SQS (mode-dependent)
        if self._codex:
            sqs_scores = self._codex.get_sqs_scores(all_tvks, mode)
            try:
                codex_statuses = self._codex.get_statuses_batch(
                    all_tvks, mode, jurisdiction)
            except TypeError:
                # Older CodexRepository without the jurisdiction parameter.
                codex_statuses = self._codex.get_statuses_batch(all_tvks, mode)
        else:
            sqs_scores = self._pantheon.get_sqs_scores(all_tvks)
            codex_statuses = None

        # Ecology (always Pantheon, mode-independent)
        biotopes = self._pantheon.get_broad_biotopes(all_tvks)
        habitats = self._pantheon.get_habitats(all_tvks)
        sats = self._pantheon.get_sats(all_tvks)
        guilds = self._pantheon.get_feeding_guilds(all_tvks)
        held = (self._pantheon.held_by_pantheon(all_tvks)
                if hasattr(self._pantheon, "held_by_pantheon")
                else set(sqs_scores) | set(biotopes) | set(habitats))

        # Which scores Pantheon published, which were derived from the rule (Codex
        # Full gap-fill). Both bases are reported; neither is hidden. (Decision 7.)
        derived = set()
        if self._codex is not None and hasattr(self._codex, "get_stored_sqs_tvks") \
                and mode != AnalysisMode.PANTHEON_ONLY:
            derived = set(sqs_scores) - self._codex.get_stored_sqs_tvks(all_tvks)

        # Fold each broad-group TVK into its species (EXA14).
        for broad, sp in merged.items():
            for d in (biotopes, habitats, sats):
                vals = list(d.get(sp, []))
                vals += [v for v in d.pop(broad, []) if v not in vals]
                if vals:
                    d[sp] = vals
            g = dict(guilds.get(sp, {}))
            for stage, guild in guilds.pop(broad, {}).items():
                if not g.get(stage):
                    g[stage] = guild
            if g:
                guilds[sp] = g
            # J2 with the species as incumbent: its published score, else the
            # broad group's published score; a derived score only where neither
            # has one (derived is a gap-fill, never a rival to a published score).
            pick = next((t for t in (sp, broad) if t in sqs_scores and t not in derived),
                        next((t for t in (sp, broad) if t in sqs_scores), None))
            if pick is not None:
                sqs_scores[sp] = sqs_scores[pick]
                if pick in derived:
                    derived.add(sp)
                else:
                    derived.discard(sp)
            sqs_scores.pop(broad, None)
            derived.discard(broad)
            if broad in held:
                held.add(sp)
            held.discard(broad)
            if codex_statuses:
                try:
                    from shared.repositories.codex_repository import stronger_status
                except ImportError:  # pragma: no cover
                    stronger_status = lambda a, b: a  # noqa: E731
                codex_statuses[sp] = stronger_status(codex_statuses.get(sp),
                                                     codex_statuses.pop(broad, None))

        result.derived_sqs_tvks = derived
        result.sqs_by_tvk = dict(sqs_scores)
        result.statuses = codex_statuses or {}
        result.biotopes_by_tvk, result.habitats_by_tvk = biotopes, habitats
        result.sats_by_tvk = sats

        # "Analysed" -- ONE definition (EXA5). Species Pantheon holds (any
        # ecology or SQS row, through the bridge) are "in Pantheon"; the SQI
        # divides by those plus any species scored from current status, so a
        # score in the numerator always has its species in the denominator and
        # scoring <= analysed. Pantheon's definition (Glory Park 144 / 123 = 117).
        result.in_pantheon_tvks = held & set(unique_tvks)
        result.species_in_pantheon = len(result.in_pantheon_tvks)
        pool = result.in_pantheon_tvks | set(sqs_scores)
        result.species_analysed = len(pool)
        result.species_with_sqs = len(sqs_scores)
        result.no_pantheon_tvks = set(unique_tvks) - result.in_pantheon_tvks
        result.overall_sqi_published = self._calc_sqi(
            "Overall (Pantheon scores)", unique_tvks,
            {t: s for t, s in sqs_scores.items() if t not in derived},
            pool=result.in_pantheon_tvks | (set(sqs_scores) - derived))

        # SQI
        result.overall_sqi = self._calc_sqi("Overall", unique_tvks, sqs_scores, pool)

        for label, tvk_set in self._group_by(biotopes).items():
            result.biotope_sqi.append(self._calc_sqi(label, tvk_set, sqs_scores, pool))
        result.biotope_counts = {b: len(s) for b, s in self._group_by(biotopes).items()}

        for label, tvk_set in self._group_by(habitats).items():
            result.habitat_sqi.append(self._calc_sqi(label, tvk_set, sqs_scores, pool))
        result.habitat_counts = {h: len(s) for h, s in self._group_by(habitats).items()}

        # Biotope x habitat, per species -- only pairs this sample actually
        # holds, each with its own species set.
        pairs = {}
        for tvk in unique_tvks:
            for bio in biotopes.get(tvk, []):
                for hab in habitats.get(tvk, []):
                    # Pantheon places each habitat under its own biotope(s): decaying wood is
                    # tree-associated, never open habitats. Skip pairings Pantheon does not make.
                    _home = _habitat_biotopes().get(str(hab).lower())
                    if _home and str(bio).lower() not in _home:
                        continue
                    pairs.setdefault(bio, {}).setdefault(hab, set()).add(tvk)
        result.biotope_habitat_counts = {
            bio: {hab: len(tvks_) for hab, tvks_ in habs.items()}
            for bio, habs in pairs.items()}
        result.biotope_habitat_sqi = {
            bio: {hab: self._calc_sqi(f"{bio} / {hab}", tvks_, sqs_scores, pool)
                  for hab, tvks_ in habs.items()}
            for bio, habs in pairs.items()}

        for label, tvk_set in self._group_by(sats).items():
            result.sat_sqi.append(self._calc_sqi(label, tvk_set, sqs_scores, pool))
        result.sat_counts = {s: len(t) for s, t in self._group_by(sats).items()}
        # Stenotopic species: each species once, however many SATs it is in (EXA4).
        result.stenotopic_count = len({t for t, v in sats.items() if v})

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
                    tier=cs.tier.value, sqs=sqs_scores.get(tvk, 0),
                    broad_biotope=", ".join(tvk_bios[:2]),
                    habitat=", ".join(tvk_habs[:2]),
                    rarity=(cs.rarity_modern.value if cs.rarity_modern
                            else (cs.rarity_legacy.value if cs.rarity_legacy else "")),
                    threat=(cs.threat_iucn_2001.value if cs.threat_iucn_2001 else ""),
                    threat_legacy=(cs.threat_iucn_legacy.value
                                   if cs.threat_iucn_legacy else ""),
                    priority=[e.value for e in (cs.priority or [])],
                    legal=[(e.detail or e.value) for e in (cs.legal_protection or [])],
                    status_note=getattr(cs, "status_note", "") or "",
                    recorded_note=(RECORDED_SL_SS if tvk in merged.values() else ""),
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
                    rarity=profile.gb_status or "",
                ))

        result.key_species.sort(key=lambda k: (-k.sqs, k.species_name))
        result.key_species_count = len(result.key_species)
        result.rare_count = sum(1 for k in result.key_species if k.tier == "Rare")
        result.scarce_count = sum(1 for k in result.key_species if k.tier == "Scarce")
        result.priority_count = sum(1 for k in result.key_species if k.tier == "Priority")

        # Denominator is total species recorded, not species Pantheon knows.
        # Wil's reports: "34 ... equates to 7.8% of the species from the
        # survey" = 34/433, where Pantheon analysed only 414 of them.
        # species_in_pantheon remains available on the result for display.
        if result.total_species > 0:
            result.key_species_pct = round(
                result.key_species_count / result.total_species * 100, 1)

        # Guilds
        # Pantheon stores Herbivore/herbivore, Predator/predator,
        # Saprophagous/saprophagous and Unknown/unknown, so the raw string
        # would count each pair twice. Normalised to lower case, which is
        # Pantheon's predominant form. See patch_guild_casing.py.
        larval = Counter()
        adult = Counter()
        for tvk, g in guilds.items():
            if "larval guild" in g and g["larval guild"]:
                larval[g["larval guild"].strip().lower()] += 1
            if "adult guild" in g and g["adult guild"]:
                adult[g["adult guild"].strip().lower()] += 1
        result.larval_guild_counts = dict(larval.most_common())
        result.adult_guild_counts = dict(adult.most_common())

        return result

    def compare(self, tvks, species_names=None, jurisdiction="England"):
        c = self.analyse(tvks, species_names, AnalysisMode.CODEX_FULL, jurisdiction)
        p = self.analyse(tvks, species_names, AnalysisMode.PANTHEON_ONLY, jurisdiction)
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

    def _calc_sqi(self, label, tvks_or_set, sqs_scores, pool=None):
        """The one SQI calculation (EXA1): CodexRepository.compute_sqi, the
        project table and every export come here. `pool` is the species
        analysed; a scored species always counts as analysed."""
        tvk_set = tvks_or_set if isinstance(tvks_or_set, set) else set(tvks_or_set)
        sqi = SQIResult(label=label)
        sqi.species_total = len(tvk_set)
        pool = pool if pool is not None else set(sqs_scores)
        sqi.species_analysed = len({t for t in tvk_set if t in pool or t in sqs_scores})
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
