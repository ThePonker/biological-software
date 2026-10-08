"""Move your records and own species profiles onto current UKSI taxa after the UKSI update.

Uses the tvk_remap table written by build_uksi_from_release.py. For every row whose
species_tvk has a replacement there, updates the TVK and re-derives the WHOLE taxonomy block
from the new taxa, so each record stays internally consistent (23_Rebuild_Procedures, step 3):
    species_tvk, species_name, taxon_rank, kingdom, phylum, class_name, order_name, superfamily,
    family, subfamily, genus, taxonomic_sort_key          (whichever of these the table has)
    common_name -- only where the record held the UKSI preferred name (your own names untouched)

Tables: observations, specimens, recording_scheme, species_profiles (your own profiles;
a profile is skipped, and reported, if the current name already has one).
Kept taxa and TVKs newer than the release are not in tvk_remap and are left alone.

  python scripts\\remap_record_tvks.py              DRY RUN (works before the swap, against data\\uksi_2025.db)
  python scripts\\remap_record_tvks.py --apply      only once the new file IS the live uksi.db; backs up observatum.db
"""
import os, re, sqlite3, sys
from collections import Counter, defaultdict
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths

try:   # the specimens' sort-key formula (backfill_sort_keys.py); imported, not restated
    from Observatum.src.utils.constants import INSECT_ORDER_POSITION as ORDER_POSITION
except ImportError:
    ORDER_POSITION = None

APPLY = "--apply" in sys.argv
D = os.path.dirname(str(paths.UKSI_DB))


def has_remap(p):
    try:
        return bool(sqlite3.connect(f"file:{p}?mode=ro", uri=True).execute(
            "SELECT 1 FROM sqlite_master WHERE name='tvk_remap'").fetchone())
    except sqlite3.Error:
        return False


live_new = has_remap(str(paths.UKSI_DB))
NEWDB = str(paths.UKSI_DB) if live_new else os.path.join(D, "uksi_2025.db")
if APPLY and not live_new:
    sys.exit("  x the live uksi.db is still the old file -- swap uksi_2025.db in first. Nothing changed.")
if not has_remap(NEWDB):
    sys.exit(f"  x {NEWDB} has no tvk_remap table -- run build_uksi_from_release.py first")
u = sqlite3.connect(f"file:{NEWDB}?mode=ro", uri=True)
o = sqlite3.connect(str(paths.OBSERVATUM_DB))

remap = {a: b for a, b in u.execute("SELECT old_tvk, new_tvk FROM tvk_remap WHERE new_tvk IS NOT NULL AND new_tvk != old_tvk")}
tcols = [r[1] for r in u.execute("PRAGMA table_info(taxa)")]
taxa = {r[0]: dict(zip(tcols, r)) for r in u.execute(f"SELECT {', '.join('[' + c + ']' for c in tcols)} FROM taxa")}
pref = {}
for nm, t, p in u.execute("SELECT common_name, tvk, preferred FROM common_names"):
    if str(p) in ("1", "Y", "y", "True") and t not in pref:
        pref[t] = nm


def subfamily(tvk):
    seen, cur = set(), taxa.get(tvk, {}).get("parent_tvk")
    while cur and cur in taxa and cur not in seen:
        seen.add(cur)
        if (taxa[cur].get("rank") or "").lower() == "subfamily":
            return taxa[cur]["scientific_name"]
        cur = taxa[cur].get("parent_tvk")
    return ""


# what the old (pre-swap) file called the preferred English name, to know which common names were derived
OLDDB = os.path.join(D, "uksi_2023.db") if live_new else str(paths.UKSI_DB)
oldpref = {}
if os.path.exists(OLDDB):
    for nm, t, p in sqlite3.connect(f"file:{OLDDB}?mode=ro", uri=True).execute("SELECT common_name, tvk, preferred FROM common_names"):
        if str(p) in ("1", "Y", "y", "True") and t not in oldpref:
            oldpref[t] = nm

FIELD = {  # record column -> taxa column (or a function)
    "species_name": "scientific_name", "taxon_rank": "rank", "kingdom": "kingdom", "phylum": "phylum",
    "class_name": "class", "order_name": "order", "superfamily": "superfamily", "family": "family", "genus": "genus",
}
print("Remap records to current UKSI taxa -- " + ("APPLY" if APPLY else "DRY RUN"))
print("=" * 88)
print(f"  using {os.path.basename(NEWDB)}   replacements available: {len(remap)}")
if not remap:
    sys.exit("  nothing to remap")

plans = {}
for tbl in ("observations", "specimens", "recording_scheme", "species_profiles"):
    cols = [r[1] for r in o.execute(f"PRAGMA table_info({tbl})")]
    if "species_tvk" not in cols:
        continue
    # Sort key -- never guessed (fault F27, 8 Oct 2026). The old test ("every sampled
    # key at most 7 digits -> sort_code, else sort_order") wrote UKSI's 50-character
    # sort_order into specimen 1752 (specimen keys are 8 digits) and into 42
    # observations (a table with no keys at all, so nothing to sample).
    #   specimens     the specimens' own formula, imported, not restated:
    #                 INSECT_ORDER_POSITION[order] * 1,000,000 + sort_code
    #   other tables  only rows that already carry a key, and only when every sampled
    #                 key is clearly one format; otherwise the key is left alone
    sk = None
    if "taxonomic_sort_key" in cols:
        if tbl == "specimens":
            sk = "specimen_formula" if ORDER_POSITION is not None else None
            if sk is None:
                print("  ! specimens: INSECT_ORDER_POSITION not importable -- sort keys left unchanged")
        else:
            vals = [str(v) for (v,) in o.execute(f"SELECT taxonomic_sort_key FROM {tbl} "
                                                 "WHERE COALESCE(taxonomic_sort_key,'')!='' LIMIT 500")]
            if vals and all(re.fullmatch(r"\d{1,7}", v) for v in vals):
                sk = "sort_code"
            elif vals and all(len(v) >= 20 and not v.isdigit() for v in vals):
                sk = "sort_order"
            elif vals:
                print(f"  ! {tbl}: sort keys of mixed format -- left unchanged on remapped rows")
    key_x = "taxonomic_sort_key" if "taxonomic_sort_key" in cols else "NULL"
    rows = list(o.execute(f"SELECT id, species_tvk, {'common_name' if 'common_name' in cols else 'NULL'}, "
                          f"{'irecord_id' if 'irecord_id' in cols else 'NULL'}, {key_x}, "
                          f"{'order_name' if 'order_name' in cols else 'NULL'} FROM {tbl} WHERE species_tvk IN "
                          f"({','.join('?' * len(remap))})", list(remap)))
    upd, skipped, by_pair, irec = [], [], Counter(), 0
    for rid, old_t, cn, irid, old_key, old_order in rows:
        new_t = remap[old_t]; tx = taxa.get(new_t)
        if not tx:
            skipped.append((rid, old_t, "replacement not in taxa")); continue
        v = {"species_tvk": new_t}
        for c, src in FIELD.items():
            if c in cols:
                v[c] = tx.get(src) or ""
        if "subfamily" in cols:
            v["subfamily"] = subfamily(new_t)
        if sk == "specimen_formula" and tx.get("sort_code") is not None:
            order = v.get("order_name") or old_order or tx.get("order")
            v["taxonomic_sort_key"] = ORDER_POSITION.get(order, 99) * 1000000 + int(tx["sort_code"])
        elif sk in ("sort_code", "sort_order") and old_key not in (None, "") and tx.get(sk) is not None:
            v["taxonomic_sort_key"] = tx.get(sk)
        if "common_name" in cols and (not cn or cn == oldpref.get(old_t)) and pref.get(new_t):
            v["common_name"] = pref[new_t]
        if tbl == "species_profiles":
            clash = o.execute("SELECT id FROM species_profiles WHERE species_name=? AND id!=?",
                              (tx["scientific_name"], rid)).fetchone()
            if clash:
                skipped.append((rid, old_t, f"a profile for {tx['scientific_name']} already exists")); continue
        upd.append((rid, v)); by_pair[(old_t, new_t)] += 1
        irec += 1 if irid else 0
    plans[tbl] = (upd, skipped, by_pair, sk, irec)
    print(f"\n  {tbl}: {len(upd)} rows to update on {len(by_pair)} TVKs"
          + (f"   (sort key written as {sk})" if sk else "") + (f"   with an iRecord ID: {irec}" if irec else ""))
    for (a, b), n in sorted(by_pair.items(), key=lambda x: -x[1])[:25]:
        on = o.execute(f"SELECT species_name FROM {tbl} WHERE species_tvk=? LIMIT 1", (a,)).fetchone()
        print(f"      {n:>4}  {(on[0] if on else '?')[:36]:36} -> {taxa[b]['scientific_name'][:36]:36} [{taxa[b].get('family') or ''}]")
    for s in skipped:
        print(f"      ! skipped row {s[0]} ({s[1]}): {s[2]}")

if not APPLY:
    sys.exit("\n  DRY RUN -- nothing changed. After the UKSI swap, re-run with --apply.\n")

bk = os.path.join(os.path.dirname(str(paths.OBSERVATUM_DB)), f"observatum_pre_uksi_remap_{datetime.now():%Y%m%d_%H%M%S}.db")
src = sqlite3.connect(str(paths.OBSERVATUM_DB)); dst = sqlite3.connect(bk); src.backup(dst); dst.close(); src.close()
print(f"\n  backup: {bk}")
try:
    for tbl, (upd, *_r) in plans.items():
        for rid, v in upd:
            o.execute(f"UPDATE {tbl} SET {', '.join('[' + k + ']=?' for k in v)} WHERE id=?", (*v.values(), rid))
    o.commit()
except Exception as e:
    o.rollback(); sys.exit(f"  x FAILED, rolled back -- nothing changed: {type(e).__name__}: {e}")
present = set(taxa)
for tbl, (upd, *_r) in plans.items():
    left = o.execute(f"SELECT COUNT(1) FROM {tbl} WHERE species_tvk IN ({','.join('?' * len(remap))})", list(remap)).fetchone()[0]
    outside = sum(1 for (t,) in o.execute(f"SELECT species_tvk FROM {tbl} WHERE COALESCE(species_tvk,'')!=''") if t not in present)
    print(f"  {tbl}: updated {len(upd)}   still on a replaced TVK {left} (should be 0)   on a TVK outside the new taxa {outside}")
print("  (TVKs outside the new taxa should be only the ones newer than the July 2025 release)")
