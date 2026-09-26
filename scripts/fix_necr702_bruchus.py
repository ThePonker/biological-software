import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3, paths
c = sqlite3.connect(str(paths.CODEX_DB))
TVK = "NBNSYS0000011069"          # Bruchus rufimanus
before = c.execute("SELECT status_track, status_value FROM manual_entries "
                   "WHERE tvk=? ORDER BY 1", (TVK,)).fetchall()
print("before:", before)
# the NA row came from Bruchus affinis reaching rufimanus through a synonym
c.execute("DELETE FROM manual_entries WHERE tvk=? AND status_track='threat_iucn_2001' "
          "AND status_value='NA'", (TVK,))
# the two rows gave identical 'none' clears -- keep one of each
c.execute("""DELETE FROM manual_entries WHERE tvk=? AND id NOT IN (
               SELECT MIN(id) FROM manual_entries WHERE tvk=?
               GROUP BY status_track, status_value)""", (TVK, TVK))
rid = c.execute("SELECT MAX(review_id) FROM manual_entries").fetchone()[0]
c.execute("UPDATE reviews SET species_count = (SELECT COUNT(DISTINCT tvk) "
          "FROM manual_entries WHERE review_id=?) WHERE id=?", (rid, rid))
c.commit()
print("after: ", c.execute("SELECT status_track, status_value FROM manual_entries "
                           "WHERE tvk=? ORDER BY 1", (TVK,)).fetchall())
print("status:", c.execute("SELECT status_track, status_value FROM status_summary "
                           "WHERE tvk=?", (TVK,)).fetchall())
