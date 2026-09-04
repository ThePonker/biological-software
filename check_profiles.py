import sqlite3, paths
for name, db in (("observatum", paths.OBSERVATUM_DB), ("codex", paths.CODEX_DB)):
    c = sqlite3.connect(str(db))
    try:
        n = c.execute("SELECT COUNT(*) FROM species_profiles").fetchone()[0]
        cols = [r[1] for r in c.execute("PRAGMA table_info(species_profiles)")]
        print(f"{name}: {n} profiles, columns: {cols}")
    except Exception as e:
        print(f"{name}: {e}")
c = sqlite3.connect(str(paths.PANTHEON_DB))
print("\npantheon tables:")
for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
    n = c.execute(f"SELECT COUNT(*) FROM {r[0]}").fetchone()[0]
    print(f"  {r[0]:28} {n}")
