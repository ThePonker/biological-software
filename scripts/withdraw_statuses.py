"""Record statuses a newer review WITHDREW: species it assessed and judged not to
qualify, but left out of its lists -- so the older status was never replaced.

Rule (4 Oct 2026): for a group, the newest review's verdict stands -- whether it
changes a status, removes one, or excludes a species by judgement. Exclusion by
SCOPE (e.g. NECR234 leaving the Tachinidae for a later volume) does not apply.

NECR234 (Falk & Pont 2017), review #21, excluded four species as "neither scarce
nor threatened enough to be included". Their Shirt 1987 / Falk 1991 statuses are
cleared, recorded against review #21 with the reason, as manual entries so the
withdrawal survives every Codex rebuild (a 'none' value = status removed).

Uses resolve / apply_status / key_tiers / backup / CLEAR from
import_status_review.py -- the same rules as every review load.

DRY RUN by default; --apply to write.

Run:  python scripts\\withdraw_statuses.py
      python scripts\\withdraw_statuses.py --apply
"""
import ast, os, sqlite3, sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "scripts")]
import paths

src = open(os.path.join(ROOT, "scripts", "import_status_review.py"), encoding="utf-8-sig").read()
if not any(isinstance(n, ast.If) and "__main__" in ast.dump(n.test) for n in ast.parse(src).body):
    sys.exit("  x import_status_review.py has no __main__ guard -- not importing it")
from import_status_review import resolve, apply_status, key_tiers, backup, CLEAR

_NOT_SCARCE = ("Excluded by NECR234 (Falk & Pont 2017) as 'neither scarce nor threatened enough "
               "to be included'; earlier Shirt 1987 / Falk 1991 status withdrawn")
# name -> (review id whose verdict applies, reason)
SPECIES = {"Phaonia siebecki": (21, _NOT_SCARCE), "Phaonia atriceps": (21, _NOT_SCARCE),
           "Thricops innocuus": (21, _NOT_SCARCE), "Sarcophaga africa": (21, _NOT_SCARCE),
           "Lispe hydromyzina": (21, "Excluded by NECR234 (Falk & Pont 2017) as 'Not British'; "
                                     "Falk 1991 status (Extinct) withdrawn"),
           "Phaonia lugubris": (21, "NECR234: 'the Phaonia lugubris of d'Assis-Fonseca (1968)' is "
                                    "Phaonia meigeni, assessed there (pNS); old name's status superseded"),
           "Sarcophaga exuberans": (21, "NECR234: 'the Sarcophaga exuberans of van Emden (1954)' is "
                                        "Sarcophaga jacobsoni, assessed there (DD); old name's status superseded"),
           "Oxycera varipes": (18, "NECR192 (Drake 2017): Falk 1991 listed it 'in error'; status withdrawn"),
           "Hercostomus nigrocoerulea": (19, "Now Ortochile nigrocoerulea, assessed by NECR195 (Drake 2018, CR); "
                                             "old name's status superseded")}
# NECR217 section 6 -- excluded by judgement
SPECIES.update({
    "Dasiops spatiosus": ("NECR217", "Excluded by NECR217 (Falk, Ismay & Chandler 2016) as '15 Vice-counties' (too widespread to qualify); earlier status withdrawn"),
    "Lonchaea collini": ("NECR217", "Excluded by NECR217 (Falk, Ismay & Chandler 2016) as 'Occurs widely' (too widespread to qualify); earlier status withdrawn"),
    "Lonchaea palposa": ("NECR217", "Excluded by NECR217 (Falk, Ismay & Chandler 2016) as '12 Vice-counties' (too widespread to qualify); earlier status withdrawn"),
    "Lonchaea peregrina": ("NECR217", "Excluded by NECR217 (Falk, Ismay & Chandler 2016) as '17 Vice-counties' (too widespread to qualify); earlier status withdrawn"),
    "Sapromyza basalis": ("NECR217", "Excluded by NECR217 (Falk, Ismay & Chandler 2016) as 'Occurs widely' (too widespread to qualify); earlier status withdrawn"),
    "Sapromyza zetterstedti": ("NECR217", "Excluded by NECR217 (Falk, Ismay & Chandler 2016) as '27 Vice-counties' (too widespread to qualify); earlier status withdrawn"),
    "Anagnota bicolor": ("NECR217", "Excluded by NECR217 (Falk, Ismay & Chandler 2016) as '28 Vice-counties' (too widespread to qualify); earlier status withdrawn"),
    "Periscelis annulipes": ("NECR217", "Excluded by NECR217 (Falk, Ismay & Chandler 2016) as 'Not British'; earlier status withdrawn"),
    "Epichlorops puncticollis": ("NECR217", "Excluded by NECR217 (Falk, Ismay & Chandler 2016) as '26 Vice-counties' (too widespread to qualify); earlier status withdrawn"),
    "Eutropha fulvifrons": ("NECR217", "Excluded by NECR217 (Falk, Ismay & Chandler 2016) as 'Occurs widely' (too widespread to qualify); earlier status withdrawn"),
    "Lasiochaeta pubescens": ("NECR217", "Excluded by NECR217 (Falk, Ismay & Chandler 2016) as 'Occurs widely' (too widespread to qualify); earlier status withdrawn"),
    "Lipara rufitarsis": ("NECR217", "Excluded by NECR217 (Falk, Ismay & Chandler 2016) as 'Occurs widely' (too widespread to qualify); earlier status withdrawn"),
    "Pseudopachychaeta ruficeps": ("NECR217", "Excluded by NECR217 (Falk, Ismay & Chandler 2016) as 'Occurs widely' (too widespread to qualify); earlier status withdrawn"),
    "Trachysiphonella scutellata": ("NECR217", "Excluded by NECR217 (Falk, Ismay & Chandler 2016) as 'Occurs widely' (too widespread to qualify); earlier status withdrawn"),
    "Stegana coleoptrata": ("NECR217", "Excluded by NECR217 (Falk, Ismay & Chandler 2016) as '25 Vice-counties' (too widespread to qualify); earlier status withdrawn"),
})
# NECR217 data-sheet notes
SPECIES.update({
    "Homoneura interstincta": ("NECR217", "NECR217: Falk 1991's material was re-identified as Homoneura mediospinosa "
                                          "(assessed, pNS); true interstincta not yet assessed -- old status withdrawn"),
})
# Hoverflies, Ball & Morris 2014 (Species Status 9), section 5: earlier statuses excluded
# (too widespread, vagrant, or the earlier name of an excluded species)
SPECIES.update({
    "Brachyopa insensilis": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 144 post-1980 hectads Larvae much more readily found than adults but still under-recorded. -- earlier status withdrawn"),
    "Brachypalpus laphriformis": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 122 post-1980 hectads. -- earlier status withdrawn"),
    "Cheilosia soror": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 217 post-1980 hectads. -- earlier status withdrawn"),
    "Criorhina asilica": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 168 post-1980 hectads. -- earlier status withdrawn"),
    "Criorhina ranunculi": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 291 post-1980 hectads. -- earlier status withdrawn"),
    "Didea alneti": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 1 post-1980 hectad. -- earlier status withdrawn"),
    "Didea fasciata": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 348 post-1980 hectads. -- earlier status withdrawn"),
    "Epistrophe diaphana": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 164 post-1980 hectads – range expanding northwards and westwards. -- earlier status withdrawn"),
    "Eristalis rupium": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 190 post-1980 hectads. -- earlier status withdrawn"),
    "Eumerus ornatus": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 143 post-1980 hectads. -- earlier status withdrawn"),
    "Eupeodes bucculatus": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 116 post-1980 records – a conifer woodland species thought to be more widespread. -- earlier status withdrawn"),
    "Metasyrphus latilunulatus": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): Falk (2002) considers that this is a species complex. -- earlier status withdrawn"),
    "Eupeodes lapponicus": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 10 post-1980 hectads .We believe this to be a vagrant. -- earlier status withdrawn"),
    "Metasyrphus lapponicus": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): localities. -- earlier status withdrawn"),
    "Lejogaster tarsata": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 107 post-1980 hectads. -- earlier status withdrawn"),
    "Megasyrphus erraticus": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 96 post-1980 hectads. -- earlier status withdrawn"),
    "Megasyrphus annulipes": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): listed as an earlier name in the excluded table -- earlier status withdrawn"),
    "Melanogaster aerosa": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 123 post-1980 hectads. -- earlier status withdrawn"),
    "Chrysogaster macquarti": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): listed as an earlier name in the excluded table -- earlier status withdrawn"),
    "Meligramma trianguliferum": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 159 post-1980 hectads. -- earlier status withdrawn"),
    "Melangyna triangulifera": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): listed as an earlier name in the excluded table -- earlier status withdrawn"),
    "Microdon myrmicae": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 99 post-1980 hectads. -- earlier status withdrawn"),
    "Neoascia geniculata": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 180 post-1980 hectads. -- earlier status withdrawn"),
    "Neoascia obliqua": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 161 post-1980 hectads. -- earlier status withdrawn"),
    "Orthonevra brevicornis": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 163 post-1980 hectads. -- earlier status withdrawn"),
    "Orthonevra geniculata": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 118 post-1980 hectads. -- earlier status withdrawn"),
    "Pipizella virens": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 225 post-1980 hectads -- earlier status withdrawn"),
    "Platycheirus podagratus": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 128 post-1980 hectads. -- earlier status withdrawn"),
    "Rhingia rostrata": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 209 post-1980 hectads. -- earlier status withdrawn"),
    "Sphegina verecunda": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 235 post-1980 hectads. -- earlier status withdrawn"),
    "Volucella inanis": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 424 post-1980 hectads. -- earlier status withdrawn"),
    "Volucella inflata": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 313 post-1980 hectads. -- earlier status withdrawn"),
    "Volucella zonaria": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 386 post-1980 hectads. -- earlier status withdrawn"),
    "Xanthandrus comtus": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 211 post-1980 hectads. -- earlier status withdrawn"),
    "Xylota florum": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 165 post-1980 hectads. -- earlier status withdrawn"),
    "Xylota jakutorum": ("Species Status 9", "Excluded by Ball & Morris 2014 (Species Status 9): 291 post-1980 hectads. -- earlier status withdrawn"),
})
# NECR217 section 6 -- excluded for 'Taxonomy': withdrawn only with --include-taxonomy
TAXONOMY = {
    "Lonchaea iona": ("NECR217", "NECR217: 'Given the taxonomic confusion surrounding L. iona and L. fraxina, these "
                                 "species are not given a status in this Review' -- earlier status withdrawn"),
    "Lonchaea britteni": ("NECR217", "Excluded by NECR217 (Falk, Ismay & Chandler 2016) as 'Taxonomy' (species concept too uncertain to assess); earlier status withdrawn"),
    "Lonchaea hirticeps": ("NECR217", "Excluded by NECR217 (Falk, Ismay & Chandler 2016) as 'Taxonomy' (species concept too uncertain to assess); earlier status withdrawn"),
    "Chlorops citrinellus": ("NECR217", "Excluded by NECR217 (Falk, Ismay & Chandler 2016) as 'Taxonomy' (species concept too uncertain to assess); earlier status withdrawn"),
    "Chlorops triangularis": ("NECR217", "Excluded by NECR217 (Falk, Ismay & Chandler 2016) as 'Taxonomy' (species concept too uncertain to assess); earlier status withdrawn"),
    "Dicraeus vallaris": ("NECR217", "Excluded by NECR217 (Falk, Ismay & Chandler 2016) as 'Taxonomy' (species concept too uncertain to assess); earlier status withdrawn"),
    "Heleomyza captiosa": ("NECR217", "Excluded by NECR217 (Falk, Ismay & Chandler 2016) as 'Taxonomy' (species concept too uncertain to assess); earlier status withdrawn"),
}
if "--include-taxonomy" in sys.argv:
    SPECIES.update(TAXONOMY)
TRACKS = ("threat_iucn_2001", "threat_iucn_legacy", "rarity_modern", "rarity_legacy")
APPLY = "--apply" in sys.argv

uksi = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
codex = sqlite3.connect(str(paths.CODEX_DB))
c = codex.cursor()
def review(rid):
    if isinstance(rid, str):                       # a report number, e.g. "NECR217"
        r = c.execute("SELECT id FROM reviews WHERE review_name LIKE ?", (f"%({rid})%",)).fetchone()
        if not r:
            sys.exit(f"  x no review loaded for {rid} -- load it first")
        rid = r[0]
    rv = c.execute("SELECT review_name, author, date_published FROM reviews WHERE id=?", (rid,)).fetchone()
    if not rv:
        sys.exit(f"  x review #{rid} not found")
    return f"{rv[0]} ({rv[1]}, {str(rv[2])[:4]})", str(rv[2])

print("Withdraw statuses -- " + ("APPLY" if APPLY else "DRY RUN"))
print("=" * 78)
print()
obs = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
plan = []
for name, (REVIEW_ID, REASON) in SPECIES.items():
    hit = resolve(uksi, name, None)
    if not hit:
        print(f"  x {name}: no UKSI match -- skipped");  continue
    tvk, sci = hit[0], hit[1]
    if sci.split()[:2] != name.split()[:2]:
        # a withdrawal must hit the exact name the report excluded -- never a synonym's
        # current species, which the same review may have assessed (NECR217, 4 Oct)
        print(f"  ! {name}: resolves to a different species ({sci}) -- NOT withdrawn")
        continue
    done = c.execute("""SELECT 1 FROM manual_entries WHERE tvk=? AND added_by='review-withdrawal'""",
                     (tvk,)).fetchone()
    cur = {tr: v for tr, v in c.execute(
        f"SELECT status_track, status_value FROM status_summary WHERE tvk=? AND COALESCE(status_detail,'')='' "
        f"AND status_track IN ({','.join('?' * len(TRACKS))})", (tvk,) + TRACKS)}
    other = [f"{tr}={v}" for tr, v in c.execute(
        f"SELECT status_track, status_value FROM status_summary WHERE tvk=? AND status_track NOT IN "
        f"({','.join('?' * len(TRACKS))})", (tvk,) + TRACKS)]
    n = obs.execute("SELECT COUNT(1) FROM assessment_records WHERE species_tvk=?", (tvk,)).fetchone()[0]
    k0, r0 = key_tiers(cur)
    print(f"  {sci:<24} {tvk}  your records: {n}")
    print(f"      now: {', '.join(f'{t}={v}' for t, v in cur.items()) or 'no threat/rarity status'}"
          f"   key: {'Rare Key' if r0 else 'Key' if k0 else 'no'}")
    if other:
        print(f"      other listings (untouched): {', '.join(other)}")
    if done:
        print("      already withdrawn -- skipped");  continue
    if not cur:
        print("      nothing to clear");  continue
    print(f"      after: no threat/rarity status   key: no")
    print(f"      review {REVIEW_ID}: {REASON}")
    plan.append((tvk, sci, list(cur), REASON, REVIEW_ID))
uksi.close(); obs.close()

print(f"\n  {len(plan)} species to clear, {sum(len(p[2]) for p in plan)} status entries")
if not APPLY:
    sys.exit("\n  DRY RUN -- nothing changed. Re-run with --apply.\n")
if not plan:
    sys.exit("  nothing to do")

print(f"  backup: {backup(paths.CODEX_DB, 'codex')}")
now = datetime.now().isoformat()
try:
    for tvk, sci, tracks, reason, rid in plan:
        source, date = review(rid)
        rid = c.execute("SELECT id FROM reviews WHERE review_name || ' (' || author || ', ' || substr(date_published,1,4) || ')' = ?",
                        (source,)).fetchone()[0]
        for tr in tracks:
            c.execute("""INSERT INTO manual_entries (tvk, species_name, status_track, status_value, status_detail,
                         source_review, date_added, added_by, notes, review_id)
                         VALUES (?,?,?,?,NULL,?,?,?,?,?)""",
                      (tvk, sci, tr, CLEAR, source, date, "review-withdrawal", reason, rid))
            apply_status(c, tvk, tr, CLEAR, None, source, date)
    codex.commit()
except Exception as e:
    codex.rollback()
    sys.exit(f"  x FAILED, rolled back: {type(e).__name__}: {e}")
left = [sci for tvk, sci, _, _r, _i in plan if c.execute(
    f"SELECT 1 FROM status_summary WHERE tvk=? AND status_track IN ({','.join('?' * len(TRACKS))})",
    (tvk,) + TRACKS).fetchone()]
dup = c.execute("""SELECT COUNT(1) FROM (SELECT tvk, status_track, COALESCE(status_detail,'')
                   FROM status_summary GROUP BY 1,2,3 HAVING COUNT(1) > 1)""").fetchone()[0]
print(f"  withdrawn: {len(plan)} species   still holding a threat/rarity status: {left or 'none'}")
print(f"  verify: duplicated statuses {dup} (should be 0)\n")
codex.close()
