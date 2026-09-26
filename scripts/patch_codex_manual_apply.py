"""patch_codex_manual_apply.py -- rebuilds must re-apply reviews correctly.

    python scripts/patch_codex_manual_apply.py

Apply BEFORE importing any review.

The fault
---------
build_codex_db.py deletes and recreates codex.db, preserving manual_entries,
then re-applies them to status_summary with:

    INSERT OR REPLACE INTO status_summary (...) VALUES (...)

status_summary's primary key is (tvk, status_track, status_detail), and for most
tracks status_detail is NULL. **SQLite treats NULL as distinct inside a
composite primary key**, so REPLACE never matches the JNCC row -- it adds a
second row beside it. Tested:

    INSERT          ('T1','threat_iucn_2001','EN',NULL)
    INSERT OR REPLACE ('T1','threat_iucn_2001','VU',NULL)
    -> both rows present

So after every rebuild each reviewed species would carry its old status and its
new one, and which a consumer saw would depend on row order.

It has never mattered because manual_entries has always been empty. The
leaf-beetle review (NECR702, Lane 2026) is the first import since the 11-track
rebuild.

The fix
-------
* DELETE the matching row (NULL-safe, via COALESCE) and then INSERT.
* A status_value of 'none' records a status the review REMOVED -- a downgrade.
  It deletes and inserts nothing. Without this, "the review says this is no
  longer Nationally Scarce" cannot be represented at all.
* Apply oldest first, so where two reviews touch one species the later wins.

Line-based replacement; re-reads the file afterwards rather than trusting the
line index. Safe to re-run. Backs up as build_codex_db.py.bak_manual.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "scripts", "build_codex_db.py")
BACKUP = TARGET + ".bak_manual"

NEW_BLOCK = '''        # Apply to status_summary, oldest first so a later review wins.
        #
        # DELETE then INSERT -- never INSERT OR REPLACE. SQLite treats NULL as
        # distinct inside a composite primary key, so REPLACE with a NULL
        # status_detail ADDS a row beside the JNCC one instead of replacing it,
        # leaving the old status and the new side by side.
        #
        # A value of 'none' records a status the review REMOVED (a downgrade):
        # delete, insert nothing. See patch_codex_manual_apply.py.
        for row in sorted(manual_statuses, key=lambda r: r[6] or ""):
            tvk, name, track, value, detail, source, date_added, by, notes, rid = row
            c.execute("""DELETE FROM status_summary
                         WHERE tvk = ? AND status_track = ?
                           AND COALESCE(status_detail, '') = COALESCE(?, '')""",
                      (tvk, track, detail))
            if (value or "").strip().lower() == "none":
                continue
            c.execute("""INSERT INTO status_summary
                (tvk, status_track, status_value, status_detail,
                 source, iucn_version, date_designated, origin)
                VALUES (?, ?, ?, ?, ?, NULL, ?, 'manual')""",
                (tvk, track, value, detail, source or "manual", date_added))'''


def main():
    if not os.path.exists(TARGET):
        print(f"NOT FOUND: {TARGET}")
        return 1
    with open(TARGET, "r", encoding="utf-8", newline="") as f:
        raw = f.read()
    ending = "\r\n" if "\r\n" in raw else "\n"

    print("")
    print("Patching build_codex_db.py -- re-applying manual entries")
    print("=" * 70)

    if "never INSERT OR REPLACE" in raw:
        print("  = already patched -- nothing to do")
        return 0

    lines = raw.split(ending)
    start = next((i for i, l in enumerate(lines)
                  if l.strip() == "# Apply to status_summary"), -1)
    end = next((i for i in range(max(start, 0), len(lines))
                if 'source or "manual", date_added))' in lines[i]), -1)
    if start < 0 or end < 0:
        print(f"  x block not found (start={start}, end={end}) -- NOTHING WRITTEN")
        return 1
    span = "\n".join(lines[start:end + 1])
    if "INSERT OR REPLACE INTO status_summary" not in span or \
            "for row in manual_statuses" not in span:
        print("  x located block does not look as expected -- NOTHING WRITTEN")
        print(span)
        return 1

    lines[start:end + 1] = NEW_BLOCK.split("\n")
    shutil.copy2(TARGET, BACKUP)
    with open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(ending.join(lines))
    print(f"  + restore block replaced")
    print(f"  backup written: {os.path.basename(BACKUP)}")

    # Re-read rather than trust the index.
    with open(TARGET, "r", encoding="utf-8") as f:
        t = f.read()
    try:
        import py_compile
        py_compile.compile(TARGET, doraise=True)
        restore = t[t.find("Restore preserved data"):]
        restore = restore[:restore.find("Restored {len(manual_statuses)}")]
        assert "never INSERT OR REPLACE" in restore
        assert "INSERT OR REPLACE INTO status_summary" not in restore
        print("  + compiles; re-read confirms the restore block no longer uses")
        print("    INSERT OR REPLACE on status_summary")
    except Exception as e:  # noqa: BLE001
        print(f"  x FAILED: {type(e).__name__}: {e}")
        print(f"    restore: copy {os.path.basename(BACKUP)} build_codex_db.py")
        return 1

    # Prove the new logic on a scratch table.
    import sqlite3
    s = sqlite3.connect(":memory:")
    s.execute("""CREATE TABLE status_summary (tvk, status_track, status_value,
                 status_detail, source, iucn_version, date_designated, origin,
                 PRIMARY KEY (tvk, status_track, status_detail))""")
    s.execute("INSERT INTO status_summary VALUES "
              "('T1','threat_iucn_2001','EN',NULL,'jncc',NULL,'2014','jncc')")
    s.execute("INSERT INTO status_summary VALUES "
              "('T1','rarity_modern','NS',NULL,'jncc',NULL,'2014','jncc')")
    c = s.cursor()
    manual_statuses = [
        ("T1", "x", "threat_iucn_2001", "VU", None, "rev", "2026-06-29", "", "", 1),
        ("T1", "x", "rarity_modern", "none", None, "rev", "2026-06-29", "", "", 1),
    ]
    exec("\n".join(l[8:] for l in NEW_BLOCK.split("\n")))
    got = sorted(s.execute("SELECT status_track, status_value FROM status_summary"))
    ok = got == [("threat_iucn_2001", "VU")]
    print(f"  {'+' if ok else 'x'} scratch test: EN -> VU replaced, NS cleared: {got}")
    print("")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
