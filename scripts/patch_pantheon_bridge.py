"""patch_pantheon_bridge.py -- stop losing ecology for 3,666 re-keyed species.

    python scripts/patch_pantheon_bridge.py

The fault
---------
pantheon.db is keyed on Pantheon's 2017 TVKs. Codex, Observatum and Examen all
work in current UKSI TVKs. The tvk_bridge table exists to translate between
them -- and it is consulted for SQS scores and for nothing else.

Every ecology lookup passes UKSI TVKs straight to a Pantheon-keyed table:

    PantheonRepository.get_broad_biotopes(tvks)
    PantheonRepository.get_habitats(tvks)
    PantheonRepository.get_sats(tvks)
    PantheonRepository.get_feeding_guilds(tvks)
    PantheonRepository.get_fidelity_scores(tvks)
    PantheonRepository.get_species_profile(tvk)

For the 8,648 species whose Pantheon TVK is already the current one, that
works. For the **3,666 resolved by name or synonym it silently returns
nothing** -- of 400 sampled, zero were found in pantheon.habitats.

Visible symptom: species carrying an SQS but no Broad Biotope and no Habitat in
the Glory Park appendix -- Larinus carlinae, Hylaeus cornutus and others. Less
visible: habitat and SAT SQIs, biotope breakdowns and the "dominant biotopes"
line have been computed over the directly-matched species only, in every
assessment the tool has produced.

The fix
-------
PantheonRepository becomes bridge-aware. It loads tvk_bridge from codex.db once,
translates incoming UKSI TVKs to Pantheon TVKs, and maps the results back, so
every caller is fixed at once and none has to know the bridge exists.

Pantheon's data is Pantheon-keyed, so a repository that reads it should
understand Pantheon's keys -- the coupling to codex.db is honest. It degrades to
the previous behaviour if the bridge is unavailable, and `use_bridge=False`
disables it for anyone genuinely holding Pantheon TVKs.

Note: several Pantheon TVKs can map to one UKSI TVK (the 1,847 collisions of
backlog J2). Ecology is UNIONED across them, which is the merge rule already
agreed -- union the ecology, incumbent wins on SQS.

Safe to re-run. Backs up as pantheon_repository.py.bak_fix1.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "shared", "repositories", "pantheon_repository.py")
BACKUP = TARGET + ".bak_fix1"

OLD_INIT = '''    def __init__(self, db_path: str = None):
        self._db_path = str(db_path or DB_PATH)
        self._conn = None'''

NEW_INIT = '''    def __init__(self, db_path: str = None, use_bridge: bool = True):
        self._db_path = str(db_path or DB_PATH)
        self._conn = None
        # pantheon.db is keyed on 2017 TVKs; callers hold current UKSI TVKs.
        # Without translation, every species re-keyed by name or synonym
        # returns no ecology at all -- 3,666 of them. See
        # patch_pantheon_bridge.py.
        self._use_bridge = use_bridge
        self._uksi_to_pan = None    # {uksi_tvk: [pantheon_tvk, ...]}
        self._pan_to_uksi = None    # {pantheon_tvk: uksi_tvk}'''

OLD_CLOSE = '''    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None'''

NEW_CLOSE = '''    def close(self):
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
        return self._pan_to_uksi.get(pan_tvk, pan_tvk)'''

# --- single-species profile ---------------------------------------------
OLD_PROFILE = '''    def get_species_profile(self, tvk: str) -> SpeciesProfile:
        """Get complete Pantheon profile for a species."""
        c = self._get_conn().cursor()

        c.execute("SELECT species_name, family FROM species WHERE tvk = ?", (tvk,))
        row = c.fetchone()
        if not row:
            return None

        profile = SpeciesProfile(tvk=tvk, species_name=row["species_name"],
                                  family=row["family"] or "")'''

NEW_PROFILE = '''    def get_species_profile(self, tvk: str) -> SpeciesProfile:
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
                                  family=row["family"] or "")'''

# --- batch helpers -------------------------------------------------------
OLD_MULTI = '''    def _get_multi(self, tvks, table, column):
        if not tvks:
            return {}
        c = self._get_conn().cursor()
        result = {}
        for batch in _chunked(tvks, 500):
            placeholders = ",".join("?" * len(batch))
            c.execute(f"SELECT tvk, {column} FROM {table} WHERE tvk IN ({placeholders})", batch)
            for r in c.fetchall():
                result.setdefault(r["tvk"], []).append(r[column])
        return result'''

NEW_MULTI = '''    def _get_multi(self, tvks, table, column):
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
        return result'''

OLD_SQS = '''    def get_sqs_scores(self, tvks: list) -> dict:
        """Get SQS scores for a list of TVKs. Returns {tvk: sqs}."""
        if not tvks:
            return {}
        c = self._get_conn().cursor()
        result = {}
        for batch in _chunked(tvks, 500):
            placeholders = ",".join("?" * len(batch))
            c.execute(f"SELECT tvk, sqs FROM sqs_scores WHERE tvk IN ({placeholders})", batch)
            for r in c.fetchall():
                result[r["tvk"]] = r["sqs"]
        return result'''

NEW_SQS = '''    def get_sqs_scores(self, tvks: list) -> dict:
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
        return result'''

OLD_CONS = '''        for batch in _chunked(tvks, 500):
            placeholders = ",".join("?" * len(batch))
            c.execute(f"""SELECT tvk, abbreviation FROM conservation_status
                         WHERE tvk IN ({placeholders}) AND reporting_category = 'GB Status'
                         AND abbreviation NOT IN ('None', 'Unknown', 'Not reviewed')""",
                      batch)
            for r in c.fetchall():
                if r["tvk"] not in result:
                    result[r["tvk"]] = r["abbreviation"]
        return result'''

NEW_CONS = '''        for batch in _chunked(self._to_pantheon(tvks), 500):
            placeholders = ",".join("?" * len(batch))
            c.execute(f"""SELECT tvk, abbreviation FROM conservation_status
                         WHERE tvk IN ({placeholders}) AND reporting_category = 'GB Status'
                         AND abbreviation NOT IN ('None', 'Unknown', 'Not reviewed')""",
                      batch)
            for r in c.fetchall():
                key = self._back(r["tvk"])
                if key not in result:
                    result[key] = r["abbreviation"]
        return result'''

OLD_GUILDS = '''        for batch in _chunked(tvks, 500):
            placeholders = ",".join("?" * len(batch))
            c.execute(f"SELECT tvk, life_stage, guild FROM feeding_guilds WHERE tvk IN ({placeholders})", batch)
            for r in c.fetchall():
                result.setdefault(r["tvk"], {})[r["life_stage"]] = r["guild"]
        return result'''

NEW_GUILDS = '''        for batch in _chunked(self._to_pantheon(tvks), 500):
            placeholders = ",".join("?" * len(batch))
            c.execute(f"SELECT tvk, life_stage, guild FROM feeding_guilds WHERE tvk IN ({placeholders})", batch)
            for r in c.fetchall():
                result.setdefault(self._back(r["tvk"]), {})[r["life_stage"]] = r["guild"]
        return result'''

OLD_FID = '''        for batch in _chunked(tvks, 500):
            placeholders = ",".join("?" * len(batch))
            if index_name:
                c.execute(f"""SELECT tvk, index_name, score FROM fidelity_scores
                             WHERE tvk IN ({placeholders}) AND index_name = ?""",
                          batch + [index_name])
            else:
                c.execute(f"SELECT tvk, index_name, score FROM fidelity_scores WHERE tvk IN ({placeholders})", batch)
            for r in c.fetchall():
                result.setdefault(r["tvk"], {})[r["index_name"]] = r["score"]
        return result'''

NEW_FID = '''        for batch in _chunked(self._to_pantheon(tvks), 500):
            placeholders = ",".join("?" * len(batch))
            if index_name:
                c.execute(f"""SELECT tvk, index_name, score FROM fidelity_scores
                             WHERE tvk IN ({placeholders}) AND index_name = ?""",
                          batch + [index_name])
            else:
                c.execute(f"SELECT tvk, index_name, score FROM fidelity_scores WHERE tvk IN ({placeholders})", batch)
            for r in c.fetchall():
                result.setdefault(self._back(r["tvk"]), {})[r["index_name"]] = r["score"]
        return result'''

EDITS = [
    ("__init__ bridge state", OLD_INIT, NEW_INIT),
    ("bridge loader + translators", OLD_CLOSE, NEW_CLOSE),
    ("get_species_profile", OLD_PROFILE, NEW_PROFILE),
    ("_get_multi (biotopes/habitats/SATs)", OLD_MULTI, NEW_MULTI),
    ("get_sqs_scores", OLD_SQS, NEW_SQS),
    ("get_conservation_statuses", OLD_CONS, NEW_CONS),
    ("get_feeding_guilds", OLD_GUILDS, NEW_GUILDS),
    ("get_fidelity_scores", OLD_FID, NEW_FID),
]


def main():
    if not os.path.exists(TARGET):
        print(f"NOT FOUND: {TARGET}")
        print("  (the small file under Observatum/src/repositories is the shim)")
        return 1
    with open(TARGET, "r", encoding="utf-8") as f:
        text = f.read()

    print("")
    print("Patching pantheon_repository.py -- bridge-aware ecology lookups")
    print("=" * 70)

    if "_to_pantheon" in text:
        print("  = already patched -- nothing to do")
        return 0

    failed = 0
    for label, old, new in EDITS:
        n = text.count(old)
        if n == 1:
            text = text.replace(old, new)
            print(f"  + {label}")
        else:
            print(f"  x {label}  ({n} matches, expected 1)")
            failed += 1

    print("")
    if failed:
        print(f"  {failed} edit(s) failed -- NOTHING WRITTEN.")
        return 1

    shutil.copy2(TARGET, BACKUP)
    print(f"  backup written: {os.path.basename(BACKUP)}")
    with open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(text)

    print("")
    print("  Checking it compiles, imports, and actually bridges...")
    try:
        import py_compile
        py_compile.compile(TARGET, doraise=True)
        sys.path.insert(0, _ROOT)
        import importlib
        m = importlib.import_module("shared.repositories.pantheon_repository")
        importlib.reload(m)
        import sqlite3 as _sq
        import paths as _p
        cx = _sq.connect(f"file:{_p.CODEX_DB}?mode=ro", uri=True)
        sample = [r[0] for r in cx.execute(
            "SELECT uksi_tvk FROM tvk_bridge WHERE match_method='name' LIMIT 200")]
        cx.close()
        repo = m.PantheonRepository()
        hab = repo.get_habitats(sample)
        repo.close()
        print(f"  + imports cleanly")
        print(f"  + {len(hab)} of {len(sample)} re-keyed species now return habitats"
              f"  (was 0)")
    except Exception as e:  # noqa: BLE001
        print(f"  x FAILED: {type(e).__name__}: {e}")
        print(f"    restore: copy {os.path.basename(BACKUP)} pantheon_repository.py")
        return 1

    print("")
    print("  NEXT: python -m Examen -> Glory Park")
    print("  Larinus carlinae and the Hylaeus species should now carry a")
    print("  broad biotope and habitat. Species-in-Pantheon and the habitat")
    print("  SQIs will rise -- those figures were computed over the directly")
    print("  matched species only.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
