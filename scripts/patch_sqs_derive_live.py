"""patch_sqs_derive_live.py -- stop storing gap-filled SQS; derive it on demand.

    python scripts/patch_sqs_derive_live.py

Then rebuild:  python scripts/build_codex_db.py
               python scripts/seed_codex.py

The problem
-----------
sqs_scores mixes two populations that are not the same kind of thing:

  * 4,971 PANTHEON scores -- a record of what Pantheon published. Worth
    storing, because one in five does not follow Pantheon's own rule, and
    reproducing them is what makes an SQI comparable with the literature.

  * 816 GAP-FILLED scores -- pure arithmetic over Codex statuses, no
    provenance. Nothing published them.

The gap-fill came from seed_codex.SQS_DEFAULTS, which is NOT Pantheon's rule.
It scores RDB3 at 16 "per Fowles original SQI" -- a different index -- and maps
single (track, value) pairs taking the maximum, where the published rule is a
function of rarity AND threat together (Nationally Rare with RDB K is capped at
4 by the rule, 8 under max-of-pairs).

Measured against shared/sqs_derivation.py: **525 of 816 (64%) disagree with the
published rule.** They sit in sqs_scores indistinguishable from Pantheon's
except by a `source` column nothing downstream is obliged to check.

The fix
-------
Derive on demand, from the published rule, against current Codex statuses:

  * seed_codex stops writing derived rows. sqs_scores becomes only what
    Pantheon published (plus any manual entries).
  * CodexRepository.get_sqs_scores falls back to shared.sqs_derivation for any
    invertebrate with no stored score.

Side effects, both wanted:
  * Infrastructure item 59 disappears -- there is no stored derived value left
    to drift between rebuilds.
  * CODEX_FULL vs PANTHEON_ONLY becomes an honest distinction rather than a
    blend of published and invented numbers.

The derivation queries status_summary directly rather than calling
get_statuses_batch, which would recurse (that method calls get_sqs_scores).

Safe to re-run. Backs up as .bak_sqslive alongside each file.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.join(_ROOT, "shared", "repositories", "codex_repository.py")
SEED = os.path.join(_ROOT, "scripts", "seed_codex.py")

# ---------------------------------------------------------------- repository
OLD_BATCH = '''    def get_sqs_scores(self, tvks, mode=AnalysisMode.CODEX_FULL):
        if not tvks:
            return {}
        if mode == AnalysisMode.PANTHEON_ONLY:
            return self._pantheon_sqs_batch(tvks)
        c = self._get_conn().cursor()
        result = {}
        for batch in _chunked(tvks, 500):
            ph = ",".join("?" * len(batch))
            c.execute(f"SELECT tvk, sqs FROM sqs_scores WHERE tvk IN ({ph})", batch)
            for row in c.fetchall():
                result[row["tvk"]] = row["sqs"]
        return result'''

NEW_BATCH = '''    def get_sqs_scores(self, tvks, mode=AnalysisMode.CODEX_FULL):
        """SQS per TVK: what Pantheon published, else derived from the rule.

        Stored scores are Pantheon's own (and any manual entries) -- a record
        of what was published, which is what makes an SQI comparable. Where
        Pantheon has no score, the published rule is applied to current Codex
        statuses instead of storing an invented value. See
        patch_sqs_derive_live.py.
        """
        if not tvks:
            return {}
        if mode == AnalysisMode.PANTHEON_ONLY:
            return self._pantheon_sqs_batch(tvks)
        c = self._get_conn().cursor()
        result = {}
        for batch in _chunked(tvks, 500):
            ph = ",".join("?" * len(batch))
            c.execute(f"""SELECT tvk, sqs FROM sqs_scores WHERE tvk IN ({ph})
                          AND source != 'derived'""", batch)
            for row in c.fetchall():
                result[row["tvk"]] = row["sqs"]
        missing = [t for t in set(tvks) if t not in result]
        if missing:
            result.update(self._derive_sqs_batch(missing))
        return result

    def _derive_sqs_batch(self, tvks):
        """Apply Pantheon's published rule to current Codex statuses.

        Invertebrates only -- SQS is an invertebrate construct, and a score for
        a lichen would be arithmetic without meaning.

        Queries status_summary directly: get_statuses_batch calls
        get_sqs_scores, so routing through it would recurse.
        """
        if not tvks:
            return {}
        try:
            from shared.sqs_derivation import derive_from_tracks
        except ImportError:
            try:
                from sqs_derivation import derive_from_tracks
            except ImportError:
                return {}

        invert = self._get_invert_tvks()
        candidates = [t for t in tvks if t in invert]
        if not candidates:
            return {}

        c = self._get_conn().cursor()
        tracks = {}
        for batch in _chunked(candidates, 500):
            ph = ",".join("?" * len(batch))
            c.execute(f"""SELECT tvk, status_track, status_value
                          FROM status_summary WHERE tvk IN ({ph})""", batch)
            for row in c.fetchall():
                tracks.setdefault(row["tvk"], {})[row["status_track"]] = row["status_value"]

        result = {}
        for tvk in candidates:
            score = derive_from_tracks(tracks.get(tvk, {}))
            if score:          # 0 and 1 are not worth storing as "has a score"
                result[tvk] = score
        return result'''

# ---------------------------------------------------------------- seed script
OLD_SEED = '''    filled = 0
    track_counts = {}
    for tvk, (tvk_, sqs, winning) in by_species.items():
        c.execute("""INSERT OR IGNORE INTO sqs_scores (tvk, sqs, source)
                     VALUES (?, ?, 'derived')""", (tvk, sqs))
        if c.rowcount > 0:
            filled += 1
            track_counts[winning[0]] = track_counts.get(winning[0], 0) + 1'''

NEW_SEED = '''    # DERIVED SCORES ARE NO LONGER STORED (Session 32).
    #
    # SQS_DEFAULTS below is not Pantheon's published rule -- it scores RDB3 at
    # 16 "per Fowles original SQI", a different index, and takes the maximum of
    # single (track, value) pairs where the rule is a function of rarity AND
    # threat together. 525 of the 816 scores it produced disagreed with the
    # published rule.
    #
    # CodexRepository.get_sqs_scores now derives on demand via
    # shared/sqs_derivation.py, so sqs_scores holds only what Pantheon
    # published (plus manual entries). The candidate count below is reported
    # for information; nothing is written.
    filled = 0
    track_counts = {}
    if False:  # retained for reference; see patch_sqs_derive_live.py
        for tvk, (tvk_, sqs, winning) in by_species.items():
            c.execute("""INSERT OR IGNORE INTO sqs_scores (tvk, sqs, source)
                         VALUES (?, ?, 'derived')""", (tvk, sqs))
            if c.rowcount > 0:
                filled += 1
                track_counts[winning[0]] = track_counts.get(winning[0], 0) + 1'''

OLD_SEED_MSG = '''    print(f"  Candidate invertebrate species: {len(by_species):,}")
    print(f"  SQS scores derived:             {filled:,}")'''

NEW_SEED_MSG = '''    print(f"  Candidate invertebrate species: {len(by_species):,}")
    print(f"  SQS scores STORED:              {filled:,}  "
          f"(derivation is now live -- see shared/sqs_derivation.py)")'''


def apply(path, edits, marker):
    name = os.path.basename(path)
    if not os.path.exists(path):
        print(f"  x NOT FOUND: {path}")
        return False
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if marker in text:
        print(f"  = {name}: already patched")
        return True
    ok = True
    for label, old, new in edits:
        n = text.count(old)
        if n == 1:
            text = text.replace(old, new)
            print(f"  + {name}: {label}")
        else:
            print(f"  x {name}: {label}  ({n} matches, expected 1)")
            ok = False
    if not ok:
        print(f"    -> {name} NOT written")
        return False
    backup = path + ".bak_sqslive"
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return True


def main():
    print("")
    print("Patching -- derive gap-filled SQS live instead of storing it")
    print("=" * 70)

    ok = apply(REPO, [("get_sqs_scores + _derive_sqs_batch", OLD_BATCH, NEW_BATCH)],
               "_derive_sqs_batch")
    ok &= apply(SEED, [("stop writing derived rows", OLD_SEED, NEW_SEED),
                       ("reporting", OLD_SEED_MSG, NEW_SEED_MSG)],
                "DERIVED SCORES ARE NO LONGER STORED")

    print("")
    if not ok:
        print("  One or more files unchanged -- review before rebuilding.")
        return 1

    print("  Checking both files compile and the repository imports...")
    try:
        import py_compile
        py_compile.compile(REPO, doraise=True)
        py_compile.compile(SEED, doraise=True)
        sys.path.insert(0, _ROOT)
        import importlib
        m = importlib.import_module("shared.repositories.codex_repository")
        importlib.reload(m)
        assert hasattr(m.CodexRepository, "_derive_sqs_batch")
        print("  + imports cleanly, _derive_sqs_batch present")
    except Exception as e:  # noqa: BLE001
        print(f"  x FAILED: {type(e).__name__}: {e}")
        print("    restore: copy *.bak_sqslive back over each file")
        return 1

    print("")
    print("  NEXT -- back up codex.db, then rebuild:")
    print("        python scripts/build_codex_db.py")
    print("        python scripts/seed_codex.py")
    print("        python scripts/check_sqs_vs_status.py")
    print("")
    print("  Expect: sqs_scores drops to ~5,522 (Pantheon only, 0 derived);")
    print("  the 'GAP-FILLED vs the published rule' section becomes empty;")
    print("  Examen's SQI figures shift for species that had an invented score.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
