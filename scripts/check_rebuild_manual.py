import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3, paths
c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
print("manual rows in status_summary:",
      c.execute("SELECT COUNT(1) FROM status_summary WHERE origin='manual'").fetchone()[0])
print("manual_entries preserved:     ",
      c.execute("SELECT COUNT(1) FROM manual_entries").fetchone()[0])
print("reviews preserved:            ",
      c.execute("SELECT review_name FROM reviews").fetchall())
print("duplicates:                   ", c.execute("""SELECT COUNT(1) FROM (
      SELECT tvk, status_track, COALESCE(status_detail,''), COUNT(1) n
      FROM status_summary GROUP BY 1,2,3 HAVING n > 1)""").fetchone()[0])
print("Z. subspinosa:", c.execute("""SELECT status_track, status_value, origin
      FROM status_summary WHERE tvk='NHMSYS0020153747'""").fetchall())
