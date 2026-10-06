"""Build a NEW uksi.db from the NHM 'UKSI Simplified Copy' spreadsheet (July 2025).

Writes data\\uksi_2025.db beside the current uksi.db -- the current file is NOT touched.
Same tables, columns and indexes as the current uksi.db (copied from it), so the
suite needs no code change when the file is later swapped in.

  taxa          July TAXA rows that are NOT redundant -- current recommended taxa only.
                kingdom..genus + superfamily derived up the PARENT_TVK chain (own rank
                included); sort_order = SORT_ORDER; sort_code renumbered in that order.
                Old conservation columns carried over by TVK (fallback only; Codex is primary).
  hierarchy     tvk -> parent_tvk
  synonyms      every Latin name (status S or U) whose TVK is not the recommended one ->
                its recommended taxon; PLUS our old taxa/synonym names that are no longer
                current (renamed or redundant), mapped through the July NAMES sheet.
                Names identical to a current taxon name are not added (no pick-list duplicates).
  common_names  English names -> recommended taxon; recommended ones marked preferred
  designations  carried over, TVKs remapped to current where they changed
  name_map      every name TVK -> recommended TVK (the Nameserver mapping)

Ends with a report: counts vs the current file, and which of your records / Codex
TVKs are not current taxa in the new file (and whether they map).

  python scripts\\build_uksi_from_release.py "<path to the .xlsx>"
"""
import os, sqlite3, sys, time
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths
from openpyxl import load_workbook

if len(sys.argv) < 2 or not os.path.isfile(sys.argv[1]):
    sys.exit('  usage: python scripts\\build_uksi_from_release.py "<path to the .xlsx>"')
XLSX = sys.argv[1]
OUT = os.path.join(os.path.dirname(str(paths.UKSI_DB)), "uksi_2025.db")
SOURCE = "UKSI Simplified Copy 20250703a (NHM Data Portal)"
t0 = time.time()
print("Build uksi_2025.db from the July 2025 UKSI release")
print("=" * 84)

old = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
schema = [(n, s) for n, s in old.execute("SELECT name, sql FROM sqlite_master WHERE sql IS NOT NULL "
                                         "AND name NOT LIKE 'sqlite_%' ORDER BY type DESC, name")]
cols = {t: [r[1] for r in old.execute(f"PRAGMA table_info([{t}])")] for t in ("taxa", "hierarchy", "synonyms", "common_names", "designations")}
# conventions of the current file
rk = [r for (r,) in old.execute("SELECT rank FROM taxa WHERE rank IS NOT NULL LIMIT 2000")]
LOWER_RANK = sum(1 for r in rk if r == r.lower()) > len(rk) / 2
pv = Counter(v for (v,) in old.execute("SELECT preferred FROM common_names"))
PREF_YES, PREF_NO = (1, 0)
if pv:
    vals = [v for v, _ in pv.most_common()]
    if any(isinstance(v, str) for v in vals):
        PREF_YES = next((v for v in vals if str(v).upper() in ("Y", "YES", "TRUE", "1")), "Y")
        PREF_NO = next((v for v in vals if str(v).upper() in ("N", "NO", "FALSE", "0")), "N")
print(f"  current file conventions: rank {'lower' if LOWER_RANK else 'as given'}-case; preferred values {dict(pv)}")

wb = load_workbook(XLSX, read_only=True, data_only=True)


def sheet(name):
    it = wb[name].iter_rows(values_only=True)
    h = [str(x or "").strip() for x in next(it)]
    for r in it:
        yield {k: ("" if v is None else str(v).strip()) for k, v in zip(h, r)}


# A TVK can sit on several TAXA rows (one per ORGANISM_KEY: e.g. an old-checklist organism flagged
# redundant AND the current one). It is current if ANY of its rows is current, and its classification
# and sort order come from that current row -- never let a redundant duplicate row win.
T, nrows, mixed = {}, Counter(), set()
for r in sheet("TAXA"):
    k = r.get("TAXON_VERSION_KEY")
    if not k:
        continue
    nrows[k] += 1
    if k not in T:
        T[k] = r
    else:
        a, b = T[k].get("REDUNDANT_FLAG") == "Y", r.get("REDUNDANT_FLAG") == "Y"
        if a != b:
            mixed.add(k)
        if a and not b:
            T[k] = r                                   # prefer the current row
print(f"  TAXA rows {sum(nrows.values())}, distinct TVKs {len(T)}; TVKs on several rows {sum(1 for v in nrows.values() if v > 1)}"
      f"; with one current and one redundant row {len(mixed)} (now treated as current)")
cur_parents = defaultdict(set)
for r in sheet("TAXA"):
    if r.get("TAXON_VERSION_KEY") and r.get("REDUNDANT_FLAG") != "Y":
        cur_parents[r["TAXON_VERSION_KEY"]].add(r.get("PARENT_TVK", ""))
split_par = [k for k, v in cur_parents.items() if len(v) > 1]
print(f"  TVKs with several CURRENT rows under different parents: {len(split_par)}"
      + (f"  e.g. {[T[k]['TAXON_NAME'] for k in split_par[:5]]}" if split_par else ""))
current = {t for t, r in T.items() if r.get("REDUNDANT_FLAG") != "Y"}
N = [r for r in sheet("NAMES") if r.get("TAXON_VERSION_KEY") and r.get("RECOMMENDED_TAXON_VERSION_KEY")]
wb.close()
print(f"  read TAXA {len(T)}, NAMES {len(N)}  ({time.time() - t0:.0f}s)")

WANT = {"kingdom": "kingdom", "phylum": "phylum", "class": "class", "order": "order",
        "superfamily": "superfamily", "family": "family", "genus": "genus"}


def derive(tvk):
    out, seen, cur = {}, set(), tvk
    while cur and cur in T and cur not in seen:
        seen.add(cur); p = T[cur]
        k = WANT.get(p.get("RANK", "").lower())
        if k and k not in out:
            out[k] = p.get("TAXON_NAME", "")
        cur = p.get("PARENT_TVK")
    return out


# name map: name TVK -> recommended TVK. Where a TVK has several NAMES rows that disagree,
# prefer the one whose recommended TVK is a current taxon.
nmap, nconf = {}, 0
for r in N:
    k = r["TAXON_VERSION_KEY"]
    v = (r["RECOMMENDED_TAXON_VERSION_KEY"], r.get("TAXON_NAME", ""), r.get("RECOMMENDED_SCIENTIFIC_NAME", ""),
         r.get("NAME_STATUS", ""), r.get("DEPRECATED_DATE", ""))
    if k not in nmap:
        nmap[k] = v
    elif nmap[k][0] != v[0]:
        nconf += 1
        if nmap[k][0] not in current and v[0] in current:
            nmap[k] = v
print(f"  NAMES: TVKs whose rows point at different recommended TVKs: {nconf} (current target preferred)")


oldname = {t: s for t, s in old.execute("SELECT tvk, scientific_name FROM taxa")}
oldrk = {t: ((r or "").lower(), (k or "")) for t, r, k in old.execute("SELECT tvk, rank, kingdom FROM taxa")}
by_name = defaultdict(list)
for t_ in current:
    by_name[T[t_].get("TAXON_NAME", "").lower()].append(t_)
HOW = {}
REJECTED = []
SPGROUP = {"species", "species pro parte", "species aggregate", "species sensu lato", "species sensu stricto",
           "species hybrid", "microspecies"}
same_rank = lambda a, b: a == b or (a in SPGROUP and b in SPGROUP)


def to_current(tvk, depth=0):
    """current taxon for a TVK: itself, else via the NAMES mapping, else by an exact
    name that matches exactly ONE current taxon (UKSI re-keyed the name without a mapping)"""
    if tvk in current:
        return tvk
    if depth <= 4 and tvk in nmap and nmap[tvk][0] != tvk:
        r = to_current(nmap[tvk][0], depth + 1)
        if r:
            HOW.setdefault(tvk, "name_map"); return r
    if depth == 0:
        nm = (oldname.get(tvk) or (nmap.get(tvk) or ("", ""))[1] or "").lower()
        hits = by_name.get(nm, []) if nm else []
        if tvk in oldrk:                     # same RANK and same KINGDOM only -- never a homonym elsewhere
            rk_, kg_ = oldrk[tvk]
            before = list(hits)
            hits = [h for h in hits if same_rank(T[h].get("RANK", "").lower(), rk_) and (not kg_ or derive(h).get("kingdom", "") == kg_)]
            if before and not hits:
                REJECTED.append((nm, tvk, rk_, kg_, [(T[h].get("RANK", ""), derive(h).get("kingdom", "")) for h in before]))
        if len(hits) == 1:
            HOW[tvk] = "same name"; return hits[0]
    return None


if os.path.exists(OUT):
    os.remove(OUT)
new = sqlite3.connect(OUT)
for n, s in schema:
    new.execute(s)
if "name_map" not in {n for n, _ in schema}:
    new.execute("""CREATE TABLE name_map (tvk TEXT PRIMARY KEY, recommended_tvk TEXT NOT NULL, name TEXT,
                   recommended_name TEXT, name_status TEXT, deprecated TEXT, source TEXT)""")
    new.execute("CREATE INDEX idx_name_map_rec ON name_map(recommended_tvk)")

# ---- taxa ----
oldcons = {}
consc = [c for c in cols["taxa"] if c in ("red_list_status", "red_list_source", "legal_protection", "bap_status",
                                         "rarity_status", "nnss_status", "international_status")]
if consc:
    for r in old.execute(f"SELECT tvk, {', '.join(consc)} FROM taxa"):
        if any(r[1:]):
            ct = to_current(r[0])
            if ct:
                oldcons.setdefault(ct, dict(zip(consc, r[1:])))
order_ = sorted(current, key=lambda t: (T[t].get("SORT_ORDER", ""), T[t].get("TAXON_NAME", "")))
# a current taxon's parent may be redundant (not in the new taxa): point it at the nearest CURRENT ancestor
par, repar = {}, 0
for t_ in current:
    p_, seen_ = T[t_].get("PARENT_TVK") or None, set()
    while p_ and p_ not in current and p_ in T and p_ not in seen_:
        seen_.add(p_); p_ = T[p_].get("PARENT_TVK") or None
    if p_ and p_ not in current:
        p_ = None
    if p_ != (T[t_].get("PARENT_TVK") or None):
        repar += 1
    par[t_] = p_
print(f"  parent links pointing at a non-current taxon, redirected to the nearest current ancestor: {repar}")
# one name, two current concepts (s. str. / s. lat., aggregates): show the qualifier, else the authority
SPLEVEL = {"species", "species aggregate", "species sensu lato", "species hybrid", "subspecies", "variety", "form",
           "microspecies", "subspecies aggregate", "nothosubspecies", "cultivar"}
kg = {x: derive(x).get("kingdom", "") for x in current if T[x].get("RANK", "").lower() in SPLEVEL}
grp = defaultdict(list)
for x in kg:
    grp[(T[x]["TAXON_NAME"].lower(), kg[x])].append(x)
dupe = {t_ for ts in grp.values() if len(ts) > 1 for t_ in ts}       # species-level, same kingdom only
shown = {}
# names stay PLAIN (import wizards, review loads and Tabella match on them, as now);
# the qualifier / authority that tells shared names apart goes into its own table
for t_ in dupe:
    q, a = T[t_].get("TAXON_QUALIFIER", ""), T[t_].get("TAXON_AUTHORITY", "")
    a2 = a if a.startswith("(") else (f"({a})" if a else "")
    shown[t_] = f"{T[t_]['TAXON_NAME']} {q}".strip() if q else (f"{T[t_]['TAXON_NAME']} {a2}".strip())
print(f"\n  names shared by more than one current taxon: {len({T[x]['TAXON_NAME'].lower() for x in dupe})} "
      f"({len(dupe)} taxa) -- kept plain in taxa, labels in taxon_qualifiers")
rows = []
for i, t in enumerate(order_, 1):
    r = T[t]; d = derive(t)
    rank = r.get("RANK", "")
    v = {"tvk": t, "scientific_name": r.get("TAXON_NAME", ""), "rank": rank.lower() if LOWER_RANK else rank,
         "parent_tvk": par[t], "sort_code": i, "sort_order": r.get("SORT_ORDER", "")}
    v.update({k: d.get(k, "") for k in WANT if k in cols["taxa"]})
    v.update(oldcons.get(t, {}))
    rows.append(tuple(v.get(c) for c in cols["taxa"]))
new.executemany(f"INSERT INTO taxa ({', '.join('[' + c + ']' for c in cols['taxa'])}) VALUES ({','.join('?' * len(cols['taxa']))})", rows)
new.execute("CREATE TABLE taxon_qualifiers (tvk TEXT PRIMARY KEY, authority TEXT, qualifier TEXT, shared_name INTEGER, label TEXT)")
new.executemany("INSERT INTO taxon_qualifiers VALUES (?,?,?,?,?)",
                [(x, T[x].get("TAXON_AUTHORITY", ""), T[x].get("TAXON_QUALIFIER", ""), 1 if x in dupe else 0,
                  shown.get(x, T[x]["TAXON_NAME"])) for x in order_
                 if T[x].get("TAXON_AUTHORITY") or T[x].get("TAXON_QUALIFIER") or x in dupe])
new.executemany("INSERT INTO hierarchy (tvk, parent_tvk) VALUES (?, ?)",
                [(t, par[t]) for t in order_])
cur_names = {T[t]["TAXON_NAME"].lower() for t in current}

# ---- synonyms ----
syn = set()
for r in N:
    if r.get("LANGUAGE") != "la" or r.get("NAME_STATUS") not in ("S", "U"):
        continue
    tgt = to_current(r["RECOMMENDED_TAXON_VERSION_KEY"])
    nm = r.get("TAXON_NAME", "")
    if tgt and nm and nm.lower() not in cur_names:
        syn.add((nm, tgt))
carried = 0
for nm, t in list(old.execute("SELECT synonym, tvk FROM synonyms")) + list(old.execute("SELECT scientific_name, tvk FROM taxa")):
    tgt = to_current(t)
    if tgt and nm and nm.lower() not in cur_names and (nm, tgt) not in syn:
        syn.add((nm, tgt)); carried += 1
new.executemany("INSERT OR IGNORE INTO synonyms (synonym, tvk) VALUES (?, ?)", sorted(syn))

# ---- common names ----
cn = {}
for r in N:
    if r.get("LANGUAGE") != "en":
        continue
    tgt = to_current(r["RECOMMENDED_TAXON_VERSION_KEY"])
    nm = r.get("TAXON_NAME", "")
    if tgt and nm:
        pref = r.get("NAME_STATUS") == "R"
        if (nm, tgt) not in cn or pref:
            cn[(nm, tgt)] = pref
cn_carried = 0
have_cn = {(nm.lower(), t_) for (nm, t_) in cn}
has_pref = {t_ for (nm, t_), p in cn.items() if p}
for nm, t_, p_ in old.execute("SELECT common_name, tvk, preferred FROM common_names"):
    tgt = to_current(t_)
    if tgt and nm and (nm.lower(), tgt) not in have_cn:
        keep_pref = str(p_) in ("1", str(PREF_YES)) and tgt not in has_pref   # stays preferred only if July has none
        cn[(nm, tgt)] = keep_pref; have_cn.add((nm.lower(), tgt)); cn_carried += 1
        if keep_pref:
            has_pref.add(tgt)
print(f"  English names carried over from the current file (not in the July sheet): {cn_carried}")
new.executemany("INSERT OR IGNORE INTO common_names (common_name, tvk, preferred) VALUES (?, ?, ?)",
                [(nm, t, PREF_YES if p else PREF_NO) for (nm, t), p in sorted(cn.items())])

# ---- designations (carried over, TVKs remapped) ----
dc = [c for c in cols["designations"] if c != "id"]
drows, dlost = [], 0
for r in old.execute(f"SELECT {', '.join(dc)} FROM designations"):
    v = dict(zip(dc, r)); tgt = to_current(v["tvk"])
    if not tgt:
        dlost += 1; continue
    v["tvk"] = tgt; drows.append(tuple(v[c] for c in dc))
new.executemany(f"INSERT INTO designations ({', '.join(dc)}) VALUES ({','.join('?' * len(dc))})", drows)

# every TVK we hold anywhere that is not current -> its replacement, and how it was found
o_ = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
c_ = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
held = set(oldname)
for db_, tb_, col_ in ((o_, "observations", "species_tvk"), (o_, "specimens", "species_tvk"), (o_, "recording_scheme", "species_tvk"),
                       (o_, "species_profiles", "species_tvk"), (c_, "designations", "tvk"), (c_, "manual_entries", "tvk"),
                       (c_, "species_profiles", "tvk"), (c_, "sqs_scores", "tvk"), (c_, "status_summary", "tvk")):
    try:
        held |= {x for (x,) in db_.execute(f"SELECT DISTINCT {col_} FROM {tb_} WHERE COALESCE({col_},'')!=''")}
    except sqlite3.Error:
        pass
used = defaultdict(list)
for db_, nm_, tb_, col_ in ((o_, "obs", "observations", "species_tvk"), (o_, "spec", "specimens", "species_tvk"),
                            (o_, "RS", "recording_scheme", "species_tvk"), (o_, "own profile", "species_profiles", "species_tvk"),
                            (c_, "review status", "manual_entries", "tvk"), (c_, "review account", "species_profiles", "tvk")):
    try:
        for x, k in db_.execute(f"SELECT {col_}, COUNT(1) FROM {tb_} WHERE COALESCE({col_},'')!='' GROUP BY {col_}"):
            used[x].append(f"{nm_} {k}")
    except sqlite3.Error:
        pass
new.execute("DROP TABLE IF EXISTS tvk_remap")
new.execute("CREATE TABLE tvk_remap (old_tvk TEXT PRIMARY KEY, new_tvk TEXT, method TEXT, old_name TEXT, new_name TEXT)")
rem = []
for x in sorted(held):
    if x in current:
        continue
    y = to_current(x)
    rem.append((x, y, HOW.get(x) if y else None, oldname.get(x) or (nmap.get(x) or ("", ""))[1], T[y]["TAXON_NAME"] if y else None))
new.executemany("INSERT INTO tvk_remap VALUES (?,?,?,?,?)", rem)
print(f"\n  tvk_remap: {len(rem)} old TVKs   by name map {sum(1 for r in rem if r[2] == 'name_map')}   "
      f"by same name {sum(1 for r in rem if r[2] == 'same name')}   "
      f"no replacement {sum(1 for r in rem if not r[1])}")
# KEEP: taxa your data uses that the UKSI no longer treats as current and that have no replacement
# (old-checklist / redundant taxa). Copied from the current file unchanged so records, review
# statuses and accounts keep working; labelled in taxon_qualifiers. Nothing is renamed on a guess.
keep = [x for x, y, how, on, nn in rem if not y and x in used and x in oldname]
# species you consider accepted British taxa although the July UKSI flags them redundant: kept selectable
KEEP_BY_REQUEST = ["Nialus varians", "Trichonotulus scrofa", "Subrinus sturmi", "Aphodius satellitius", "Nimbus affinis",
    "Bolitobius formosus", "Cypha ovulum", "Atheta gilvicollis", "Atheta brisouti", "Cousya defecta", "Myllaena graeca",
    "Ochthebius difficilis", "Laccobius obscuratus", "Calathus luctuosus", "Cerylon deplanatum", "Cerophytum elateroides",
    "Cidnopus parvulus", "Otiorhynchus coecus", "Sibinia pellucens", "Miarus salsolae", "Anaspis melanostoma",
    "Aglyptinus agathidioides", "Carpophilus flavipes", "Hydroporus foveolatus", "Otolelus neglectus", "Lathrobium laevipenne"]
present_ = {T[x]["TAXON_NAME"].lower() for x in current}
req_found, req_missing = [], []
for nm_ in KEEP_BY_REQUEST:
    if nm_.lower() in present_:
        continue                                            # already current -- nothing to keep
    hit_ = [x for x, s in oldname.items() if s and (s.lower() == nm_.lower() or
            s.lower().replace("aphodius (nialus) ?", "nialus ").replace("aphodius (trichonotulus) ", "trichonotulus ")
             .replace("aphodius (subrinus) ?", "subrinus ") == nm_.lower())]
    if hit_:
        req_found.append(hit_[0])
    else:
        req_missing.append(nm_)
keep_req = [x for x in req_found if x not in keep]
accepted = {}                                   # tvk -> the accepted name you gave (for every requested taxon, used or not)
for nm_ in KEEP_BY_REQUEST:
    for x in req_found:
        on_ = oldname[x].lower().replace("aphodius (nialus) ?", "nialus ").replace("aphodius (trichonotulus) ", "trichonotulus ") \
              .replace("aphodius (subrinus) ?", "subrinus ")
        if on_ == nm_.lower() and oldname[x] != nm_:
            accepted[x] = nm_
keep = keep + keep_req
if keep:
    oc = cols["taxa"]
    for x in keep:
        r_ = old.execute(f"SELECT {', '.join('[' + c + ']' for c in oc)} FROM taxa WHERE tvk=?", (x,)).fetchone()
        new.execute(f"INSERT OR IGNORE INTO taxa ({', '.join('[' + c + ']' for c in oc)}) VALUES ({','.join('?' * len(oc))})", r_)
        op_ = dict(zip(oc, r_)).get("parent_tvk")
        np_ = to_current(op_) if op_ else None
        new.execute("UPDATE taxa SET parent_tvk=? WHERE tvk=?", (np_, x))
        new.execute("INSERT OR IGNORE INTO hierarchy (tvk, parent_tvk) VALUES (?, ?)", (x, np_))
        why_ = "kept at your request (accepted British species)" if x in keep_req else "kept because your data uses it"
        new.execute("INSERT OR REPLACE INTO taxon_qualifiers (tvk, authority, qualifier, shared_name, label) VALUES (?,?,?,?,?)",
                    (x, "", "not current in UKSI 2025 -- " + why_, 0, oldname[x]))
    # their old synonyms and English names come with them (so 'Aphodius varians' still finds the kept taxon)
    ks_ = set(keep)
    curn_ = {s.lower() for (s,) in new.execute("SELECT scientific_name FROM taxa")}
    new.executemany("INSERT OR IGNORE INTO synonyms (synonym, tvk) VALUES (?, ?)",
                    [(s, x) for s, x in old.execute("SELECT synonym, tvk FROM synonyms") if x in ks_ and s and s.lower() not in curn_])
    new.executemany("INSERT OR IGNORE INTO common_names (common_name, tvk, preferred) VALUES (?, ?, ?)",
                    [(c, x, p) for c, x, p in old.execute("SELECT common_name, tvk, preferred FROM common_names") if x in ks_])
    for x, nm_ in accepted.items():
        if x in ks_:
            new.execute("UPDATE taxa SET scientific_name=?, genus=? WHERE tvk=?", (nm_, nm_.split()[0], x))
            new.execute("INSERT OR IGNORE INTO synonyms (synonym, tvk) VALUES (?, ?)", (oldname[x], x))
            new.execute("UPDATE taxon_qualifiers SET label=? WHERE tvk=?", (nm_, x))
            print(f"      shown as your accepted name: {oldname[x]}  ->  {nm_}   (old name kept as a synonym)")
    rem = [(x, x, "kept (your request)" if x in keep_req else "kept (used by your data)", on, on) if x in keep
           else (x, y, how, on, nn) for x, y, how, on, nn in rem]
    new.execute("DELETE FROM tvk_remap WHERE old_tvk IN (%s)" % ",".join("?" * len(keep)), keep)
    new.executemany("INSERT INTO tvk_remap VALUES (?,?,?,?,?)", [r_ for r_ in rem if r_[0] in keep])
    print(f"  kept as taxa, not current in UKSI 2025: {len(keep)}  ({len(keep) - len(keep_req)} used by your data, {len(keep_req)} at your request)")
    for x in keep:
        print(f"      {oldname[x][:40]:40} {x}  [{'; '.join(used[x]) if x in used else 'your request'}]")
if req_missing:
    print(f"  requested but not found in the current file either (cannot be kept): {req_missing}")

# TVKs your data uses that are not in the current file at all (newer than this release): left as they are
newer = [x for x, y, how, on, nn in rem if not y and x in used and x not in oldname]
if newer:
    print(f"  TVKs your data uses that are newer than this release (left as they are): {len(newer)}")
    for x in newer:
        print(f"      {x}  [{'; '.join(used[x])}]")

# sort_code: one sequence over the whole table, in sort_order (kept taxa included)
seq = [x for (x,) in new.execute("SELECT tvk FROM taxa ORDER BY sort_order, scientific_name")]
new.executemany("UPDATE taxa SET sort_code=? WHERE tvk=?", [(i, x) for i, x in enumerate(seq, 1)])

new.executemany("INSERT OR IGNORE INTO name_map VALUES (?,?,?,?,?,?,?)",
                [(t,) + v + (SOURCE,) for t, v in nmap.items()])
new.commit()

# ---- report ----
cnt = lambda db, t: db.execute(f"SELECT COUNT(1) FROM {t}").fetchone()[0]
print(f"\n  written: {OUT}  ({time.time() - t0:.0f}s)")
print(f"  {'table':<14} {'current':>9} {'new':>9}")
for t in ("taxa", "hierarchy", "synonyms", "common_names", "designations", "name_map"):
    try:
        a = cnt(old, t)
    except sqlite3.Error:
        a = "-"
    print(f"  {t:<14} {a:>9} {cnt(new, t):>9}")
print(f"  (synonyms carried over from the current file: {carried}; designations not mappable: {dlost})")
# old names that can no longer be found at all (not a current name, not a synonym)
findable = {s.lower() for (s,) in new.execute("SELECT scientific_name FROM taxa")} | {T[x]["TAXON_NAME"].lower() for x in current} | \
           {s.lower() for (s,) in new.execute("SELECT synonym FROM synonyms")}
okk = {t_: (k or "?") for t_, k in old.execute("SELECT tvk, kingdom FROM taxa")}
lostk, lostan = Counter(), []
for nm_, t_ in list(old.execute("SELECT scientific_name, tvk FROM taxa")) + list(old.execute("SELECT synonym, tvk FROM synonyms")):
    if nm_ and nm_.lower() not in findable:
        lostk[okk.get(t_, "?")] += 1
        if okk.get(t_) == "Animalia":
            lostan.append((nm_, t_, oldname.get(t_, "")))
print(f"\n  old names no longer findable, by kingdom of the taxon: {dict(lostk.most_common())}")
okr = {t_: (r or "") for t_, r in old.execute("SELECT tvk, rank FROM taxa")}
ocl = {t_: (o_ or "", f_ or "") for t_, o_, f_ in old.execute("SELECT tvk, [order], family FROM taxa")}
LOST = os.path.join(os.path.dirname(str(paths.UKSI_DB)), "uksi_lost_names.csv")
lost_all = []
for nm_, t_, src_ in list(old.execute("SELECT scientific_name, tvk, 'taxon name' FROM taxa")) + \
                    list(old.execute("SELECT synonym, tvk, 'synonym' FROM synonyms")):
    if not nm_ or nm_.lower() in findable:
        continue
    if t_ not in T:
        why = "not in July release"
    elif T[t_].get("REDUNDANT_FLAG") == "Y":
        why = "flagged redundant"
    elif t_ in current:
        why = "name dropped, taxon current"
    else:
        why = "taxon not current"
    lost_all.append((nm_, src_, t_, oldname.get(t_, ""), okk.get(t_, "?"), okr.get(t_, ""), *ocl.get(t_, ("", "")), why))
with open(LOST, "w", newline="", encoding="utf-8") as f_:
    import csv as _csv2
    w_ = _csv2.writer(f_)
    w_.writerow(["name", "name_type", "old_tvk", "old_taxon_name", "kingdom", "rank", "order", "family", "why_lost"])
    for r_ in sorted(lost_all, key=lambda r: (r[4], r[6], r[7], r[0])):
        w_.writerow(r_)
print(f"  ALL lost names written to {LOST}: {len(lost_all)}")
print(f"    by reason: {Counter(r[8] for r in lost_all).most_common()}")
print(f"    by rank:   {Counter(r[5] for r in lost_all).most_common(10)}")
seen_rej = set()
rej = [r for r in REJECTED if not (r[1] in seen_rej or seen_rej.add(r[1]))]
print(f"\n  same-name matches REJECTED by the rank/kingdom rule: {len(rej)}")
print(f"    by reason: {Counter(('rank' if all(not same_rank(rk.lower(), r[2]) for rk, kg in r[4]) else 'kingdom') for r in rej).most_common()}")
for nm_, x, rk_, kg_, cands in rej[:40]:
    print(f"      {nm_[:34]:34} old: {rk_ or '?'}/{kg_ or '?'}   current: {cands[:3]}")
oldranks = {r for (r,) in old.execute("SELECT DISTINCT rank FROM taxa")}
newr = Counter(r for (r,) in new.execute("SELECT rank FROM taxa") if r not in oldranks)
print(f"  rank values in the new file that the current file never used: {dict(newr.most_common())}")
dang = new.execute("SELECT COUNT(1) FROM taxa WHERE parent_tvk IS NOT NULL AND parent_tvk NOT IN (SELECT tvk FROM taxa)").fetchone()[0]
print(f"  parent links pointing outside the new taxa: {dang} (should be 0)")
dup = new.execute("SELECT COUNT(1) FROM (SELECT lower(scientific_name) n FROM taxa WHERE rank IN ('species','Species') GROUP BY n HAVING COUNT(1)>1)").fetchone()[0]
print(f"  duplicate current species names in taxa: {dup}")


def check(label, tvks):
    tvks = {t for t in tvks if t}
    present = {x for (x,) in new.execute("SELECT tvk FROM taxa")}
    notcur = [t for t in tvks if t not in present]
    maps = [t for t in notcur if to_current(t)]
    print(f"\n  {label}: {len(tvks)} TVKs; not a current taxon in the new file: {len(notcur)}"
          f"  -> map to a current taxon: {len(maps)}   no mapping: {len(notcur) - len(maps)}")
    for t in maps[:5]:
        print(f"      e.g. {nmap.get(t, ('', '?'))[1][:32]:32} {t} -> {T[to_current(t)]['TAXON_NAME']}")


o = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
for tbl in ("observations", "specimens", "recording_scheme"):
    try:
        check(f"observatum {tbl}", {t for (t,) in o.execute(f"SELECT DISTINCT species_tvk FROM {tbl}")})
    except sqlite3.Error:
        pass
c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
check("codex designations (JNCC)", {t for (t,) in c.execute("SELECT DISTINCT tvk FROM designations")})
check("codex species_profiles (accounts)", {t for (t,) in c.execute("SELECT DISTINCT tvk FROM species_profiles")})
print("\n  The current uksi.db is unchanged. Nothing is switched over until you decide.")
