"""For each lost name that matters, list every CURRENT taxon in uksi_2025.db whose name
contains its epithet stem (any genus), with rank, family and TVK -- plus what the July
NAMES sheet says about the old name.   READ ONLY

  python scripts\\lookup_lost_names.py
"""
import os, re, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths

NEW = os.path.join(os.path.dirname(str(paths.UKSI_DB)), "uksi_2025.db")
n = sqlite3.connect(f"file:{NEW}?mode=ro", uri=True)

# lost name : epithet stem to search (gender-neutral)
NAMES = [
    # carry data (review accounts / statuses / your records)
    ("Aphodius (Nialus) varians", "varian"), ("Aphodius (Trichonotulus) scrofa", "scrof"),
    ("Ptinus pilosus", "pilos"), ("Morimus funereus", "funere"), ("Morimus funereus", "Morimus"),
    ("Trachelus troglodytus", "troglodyt"), ("Trachelus troglodytus", "Trachelus"),
    ("Megalodontes plagiocephalus", "plagiocephal"), ("Megalodontes plagiocephalus", "Megalodontes"),
    ("Pristiphora micronematica", "micronemat"), ("Oxycera varipes", "Oxycera"),
    ("Lispe hydromyzina", "hydromyz"),
    # British-looking beetles
    ("Aphodius sturmi", "sturm"), ("Aphodius satellitius", "satellit"), ("Nimbus affinis", "Nimbus"),
    ("Bolitobius formosus", "Bolitobius"), ("Lathrobium laevipenne", "laevipenn"), ("Cypha ovulum", "Cypha"),
    ("Atheta gilvicollis", "gilvicoll"), ("Atheta brisouti", "brisout"), ("Cousya defecta", "defect"),
    ("Myllaena graeca", "graec"), ("Ochthebius difficilis", "Ochthebius"), ("Laccobius obscuratus", "obscurat"),
    ("Calathus luctuosus", "Calathus"), ("Tachyura quadrisignata", "quadrisignat"),
    ("Cerylon deplanatum", "Cerylon"), ("Cerophytum elateroides", "elateroid"), ("Cidnopus parvulus", "Cidnopus"),
    ("Otiorhynchus coecus", "Otiorhynchus"), ("Sibinia pellucens", "Sibinia"), ("Miarus salsolae", "salsol"),
    ("Anaspis melanostoma", "Anaspis"), ("Aglyptinus agathidioides", "agathidioid"),
    ("Carpophilus flavipes", "Carpophilus"), ("Hydroporus foveolatus", "foveolat"), ("Otolelus neglectus", "Otolelus"),
    ("Cetonia aurata pallida", "Cetonia"), ("Agabus affinis/unguicularis", "unguicular"),
    # bugs / spiders that look British
    ("Brunotartessus fulvus", "Brunotartessus"), ("Notonecta lutea", "Notonecta"), ("Aphrophora gelida", "Aphrophora"),
    ("Tegenaria pagana", "pagan"), ("Micaria coarctata", "Micaria"),
]
print("Lost names -- current taxa in the July 2025 UKSI   READ ONLY")
print("=" * 100)
for lost, term in NAMES:
    genus_search = term[0].isupper()
    q = "SELECT scientific_name, rank, family, tvk FROM taxa WHERE " + \
        ("scientific_name LIKE ? " if genus_search else "scientific_name LIKE ? AND lower(rank) NOT IN ('genus','subgenus','family','subfamily','tribe')")
    pat = (term + " %") if genus_search else ("% " + term + "%")
    hits = list(n.execute(q + " ORDER BY scientific_name LIMIT 40", (pat,)))
    nm = list(n.execute("SELECT name, recommended_name, name_status FROM name_map WHERE name=? LIMIT 3",
                        (lost.split("/")[0].replace("Aphodius (Nialus) ", "Aphodius ").replace("Aphodius (Trichonotulus) ", "Aphodius "),)))
    print(f"\n  {lost}   [searched: {pat}]   NAMES says: {nm if nm else '-'}")
    if not hits:
        print("      (no current taxon)")
    for s, r, f, t in hits:
        print(f"      {s[:52]:52} {r or '':<12} {f or '(no family)':<22} {t}")
print("\nREAD ONLY -- nothing has been changed.")
