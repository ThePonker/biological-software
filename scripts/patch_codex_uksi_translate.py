"""Patch scripts\\build_codex_db.py so Codex follows a UKSI update.

When uksi.db carries the tables tvk_remap / name_map (written by build_uksi_from_release.py),
every TVK Codex stores is translated to the current taxon at the four points where a TVK
enters a build:
    1. JNCC designations, as read from the spreadsheet
    2. review statuses (manual_entries), restored from the previous codex.db
    3. manual SQS scores, restored
    4. review accounts (species_profiles), restored -- where two old TVKs of the SAME review
       land on one current species, the first is kept and the other reported (the plain
       INSERT would otherwise abort the build on the primary key)
With the current uksi.db (no such tables) nothing is translated: safe to apply now.

  python scripts\\patch_codex_uksi_translate.py          (refuses a second run; keeps a .bak)
"""
import os, py_compile, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "scripts", "build_codex_db.py")
MARK = "_tvk_translator"
t = open(P, encoding="utf-8").read()
if MARK in t:
    sys.exit("  already patched -- nothing done")


def rep(old, new):
    global t
    n = t.count(old)
    if n != 1:
        sys.exit(f"  x expected 1 match, found {n}: {old[:70]!r} -- nothing written")
    t = t.replace(old, new)


# --- the translator, defined before build_codex()
rep('''def build_codex():
    now = datetime.now().isoformat()''',
'''def _tvk_translator():
    """old TVK -> current TVK, from the tvk_remap and name_map tables of the current uksi.db
    (written by build_uksi_from_release.py). Without those tables nothing is translated."""
    used = Counter()
    if not os.path.exists(UKSI_PATH):
        return (lambda t: t), used
    u = sqlite3.connect(f"file:{UKSI_PATH}?mode=ro", uri=True)
    try:
        taxa = {r[0] for r in u.execute("SELECT tvk FROM taxa")}
    except sqlite3.OperationalError:
        return (lambda t: t), used
    rem, nmap = {}, {}
    try:
        rem = {a: b for a, b in u.execute("SELECT old_tvk, new_tvk FROM tvk_remap WHERE new_tvk IS NOT NULL")}
    except sqlite3.OperationalError:
        pass
    try:
        nmap = {a: b for a, b in u.execute("SELECT tvk, recommended_tvk FROM name_map")}
    except sqlite3.OperationalError:
        pass
    u.close()

    def tr(t):
        if not t or t in taxa:
            return t
        n = rem.get(t)
        if n and n != t and n in taxa:
            used["tvk_remap"] += 1
            return n
        n = nmap.get(t)
        if n and n != t and n in taxa:
            used["name_map"] += 1
            return n
        return t
    return tr, used


def build_codex():
    now = datetime.now().isoformat()
    TR, TR_USED = _tvk_translator()''')

# --- 1. JNCC rows
rep('''            tvk = cell(row, "Recommended taxon version")
            if not tvk:
                continue''',
'''            tvk = cell(row, "Recommended taxon version")
            if not tvk:
                continue
            tvk = TR(tvk)                    # JNCC's TVK -> current UKSI taxon (no-op without tvk_remap)''')

# --- 2-4. restored data
rep('''    if manual_statuses:
        # manual_statuses tuple: (tvk, species_name, track, value, detail,''',
'''    manual_statuses = [(TR(r[0]),) + tuple(r[1:]) for r in manual_statuses]
    manual_sqs = [(TR(r[0]), r[1]) for r in manual_sqs]
    if saved_profiles:
        _seen, _kept, _dropped = set(), [], []
        for r in saved_profiles:
            r = (TR(r[0]),) + tuple(r[1:])
            if (r[0], r[1]) in _seen:
                _dropped.append(r)
            else:
                _seen.add((r[0], r[1])); _kept.append(r)
        saved_profiles = _kept
        if _dropped:
            print(f"\\n  ! {len(_dropped)} account(s) landed on a species that already has an account "
                  f"from the same review -- first kept, these not restored:")
            for r in _dropped:
                print(f"      review #{r[1]}  {r[2] or '?'}  -> {r[0]}")
    if TR_USED:
        print(f"\\n  TVKs translated to current UKSI taxa: {dict(TR_USED)}")
    if manual_statuses:
        # manual_statuses tuple: (tvk, species_name, track, value, detail,''')

tmp = P + ".tmp"
open(tmp, "w", encoding="utf-8").write(t)
try:
    py_compile.compile(tmp, doraise=True)
except py_compile.PyCompileError as e:
    os.remove(tmp)
    sys.exit(f"  x patched file does not compile -- nothing written: {e}")
shutil.copy2(P, P + ".bak")
os.replace(tmp, P)
print("  patched scripts\\build_codex_db.py (backup: build_codex_db.py.bak)")
print("  with the current uksi.db nothing is translated; after the UKSI swap it translates automatically")
