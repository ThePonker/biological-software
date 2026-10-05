"""Key species with NO account anywhere -- what is left to find or write.  READ ONLY.

For every key species (Telfer: key / rare key from its current statuses) in
your records, checks for:
  * a review account in codex.db species_profiles (any review)
  * your own account in observatum.db species_profiles
and lists those with neither, grouped by the source of the status that makes
them key -- i.e. which review you would need (Hyman 1992/94, Falk 1991 flies...).

Also: per survey, how many key species have / lack an account.

Run:  python scripts\\list_missing_accounts.py
      python scripts\\list_missing_accounts.py --csv missing_accounts.csv   (full list)
"""
import csv, os, sqlite3, sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "scripts")]
import paths
from import_status_review import key_tiers

TR = ("threat_iucn_2001", "threat_iucn_legacy", "rarity_modern", "rarity_legacy")
c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
o = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
u = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)

st = defaultdict(dict)
for t, tr, v, s in c.execute(f"""SELECT tvk, status_track, status_value, source FROM status_summary
                                 WHERE COALESCE(status_detail,'')='' AND status_track IN ({','.join('?'*4)})""", TR):
    st[t][tr] = (v, s or "")
review_acc = {t for (t,) in c.execute("SELECT DISTINCT tvk FROM species_profiles")}
try:
    own_acc = {t for (t,) in o.execute("SELECT DISTINCT species_tvk FROM species_profiles "
                                       "WHERE COALESCE(profile_text,'')!='' AND species_tvk IS NOT NULL")}
except sqlite3.Error as e:
    sys.exit(f"  x could not read your own profiles from observatum.db: {e}")

recs = Counter(); surveys = defaultdict(set)
for t, p, d in o.execute("SELECT species_tvk, project_name, substr(date,1,4) FROM assessment_records WHERE species_tvk IS NOT NULL"):
    recs[t] += 1
    if p:
        surveys[f"{p} {d}"].add(t)


def info(t):
    r = u.execute("SELECT scientific_name, family FROM taxa WHERE tvk=?", (t,)).fetchone()
    return (r[0], r[1] or "?") if r else (t, "?")


def keyness(t):
    s = st.get(t, {})
    k, r = key_tiers({tr: v for tr, (v, src) in s.items()})
    if not k:
        return None
    # the review behind the key status: the threat or rarity source that qualifies it (prefer modern)
    for tr in ("threat_iucn_2001", "rarity_modern", "threat_iucn_legacy", "rarity_legacy"):
        if tr in s and key_tiers({tr: s[tr][0]})[0]:
            return ("Rare Key" if r else "Key", s[tr][1])
    return ("Rare Key" if r else "Key", "")


missing = []
for t in recs:
    kk = keyness(t)
    if kk and t not in review_acc and t not in own_acc:
        n, f = info(t)
        missing.append((kk[1], n, f, kk[0], recs[t], sorted(s for s, ts in surveys.items() if t in ts), t))

print("Key species with no account   READ ONLY")
print("=" * 96)
allkey = [t for t in recs if keyness(t)]
print(f"  key species in your records: {len(allkey)}   with a review account: {sum(1 for t in allkey if t in review_acc)}"
      f"   your own account: {sum(1 for t in allkey if t in own_acc)}   NEITHER: {len(missing)}")

print("\n  BY THE REVIEW THAT IS CURRENT FOR THEM (where an account would come from)")
by = defaultdict(list)
for m in missing:
    by[m[0][:90]].append(m)
for src, ms in sorted(by.items(), key=lambda x: -len(x[1])):
    on_surveys = sum(1 for m in ms if m[5])
    print(f"\n  {len(ms):>4} species ({on_surveys} on surveys) -- {src or '(no source)'}")
    for m in sorted(ms, key=lambda m: (-len(m[5]), -m[4]))[:12]:
        print(f"         {m[1][:32]:32} {m[2][:16]:16} {m[3]:8} {m[4]:>3} recs  {', '.join(m[5])[:40]}")
    if len(ms) > 12:
        print(f"         ... and {len(ms) - 12} more")

print("\n  PER SURVEY: key species with / without any account")
for s, ts in sorted(surveys.items()):
    k = [t for t in ts if keyness(t)]
    miss = [t for t in k if t not in review_acc and t not in own_acc]
    print(f"    {s:<36} key {len(k):>3}   with account {len(k) - len(miss):>3}   without {len(miss):>3}")

if "--csv" in sys.argv:
    path = sys.argv[sys.argv.index("--csv") + 1]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["species", "family", "key", "records", "surveys", "current_review_source", "tvk"])
        for m in sorted(missing, key=lambda m: (m[2], m[1])):
            w.writerow([m[1], m[2], m[3], m[4], "; ".join(m[5]), m[0], m[6]])
    print(f"\n  full list written: {path}")
print("\nREAD ONLY -- nothing has been changed.")
