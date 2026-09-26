"""
Pantheon Repository — Data Access Layer

Provides query methods for pantheon.db. Read-only access to
conservation status, habitat traits, SQS scores, SATs, fidelity
scores, and associations for species matched by TVK.

Usage:
    repo = PantheonRepository()
    scores = repo.get_sqs_scores(['NBNSYS0000007302', ...])
    status = repo.get_conservation_status('NBNSYS0000007302')
"""

import sqlite3
import paths
from pathlib import Path
from dataclasses import dataclass, field


DB_PATH = paths.PANTHEON_DB


@dataclass
class SpeciesProfile:
    """Complete Pantheon profile for a single species."""
    tvk: str
    species_name: str
    family: str = ""
    sqs: int = 0
    gb_status: str = ""
    gb_red_list: str = ""
    section41: bool = False
    legal_protection: bool = False
    broad_biotopes: list = field(default_factory=list)
    habitats: list = field(default_factory=list)
    larval_guild: str = ""
    adult_guild: str = ""
    sats: list = field(default_factory=list)
    fidelity_scores: dict = field(default_factory=dict)
    associations: list = field(default_factory=list)


class PantheonRepository:
    """Read-only access to pantheon.db."""

    def __init__(self, db_path: str = None, use_bridge: bool = True):
        self._db_path = str(db_path or DB_PATH)
        self._conn = None
        # pantheon.db is keyed on 2017 TVKs; callers hold current UKSI TVKs.
        # Without translation, every species re-keyed by name or synonym
        # returns no ecology at all -- 3,666 of them. See
        # patch_pantheon_bridge.py.
        self._use_bridge = use_bridge
        self._uksi_to_pan = None    # {uksi_tvk: [pantheon_tvk, ...]}
        self._pan_to_uksi = None    # {pantheon_tvk: uksi_tvk}

    def _get_conn(self):
        if self._conn is None:
            if not Path(self._db_path).exists():
                raise FileNotFoundError(f"pantheon.db not found: {self._db_path}")
            self._conn = sqlite3.connect(self._db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # ================================================================
    # TVK bridge -- UKSI (current) <-> Pantheon (2017)
    # ================================================================

    def _load_bridge(self):
        """Load tvk_bridge from codex.db, once. Silent no-op if unavailable."""
        if self._uksi_to_pan is not None:
            return
        self._uksi_to_pan, self._pan_to_uksi = {}, {}
        if not self._use_bridge:
            return
        try:
            import paths as _paths
            if not Path(str(_paths.CODEX_DB)).exists():
                return
            cx = sqlite3.connect(f"file:{_paths.CODEX_DB}?mode=ro", uri=True)
            try:
                for pan_tvk, uksi_tvk in cx.execute(
                        "SELECT pantheon_tvk, uksi_tvk FROM tvk_bridge"):
                    self._uksi_to_pan.setdefault(uksi_tvk, []).append(pan_tvk)
                    self._pan_to_uksi[pan_tvk] = uksi_tvk
            finally:
                cx.close()
        except Exception:  # noqa: BLE001 -- degrade to unbridged behaviour
            self._uksi_to_pan, self._pan_to_uksi = {}, {}

    def _to_pantheon(self, tvks):
        """UKSI TVKs -> Pantheon TVKs to query with.

        A TVK not in the bridge is passed through unchanged, so callers already
        holding Pantheon TVKs still work. Several Pantheon taxa can map to one
        current species; all of them are queried and the results unioned.
        """
        self._load_bridge()
        if not self._uksi_to_pan:
            return list(tvks)
        out = []
        for t in tvks:
            mapped = self._uksi_to_pan.get(t)
            out.extend(mapped if mapped else [t])
        return out

    def _back(self, pan_tvk):
        """Pantheon TVK -> the UKSI TVK the caller asked about."""
        if not self._pan_to_uksi:
            return pan_tvk
        return self._pan_to_uksi.get(pan_tvk, pan_tvk)

    # ================================================================
    # Single species lookups
    # ================================================================

    def get_species_profile(self, tvk: str) -> SpeciesProfile:
        """Get complete Pantheon profile for a species.

        `tvk` may be a current UKSI TVK; it is translated via the bridge. Where
        several Pantheon taxa map to one current species, the first is used for
        the scalar fields -- see backlog J2 for the merge rule.
        """
        c = self._get_conn().cursor()

        lookup = tvk
        for cand in self._to_pantheon([tvk]):
            if c.execute("SELECT 1 FROM species WHERE tvk = ?", (cand,)).fetchone():
                lookup = cand
                break
        tvk = lookup

        c.execute("SELECT species_name, family FROM species WHERE tvk = ?", (tvk,))
        row = c.fetchone()
        if not row:
            return None

        profile = SpeciesProfile(tvk=self._back(tvk), species_name=row["species_name"],
                                  family=row["family"] or "")

        # SQS
        c.execute("SELECT sqs FROM sqs_scores WHERE tvk = ?", (tvk,))
        sqs_row = c.fetchone()
        if sqs_row:
            profile.sqs = sqs_row["sqs"]

        # Conservation status
        c.execute("""SELECT reporting_category, abbreviation
                     FROM conservation_status WHERE tvk = ?""", (tvk,))
        for sr in c.fetchall():
            cat = sr["reporting_category"]
            abbr = sr["abbreviation"]
            if cat == "GB Status" and not profile.gb_status:
                profile.gb_status = abbr
            elif cat == "GB Red List" and not profile.gb_red_list:
                profile.gb_red_list = abbr
            elif cat == "Section 41 Priority Species":
                profile.section41 = True
            elif cat == "Legal Protection":
                profile.legal_protection = True

        # Broad biotopes
        c.execute("SELECT biotope FROM broad_biotope WHERE tvk = ?", (tvk,))
        profile.broad_biotopes = [r["biotope"] for r in c.fetchall()]

        # Habitats
        c.execute("SELECT habitat FROM habitats WHERE tvk = ?", (tvk,))
        profile.habitats = [r["habitat"] for r in c.fetchall()]

        # Feeding guilds
        c.execute("SELECT life_stage, guild FROM feeding_guilds WHERE tvk = ?", (tvk,))
        for r in c.fetchall():
            if r["life_stage"] == "larval guild":
                profile.larval_guild = r["guild"] or ""
            elif r["life_stage"] == "adult guild":
                profile.adult_guild = r["guild"] or ""

        # SATs
        c.execute("SELECT sat_name FROM specific_assemblage_types WHERE tvk = ?", (tvk,))
        profile.sats = [r["sat_name"] for r in c.fetchall()]

        # Fidelity scores
        c.execute("SELECT index_name, score FROM fidelity_scores WHERE tvk = ?", (tvk,))
        profile.fidelity_scores = {r["index_name"]: r["score"] for r in c.fetchall()}

        # Associations
        c.execute("""SELECT associated_taxa_type, associated_taxa
                     FROM associations WHERE tvk = ?""", (tvk,))
        profile.associations = [(r["associated_taxa_type"], r["associated_taxa"])
                                 for r in c.fetchall()]

        return profile

    # ================================================================
    # Batch lookups (for analysis service)
    # ================================================================

    def get_sqs_scores(self, tvks: list) -> dict:
        """Get SQS scores for a list of TVKs. Returns {tvk: sqs}.

        Where several Pantheon taxa map to one current species, the highest
        score is kept -- this is a bare Pantheon lookup, distinct from Codex's
        merge rule (backlog J2).
        """
        if not tvks:
            return {}
        c = self._get_conn().cursor()
        result = {}
        for batch in _chunked(self._to_pantheon(tvks), 500):
            placeholders = ",".join("?" * len(batch))
            c.execute(f"SELECT tvk, sqs FROM sqs_scores WHERE tvk IN ({placeholders})", batch)
            for r in c.fetchall():
                key = self._back(r["tvk"])
                if r["sqs"] > result.get(key, 0):
                    result[key] = r["sqs"]
        return result

    def get_broad_biotopes(self, tvks: list) -> dict:
        """Get broad biotopes for TVKs. Returns {tvk: [biotope, ...]}."""
        return self._get_multi(tvks, "broad_biotope", "biotope")

    def get_habitats(self, tvks: list) -> dict:
        """Get habitats for TVKs. Returns {tvk: [habitat, ...]}."""
        return self._get_multi(tvks, "habitats", "habitat")

    def get_sats(self, tvks: list) -> dict:
        """Get SATs for TVKs. Returns {tvk: [sat_name, ...]}."""
        return self._get_multi(tvks, "specific_assemblage_types", "sat_name")

    def get_conservation_statuses(self, tvks: list) -> dict:
        """Get GB Status for TVKs. Returns {tvk: abbreviation}."""
        if not tvks:
            return {}
        c = self._get_conn().cursor()
        result = {}
        for batch in _chunked(self._to_pantheon(tvks), 500):
            placeholders = ",".join("?" * len(batch))
            c.execute(f"""SELECT tvk, abbreviation FROM conservation_status
                         WHERE tvk IN ({placeholders}) AND reporting_category = 'GB Status'
                         AND abbreviation NOT IN ('None', 'Unknown', 'Not reviewed')""",
                      batch)
            for r in c.fetchall():
                key = self._back(r["tvk"])
                if key not in result:
                    result[key] = r["abbreviation"]
        return result

    def get_feeding_guilds(self, tvks: list) -> dict:
        """Get feeding guilds. Returns {tvk: {life_stage: guild}}."""
        if not tvks:
            return {}
        c = self._get_conn().cursor()
        result = {}
        for batch in _chunked(self._to_pantheon(tvks), 500):
            placeholders = ",".join("?" * len(batch))
            c.execute(f"SELECT tvk, life_stage, guild FROM feeding_guilds WHERE tvk IN ({placeholders})", batch)
            for r in c.fetchall():
                result.setdefault(self._back(r["tvk"]), {})[r["life_stage"]] = r["guild"]
        return result

    def get_fidelity_scores(self, tvks: list, index_name: str = None) -> dict:
        """Get fidelity scores. Returns {tvk: {index: score}}."""
        if not tvks:
            return {}
        c = self._get_conn().cursor()
        result = {}
        for batch in _chunked(self._to_pantheon(tvks), 500):
            placeholders = ",".join("?" * len(batch))
            if index_name:
                c.execute(f"""SELECT tvk, index_name, score FROM fidelity_scores
                             WHERE tvk IN ({placeholders}) AND index_name = ?""",
                          batch + [index_name])
            else:
                c.execute(f"SELECT tvk, index_name, score FROM fidelity_scores WHERE tvk IN ({placeholders})", batch)
            for r in c.fetchall():
                result.setdefault(self._back(r["tvk"]), {})[r["index_name"]] = r["score"]
        return result

    def get_metadata(self) -> dict:
        """Get database metadata."""
        c = self._get_conn().cursor()
        c.execute("SELECT key, value FROM metadata")
        return {r["key"]: r["value"] for r in c.fetchall()}

    def get_species_count(self) -> int:
        c = self._get_conn().cursor()
        c.execute("SELECT COUNT(*) FROM species")
        return c.fetchone()[0]

    # ================================================================
    # Private helpers
    # ================================================================

    def _get_multi(self, tvks, table, column):
        """Batch multi-value lookup, keyed back to the caller's TVKs.

        Values are unioned where several Pantheon taxa map to one current
        species, and de-duplicated.
        """
        if not tvks:
            return {}
        c = self._get_conn().cursor()
        result = {}
        for batch in _chunked(self._to_pantheon(tvks), 500):
            placeholders = ",".join("?" * len(batch))
            c.execute(f"SELECT tvk, {column} FROM {table} WHERE tvk IN ({placeholders})", batch)
            for r in c.fetchall():
                key = self._back(r["tvk"])
                vals = result.setdefault(key, [])
                if r[column] not in vals:
                    vals.append(r[column])
        return result


def _chunked(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]
