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
# JNCC Species Status 1 (water beetles, Table 2), 2 and 3 (flies, section 7): earlier statuses excluded
SPECIES.update({
    "Agabus unguicularis": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (159 hectads since 1980) -- earlier status withdrawn"),
    "Anacaena bipustulata": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (254 hectads since 1980) -- earlier status withdrawn"),
    "Berosus affinis": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (105 hectads since 1980) -- earlier status withdrawn"),
    "Berosus signaticollis": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (109 hectads since 1980) -- earlier status withdrawn"),
    "Cercyon convexiusculus": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (324 hectads since 1980) -- earlier status withdrawn"),
    "Cercyon sternalis": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (108 hectads since 1980) -- earlier status withdrawn"),
    "Cercyon tristis": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (221 hectads since 1980) -- earlier status withdrawn"),
    "Cercyon ustulatus": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (256 hectads since 1980) -- earlier status withdrawn"),
    "Dytiscus circumflexus": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (127 hectads since 1980) -- earlier status withdrawn"),
    "Enochrus affinis": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (154 hectads since 1980) -- earlier status withdrawn"),
    "Enochrus melanocephalus": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (178 hectads since 1980) -- earlier status withdrawn"),
    "Enochrus ochropterus": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (148 hectads since 1980) -- earlier status withdrawn"),
    "Graptodytes granularis": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (122 hectads since 1980) -- earlier status withdrawn"),
    "Gyrinus urinator": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (134 hectads since 1980) -- earlier status withdrawn"),
    "Haliplus heydeni": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (142 hectads since 1980) -- earlier status withdrawn"),
    "Haliplus laminatus": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (128 hectads since 1980) -- earlier status withdrawn"),
    "Helochares lividus": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (429 hectads since 1980) -- earlier status withdrawn"),
    "Helophorus arvernicus": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (189 hectads since 1980) -- earlier status withdrawn"),
    "Helophorus griseus": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (221 hectads since 1980) -- earlier status withdrawn"),
    "Hydraena nigrita": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (144 hectads since 1980) -- earlier status withdrawn"),
    "Hydraena testacea": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (227 hectads since 1980) -- earlier status withdrawn"),
    "Hydroglyphus geminus": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (299 hectads since 1980) -- earlier status withdrawn"),
    "Hydroporus longulus": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (171 hectads since 1980) -- earlier status withdrawn"),
    "Ilybius aenescens": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (127 hectads since 1980) -- earlier status withdrawn"),
    "Ilybius chalconatus": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (196 hectads since 1980) -- earlier status withdrawn"),
    "Ilybius fenestratus": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (169 hectads since 1980) -- earlier status withdrawn"),
    "Ilybius guttiger": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (163 hectads since 1980) -- earlier status withdrawn"),
    "Laccobius sinuatus": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (207 hectads since 1980) -- earlier status withdrawn"),
    "Laccobius ytenensis": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (110 hectads since 1980) -- earlier status withdrawn"),
    "Limnebius nitidus": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (150 hectads since 1980) -- earlier status withdrawn"),
    "Ochthebius bicolon": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (145 hectads since 1980) -- earlier status withdrawn"),
    "Ochthebius marinus": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (110 hectads since 1980) -- earlier status withdrawn"),
    "Prionocyphon serricornis": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (220 hectads since 1980) -- earlier status withdrawn"),
    "Rhantus grapii": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (128 hectads since 1980) -- earlier status withdrawn"),
    "Rhantus suturalis": ("Species Status 1", "Excluded by Foster et al. 2010 (Species Status 1): too widespread to qualify as Nationally Scarce (285 hectads since 1980) -- earlier status withdrawn"),
    "Bolitophila basicornis": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Occurs widely -- earlier status withdrawn"),
    "Bolitophila glabrata": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): At least 42 sites -- earlier status withdrawn"),
    "Bolitophila rossica": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Occurs widely -- earlier status withdrawn"),
    "Macrocera nigricoxa": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Occurs widely -- earlier status withdrawn"),
    "Allodia barbata": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): About 60 sites -- earlier status withdrawn"),
    "Allodia pistillata": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Over 40 sites -- earlier status withdrawn"),
    "Anatella dampfi": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Widely in wetlands -- earlier status withdrawn"),
    "Anatella lenis": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Widely in woods -- earlier status withdrawn"),
    "Boletina dispecta": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Occurs widely -- earlier status withdrawn"),
    "Boletina nitida": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Occurs widely -- earlier status withdrawn"),
    "Boletina pallidula": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): At 39 sites -- earlier status withdrawn"),
    "Boletina rejecta": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Occurs widely -- earlier status withdrawn"),
    "Brachypeza bisignata": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): At least 40 sites -- earlier status withdrawn"),
    "Brevicornu boreale": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Over 40 sites -- earlier status withdrawn"),
    "Brevicornu proximum": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Over 40 sites -- earlier status withdrawn"),
    "Coelosia fusca": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Over 50 sites -- earlier status withdrawn"),
    "Cordyla nitidula": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Occurs widely -- earlier status withdrawn"),
    "Docosia fuscipes": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Occurs widely -- earlier status withdrawn"),
    "Dziedzickia marginata": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): In 15 counties -- earlier status withdrawn"),
    "Epicypta limnophila": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): About 75 sites -- earlier status withdrawn"),
    "Exechia cincta": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): In 13 counties -- earlier status withdrawn"),
    "Exechia exigua": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Occurs widely -- earlier status withdrawn"),
    "Exechia lundstroemi": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Not British -- earlier status withdrawn"),
    "Exechia pseudofestiva": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Occurs widely -- earlier status withdrawn"),
    "Exechiopsis crucigera": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): More than 50 sites -- earlier status withdrawn"),
    "Exechiopsis dumitrescae": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Over 30 sites -- earlier status withdrawn"),
    "Exechiopsis fimbriata": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Over 50 sites -- earlier status withdrawn"),
    "Exechiopsis ligulata": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Over 40 sites -- earlier status withdrawn"),
    "Exechiopsis pollicata": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Over 40 sites -- earlier status withdrawn"),
    "Exechiopsis pseudindecisa": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Occurs widely -- earlier status withdrawn"),
    "Megalopelma nigroclavatum": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): At 56 sites -- earlier status withdrawn"),
    "Megophthalmidia crassicornis": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): More than 50 sites -- earlier status withdrawn"),
    "Mycetophila autumnalis": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): At 32 sites -- earlier status withdrawn"),
    "Mycetophila freyi": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Occurs widely -- earlier status withdrawn"),
    "Mycetophila hetschkoi": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Over 60 sites -- earlier status withdrawn"),
    "Mycetophila magnicauda": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): At about 40 post 1960 sites -- earlier status withdrawn"),
    "Mycetophila mitis": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): At 40 sites -- earlier status withdrawn"),
    "Mycetophila stolida": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Occurs widely -- earlier status withdrawn"),
    "Mycetophila strigata": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): At about 50 sites -- earlier status withdrawn"),
    "Mycomya flavicollis": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Occurs widely -- earlier status withdrawn"),
    "Myrosia maculosa": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Over 20 sites and -- earlier status withdrawn"),
    "Neuratelia nigricornis": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): More than 50 sites -- earlier status withdrawn"),
    "Phronia disgrega": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Occurs widely -- earlier status withdrawn"),
    "Pseudexechia aurivernica": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Over 30 sites -- earlier status withdrawn"),
    "Rymosia placida": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Over 45 sites -- earlier status withdrawn"),
    "Rymosia signatipes": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): More than 40 post -- earlier status withdrawn"),
    "Sceptonia costata": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Occurs widely -- earlier status withdrawn"),
    "Sciophila fenestella": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): At 46 sites -- earlier status withdrawn"),
    "Sciophila nonnisilva": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): At 55 sites -- earlier status withdrawn"),
    "Trichonta vulcani": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Occurs widely -- earlier status withdrawn"),
    "Mycetobia pallipes": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): In 22 counties -- earlier status withdrawn"),
    "Dixella attica": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): About 50 sites -- earlier status withdrawn"),
    "Dixella serotina": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Over 60 sites -- earlier status withdrawn"),
    "Lonchoptera nitidifrons": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): In 20 counties -- earlier status withdrawn"),
    "Cephalops signatus": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): In 11 counties -- earlier status withdrawn"),
    "Dorylomorpha hungarica": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): In 21 counties -- earlier status withdrawn"),
    "Dorylomorpha infirmata": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Occurs widely -- earlier status withdrawn"),
    "Eudorylas montium": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): At least 38 sites -- earlier status withdrawn"),
    "Eudorylas obliquus": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Over 60 sites -- earlier status withdrawn"),
    "Nephrocerus flavicornis": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): In 20 counties -- earlier status withdrawn"),
    "Tomosvaryella palliditarsis": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): At least 40 sites -- earlier status withdrawn"),
    "Crossopalpus curvipes": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 14 counties -- earlier status withdrawn"),
    "Drapetis arcuata": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 14 counties -- earlier status withdrawn"),
    "Drapetis simulans": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 11 counties -- earlier status withdrawn"),
    "Platypalpus albicornis": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 14 counties -- earlier status withdrawn"),
    "Platypalpus albiseta": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 15 counties -- earlier status withdrawn"),
    "Platypalpus albocapillatus": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 16 counties -- earlier status withdrawn"),
    "Platypalpus aristatus": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 18 counties -- earlier status withdrawn"),
    "Platypalpus cothurnatus": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 22 counties -- earlier status withdrawn"),
    "Platypalpus incertus": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 16 counties -- earlier status withdrawn"),
    "Platypalpus leucothrix": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 12 counties -- earlier status withdrawn"),
    "Platypalpus niger": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 15 counties -- earlier status withdrawn"),
    "Platypalpus politus": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 13 counties -- earlier status withdrawn"),
    "Platypalpus ruficornis": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 16 counties -- earlier status withdrawn"),
    "Platypalpus stabilis": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 14 counties -- earlier status withdrawn"),
    "Platypalpus tonsus": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 14 counties -- earlier status withdrawn"),
    "Stilpon sublunatus": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 20 counties -- earlier status withdrawn"),
    "Symballophthalmus fuscitarsis": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 17 counties (with -- earlier status withdrawn"),
    "Symballophthalmus scapularis": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 14 hectads in -- earlier status withdrawn"),
    "Trichina pallipes": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 13 counties -- earlier status withdrawn"),
    "Oedalea tibialis": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 23 counties -- earlier status withdrawn"),
    "Oedalea zetterstedti": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 21 counties -- earlier status withdrawn"),
    "Euthyneura gyllenhali": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 11 counties -- earlier status withdrawn"),
    "Euthyneura halidayi": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 24 counties -- earlier status withdrawn"),
    "Microphor anomalus": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 14 counties -- earlier status withdrawn"),
    "Ragas unica": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 16 counties -- earlier status withdrawn"),
    "Rhamphomyia culicina": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 14 counties -- earlier status withdrawn"),
    "Rhamphomyia morio": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 10 counties -- earlier status withdrawn"),
    "Rhamphomyia nitidula": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 18 counties -- earlier status withdrawn"),
    "Rhamphomyia tibialis": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 13 counties -- earlier status withdrawn"),
    "Empis picipes": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 14 counties -- earlier status withdrawn"),
    "Empis rufiventris": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 13 counties -- earlier status withdrawn"),
    "Empis volucris": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 14 counties -- earlier status withdrawn"),
    "Hilara albipennis": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 9 counties (with 9 hectads in Yorkshire) -- earlier status withdrawn"),
    "Hilara apta": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 12 counties -- earlier status withdrawn"),
    "Hilara clypeata": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 20 counties -- earlier status withdrawn"),
    "Hilara discoidalis": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 14 counties -- earlier status withdrawn"),
    "Hilara morata": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 14 counties -- earlier status withdrawn"),
    "Hilara nigrohirta": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 13 counties -- earlier status withdrawn"),
    "Chelifera subangusta": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 16 counties -- earlier status withdrawn"),
    "Clinocera wesmaelii": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 8 counties (with 11 hectads in Yorkshire) -- earlier status withdrawn"),
    "Sciapus contristans": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 26 counties -- earlier status withdrawn"),
    "Sciapus loewi": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): Synonymy -- earlier status withdrawn"),
    "Dolichopus acuticornis": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 17 counties -- earlier status withdrawn"),
    "Dolichopus andalusiacus": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 10 counties -- earlier status withdrawn"),
    "Dolichopus linearis": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 18 counties -- earlier status withdrawn"),
    "Hercostomus chalybeus": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 22 counties -- earlier status withdrawn"),
    "Sybistroma discipes": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 20 counties -- earlier status withdrawn"),
    "Poecilobothrus principalis": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 16 counties -- earlier status withdrawn"),
    "Orthoceratium lacustre": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 16 counties -- earlier status withdrawn"),
    "Schoenophilus versutus": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 13 counties -- earlier status withdrawn"),
    "Aphrosylus raptor": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 13 counties -- earlier status withdrawn"),
    "Medetera ambigua": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 12 counties -- earlier status withdrawn"),
    "Medetera petrophila": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 12 counties -- earlier status withdrawn"),
    "Thrypticus laetus": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 18 counties -- earlier status withdrawn"),
    "Thrypticus pollinosus": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 12 counties -- earlier status withdrawn"),
    "Rhaphium antennatum": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 17 counties -- earlier status withdrawn"),
    "Rhaphium auctum": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 18 counties -- earlier status withdrawn"),
    "Rhaphium nasutum": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 15 counties -- earlier status withdrawn"),
    "Syntormon fuscipes": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 17 counties -- earlier status withdrawn"),
    "Syntormon zelleri": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 19 counties -- earlier status withdrawn"),
    "Systenus pallipes": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 15 counties -- earlier status withdrawn"),
    "Achalcus melanotrichus": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 14 counties -- earlier status withdrawn"),
    "Neurigona suturalis": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 15 counties -- earlier status withdrawn"),
    "Chrysotus angulicornis": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): Synonymy -- earlier status withdrawn"),
    "Chrysotus collini": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 15 counties -- earlier status withdrawn"),
    "Chrysotus obscuripes": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 18 counties -- earlier status withdrawn"),
    "Chrysotus palustris": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 14 counties -- earlier status withdrawn"),
    "Chrysotus suavis": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 12 counties -- earlier status withdrawn"),
    "Argyra atriceps": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 17 counties -- earlier status withdrawn"),
    "Argyra elongata": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 21 counties -- earlier status withdrawn"),
    "Campsicnemus compeditus": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 18 counties -- earlier status withdrawn"),
    "Campsicnemus marginatus": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 13 counties -- earlier status withdrawn"),
    "Campsicnemus pusillus": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 16 counties -- earlier status withdrawn"),
    "Sympycnus spiculatus": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 16 counties -- earlier status withdrawn"),
    "Micromorphus albipes": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 23 counties -- earlier status withdrawn"),
    "Chrysotimus flaviventris": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 15 counties -- earlier status withdrawn"),
    "Lamprochromus bifasciatus": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 20 counties -- earlier status withdrawn"),
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
TAXONOMY.update({
    "Brevicornu nigrofuscum": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Taxonomy -- earlier status withdrawn"),
    "Chalarus argenteus": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Taxonomy -- earlier status withdrawn"),
    "Chalarus basalis": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Taxonomy -- earlier status withdrawn"),
    "Chalarus griseus": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Taxonomy -- earlier status withdrawn"),
    "Chalarus parmenteri": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Taxonomy -- earlier status withdrawn"),
    "Eudorylas dissimilis": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Taxonomy -- earlier status withdrawn"),
    "Eudorylas inferus": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Taxonomy -- earlier status withdrawn"),
    "Eudorylas jenkinsoni": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Taxonomy -- earlier status withdrawn"),
    "Pipunculus fonsecai": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Taxonomy -- earlier status withdrawn"),
    "Pipunculus hertzogi": ("Species Status 2", "Excluded by Falk et al. 2005 (Species Status 2): Taxonomy -- earlier status withdrawn"),
    "Dolichocephala ocellata": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): 10 counties (taxonomic problems cited in section 6) -- earlier status withdrawn"),
    "Medetera borealis": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): Taxonomic status uncertain -- earlier status withdrawn"),
    "Medetera jugalis": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): Taxonomic status uncertain -- earlier status withdrawn"),
    "Medetera nitida": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): Taxonomic status uncertain -- earlier status withdrawn"),
    "Medetera oscillans": ("Species Status 3", "Excluded by Falk et al. 2005 (Species Status 3): Taxonomic status uncertain -- earlier status withdrawn"),
})
if "--include-taxonomy" in sys.argv:
    SPECIES.update(TAXONOMY)
TRACKS = ("threat_iucn_2001", "threat_iucn_legacy", "rarity_modern", "rarity_legacy")
APPLY = "--apply" in sys.argv

uksi = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
codex = sqlite3.connect(str(paths.CODEX_DB))
c = codex.cursor()
def _year(d, src=""):
    import re as _re
    s = str(d or "").strip()
    if _re.fullmatch(r"\d{5}(\.0)?", s):
        from datetime import date as _d, timedelta as _td
        return (_d(1899, 12, 30) + _td(days=int(float(s)))).year
    m = _re.match(r"(19|20)\d{2}", s) or _re.search(r"\b(19[5-9]\d|20[0-2]\d)\b", str(src or ""))
    return int(m.group(0)) if m else 0


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
    rows = c.execute(
        f"SELECT status_track, status_value, source, date_designated FROM status_summary WHERE tvk=? "
        f"AND COALESCE(status_detail,'')='' AND status_track IN ({','.join('?' * len(TRACKS))})", (tvk,) + TRACKS).fetchall()
    cur = {tr: v for tr, v, s, d in rows}
    # newest review wins: an exclusion only withdraws statuses OLDER than the excluding review.
    # A status from a later review (e.g. Drake 2018 after Falk & Crossley 2005) is kept.
    rev_year = _year(review(REVIEW_ID)[1])
    newer = {tr: (v, s, _year(d, s)) for tr, v, s, d in rows if _year(d, s) >= rev_year > 0}
    older = {tr: v for tr, v in cur.items() if tr not in newer}
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
    if newer:
        print("      kept -- newer than the exclusion (" + str(rev_year) + "): "
              + ", ".join(f"{tr}={v} ({y}, {s[:35]})" for tr, (v, s, y) in newer.items()))
    if not older:
        print("      nothing older to clear");  continue
    k1, r1 = key_tiers({tr: v for tr, (v, s, y) in newer.items()})
    print(f"      after: {', '.join(f'{t}={v}' for t, (v, s, y) in newer.items()) or 'no threat/rarity status'}"
          f"   key: {'Rare Key' if r1 else 'Key' if k1 else 'no'}")
    print(f"      review {REVIEW_ID}: {REASON}")
    plan.append((tvk, sci, list(older), REASON, REVIEW_ID))
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
left = [sci for tvk, sci, trs, _r, _i in plan for tr in trs if c.execute(
    "SELECT 1 FROM status_summary WHERE tvk=? AND status_track=? AND COALESCE(status_detail,'')=''",
    (tvk, tr)).fetchone()]                          # only the tracks this run cleared must be gone
dup = c.execute("""SELECT COUNT(1) FROM (SELECT tvk, status_track, COALESCE(status_detail,'')
                   FROM status_summary GROUP BY 1,2,3 HAVING COUNT(1) > 1)""").fetchone()[0]
print(f"  withdrawn: {len(plan)} species   cleared tracks still present: {left or "none"}")
print(f"  verify: duplicated statuses {dup} (should be 0)\n")
codex.close()
