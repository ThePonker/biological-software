"""Examen -- presentation helpers shared by the screen, the workbook and the reports (E8).

One home for three things the views and exports would otherwise each write for
themselves:

    status_name("NS")            -> "Nationally Scarce"   (codes as names, E8a)
    status_names("NT, NS, S41")  -> "Near Threatened, Nationally Scarce, Section 41"
    vernacular("", "Carabidae", "Coleoptera") -> "A ground beetle"   (E8b fallback)
    SQI_SCALE / SQI_TOOLTIP      what the SQI number means (E8c)

The code -> name pairs are also what the Conservation tab lists, so a code cannot be
named one way there and another in the species table.
"""
from __future__ import annotations

# ---- conservation status codes -> names ------------------------------------
# Threat (IUCN 2001 and pre-2001 Red Data Book), rarity (current and legacy), and the
# short labels Codex gives priority listings (codex_repository._priority_label).
STATUS_NAMES = {
    "CR": "Critically Endangered",
    "EN": "Endangered",
    "VU": "Vulnerable",
    "NT": "Near Threatened",
    "DD": "Data Deficient",
    "LC": "Least Concern",
    "RE": "Regionally Extinct",
    "EX": "Extinct",
    "RDB1": "Red Data Book 1",
    "RDB2": "Red Data Book 2",
    "RDB3": "Red Data Book 3",
    "RDBK": "Red Data Book K",
    "RDBI": "Red Data Book I",
    "NR": "Nationally Rare",
    "NS": "Nationally Scarce",
    "Na": "Notable A",
    "Nb": "Notable B",
    "Notable": "Notable",
    "Priority": "Priority species",
    "S41": "Section 41",
    "S41 (research only)": "Section 41 (research only)",
    "Wales S7": "Wales Section 7",
    "SBL": "Scottish Biodiversity List",
    "NI Priority": "Northern Ireland priority",
    "UK BAP": "UK BAP priority",
    "UK BAP (research only)": "UK BAP (research only)",
}


def status_name(code) -> str:
    """The name for one status code; anything unrecognised is returned unchanged."""
    c = " ".join(str(code or "").split())
    if not c:
        return ""
    if c in STATUS_NAMES:
        return STATUS_NAMES[c]
    compact = c.replace(" ", "")
    if compact.upper() in STATUS_NAMES:                 # "RDB 1", "rdbk"
        return STATUS_NAMES[compact.upper()]
    if c.startswith("Legal ("):                         # "Legal (2)"
        return "Legally protected " + c[len("Legal "):]
    if c.startswith("Legal:"):                          # "Legal: WCA Sch5" (EXA10)
        return "Legally protected: " + c[len("Legal:"):].strip()
    return c


def status_names(text) -> str:
    """A comma-separated status string with each code named."""
    return ", ".join(status_name(p) for p in str(text or "").split(",") if p.strip())


# ---- vernacular fallback ----------------------------------------------------
# Where UKSI holds no common name, a description of the group: family first, then
# order. A description, not a name -- it always starts "A"/"An".
FAMILY_NOUN = {
    # beetles
    "Carabidae": "ground beetle", "Staphylinidae": "rove beetle", "Curculionidae": "weevil",
    "Apionidae": "weevil", "Brentidae": "weevil", "Nanophyidae": "weevil",
    "Erirhinidae": "weevil", "Dryophthoridae": "weevil", "Attelabidae": "leaf-rolling weevil",
    "Rhynchitidae": "leaf-rolling weevil", "Anthribidae": "fungus weevil",
    "Chrysomelidae": "leaf beetle", "Coccinellidae": "ladybird", "Elateridae": "click beetle",
    "Eucnemidae": "false click beetle", "Throscidae": "false click beetle",
    "Cerambycidae": "longhorn beetle", "Scarabaeidae": "scarab beetle",
    "Aphodiidae": "dung beetle", "Geotrupidae": "dor beetle", "Lucanidae": "stag beetle",
    "Dytiscidae": "diving beetle", "Hydrophilidae": "water scavenger beetle",
    "Haliplidae": "crawling water beetle", "Gyrinidae": "whirligig beetle",
    "Hydraenidae": "minute moss beetle", "Elmidae": "riffle beetle", "Scirtidae": "marsh beetle",
    "Cantharidae": "soldier beetle", "Lampyridae": "glow-worm", "Lycidae": "net-winged beetle",
    "Melyridae": "soft-winged flower beetle", "Malachiidae": "soft-winged flower beetle",
    "Dasytidae": "soft-winged flower beetle", "Cleridae": "chequered beetle",
    "Nitidulidae": "sap beetle", "Kateretidae": "sap beetle",
    "Cryptophagidae": "silken fungus beetle", "Latridiidae": "minute scavenger beetle",
    "Leiodidae": "round fungus beetle", "Silphidae": "carrion beetle", "Histeridae": "clown beetle",
    "Buprestidae": "jewel beetle", "Ptinidae": "spider or woodworm beetle",
    "Anobiidae": "woodworm beetle", "Mordellidae": "tumbling flower beetle",
    "Oedemeridae": "false blister beetle", "Pyrochroidae": "cardinal beetle",
    "Tenebrionidae": "darkling beetle", "Melandryidae": "false darkling beetle",
    "Dermestidae": "hide beetle", "Byrrhidae": "pill beetle", "Ciidae": "tree-fungus beetle",
    "Mycetophagidae": "hairy fungus beetle", "Erotylidae": "pleasing fungus beetle",
    "Endomychidae": "handsome fungus beetle", "Anthicidae": "ant-like flower beetle",
    "Scraptiidae": "false flower beetle", "Ptiliidae": "featherwing beetle",
    "Phalacridae": "shining flower beetle", "Monotomidae": "root-eating beetle",
    "Silvanidae": "flat bark beetle", "Laemophloeidae": "lined flat bark beetle",
    "Cucujidae": "flat bark beetle", "Zopheridae": "cylindrical bark beetle",
    "Salpingidae": "narrow-waisted bark beetle", "Aderidae": "ant-like leaf beetle",
    "Bostrichidae": "auger beetle", "Trogossitidae": "bark-gnawing beetle",
    "Clambidae": "fringe-winged beetle", "Corylophidae": "minute hooded beetle",
    "Heteroceridae": "variegated mud-loving beetle", "Dryopidae": "long-toed water beetle",
    "Sphindidae": "slime mould beetle", "Biphyllidae": "false skin beetle",
    "Cerylonidae": "minute bark beetle", "Lymexylidae": "ship-timber beetle",
    # spiders
    "Linyphiidae": "money spider", "Lycosidae": "wolf spider", "Salticidae": "jumping spider",
    "Thomisidae": "crab spider", "Philodromidae": "running crab spider",
    "Araneidae": "orb-weaver spider", "Tetragnathidae": "long-jawed orb-weaver spider",
    "Theridiidae": "comb-footed spider", "Gnaphosidae": "ground spider",
    "Clubionidae": "sac spider", "Pisauridae": "nursery-web spider",
    "Dictynidae": "mesh-web spider", "Agelenidae": "funnel-web spider",
    "Hahniidae": "lesser cobweb spider",
    # flies
    "Syrphidae": "hoverfly", "Tipulidae": "cranefly", "Limoniidae": "cranefly",
    "Pediciidae": "cranefly", "Cylindrotomidae": "cranefly", "Asilidae": "robberfly",
    "Tabanidae": "horsefly", "Stratiomyidae": "soldierfly", "Bombyliidae": "bee-fly",
    "Conopidae": "thick-headed fly", "Tephritidae": "picture-winged fly",
    "Ulidiidae": "picture-winged fly", "Dolichopodidae": "long-legged fly",
    "Empididae": "dance fly", "Hybotidae": "dagger fly", "Muscidae": "muscid fly",
    "Calliphoridae": "blow fly", "Sarcophagidae": "flesh fly", "Tachinidae": "parasitic fly",
    "Sciomyzidae": "snail-killing fly", "Mycetophilidae": "fungus gnat",
    "Sciaridae": "dark-winged fungus gnat", "Chironomidae": "non-biting midge",
    "Ceratopogonidae": "biting midge", "Culicidae": "mosquito", "Psychodidae": "moth fly",
    "Bibionidae": "St Mark's fly", "Rhagionidae": "snipe fly", "Xylophagidae": "awl-fly",
    "Therevidae": "stiletto fly", "Anthomyiidae": "root-maggot fly",
    "Fanniidae": "lesser house fly", "Scathophagidae": "dung fly",
    "Sphaeroceridae": "lesser dung fly", "Sepsidae": "black scavenger fly",
    "Chloropidae": "frit fly", "Agromyzidae": "leaf-mining fly", "Drosophilidae": "fruit fly",
    "Pipunculidae": "big-headed fly", "Platypezidae": "flat-footed fly",
    "Phoridae": "scuttle fly", "Ephydridae": "shore fly", "Micropezidae": "stilt-legged fly",
    "Lonchopteridae": "spear-winged fly", "Opomyzidae": "grass fly",
    "Lauxaniidae": "lauxaniid fly",
    # bees, wasps, ants, sawflies
    "Apidae": "bee", "Andrenidae": "mining bee", "Halictidae": "furrow bee",
    "Colletidae": "plasterer or yellow-faced bee", "Megachilidae": "leafcutter or mason bee",
    "Melittidae": "bee", "Formicidae": "ant", "Vespidae": "social or potter wasp",
    "Crabronidae": "solitary wasp", "Sphecidae": "digger wasp",
    "Pompilidae": "spider-hunting wasp", "Chrysididae": "ruby-tailed wasp",
    "Ichneumonidae": "ichneumon wasp", "Braconidae": "braconid wasp",
    "Cynipidae": "gall wasp", "Mutillidae": "velvet ant", "Tenthredinidae": "sawfly",
    "Argidae": "sawfly", "Cimbicidae": "sawfly", "Diprionidae": "sawfly",
    "Siricidae": "horntail", "Xiphydriidae": "wood wasp",
    # true bugs
    "Miridae": "plant bug", "Lygaeidae": "ground bug", "Rhyparochromidae": "ground bug",
    "Pentatomidae": "shieldbug", "Acanthosomatidae": "shieldbug", "Scutelleridae": "shieldbug",
    "Cydnidae": "burrower bug", "Coreidae": "squashbug", "Rhopalidae": "rhopalid bug",
    "Alydidae": "broad-headed bug", "Anthocoridae": "flower bug", "Nabidae": "damsel bug",
    "Reduviidae": "assassin bug", "Tingidae": "lace bug", "Saldidae": "shore bug",
    "Berytidae": "stilt bug", "Cicadellidae": "leafhopper", "Delphacidae": "planthopper",
    "Cixiidae": "lacehopper", "Cercopidae": "froghopper", "Aphrophoridae": "froghopper",
    "Membracidae": "treehopper", "Psyllidae": "jumping plant louse",
    "Triozidae": "jumping plant louse", "Aphididae": "aphid", "Corixidae": "water boatman",
    "Notonectidae": "backswimmer", "Gerridae": "pond skater",
    # butterflies and moths
    "Nymphalidae": "butterfly", "Lycaenidae": "butterfly", "Pieridae": "butterfly",
    "Papilionidae": "butterfly", "Riodinidae": "butterfly", "Hesperiidae": "skipper butterfly",
    "Geometridae": "geometer moth", "Crambidae": "grass moth", "Tortricidae": "tortrix moth",
    "Sphingidae": "hawk-moth", "Zygaenidae": "burnet or forester moth",
    "Sesiidae": "clearwing moth", "Pterophoridae": "plume moth",
    "Gracillariidae": "leaf-mining moth", "Nepticulidae": "leaf-mining moth",
    # grasshoppers, dragonflies, others
    "Acrididae": "grasshopper", "Tettigoniidae": "bush-cricket", "Tetrigidae": "groundhopper",
    "Gryllidae": "cricket", "Coenagrionidae": "damselfly", "Lestidae": "damselfly",
    "Calopterygidae": "damselfly", "Platycnemididae": "damselfly", "Aeshnidae": "hawker dragonfly",
    "Libellulidae": "chaser or darter dragonfly", "Chrysopidae": "green lacewing",
    "Hemerobiidae": "brown lacewing", "Coniopterygidae": "dustywing",
    "Asellidae": "water louse",
}

ORDER_NOUN = {
    "Coleoptera": "beetle", "Araneae": "spider", "Diptera": "fly", "Hymenoptera": "bee, wasp or ant",
    "Hemiptera": "true bug", "Lepidoptera": "moth", "Orthoptera": "grasshopper or cricket",
    "Odonata": "dragonfly or damselfly", "Isopoda": "woodlouse", "Opiliones": "harvestman",
    "Pseudoscorpiones": "pseudoscorpion", "Neuroptera": "lacewing", "Trichoptera": "caddisfly",
    "Ephemeroptera": "mayfly", "Plecoptera": "stonefly", "Dermaptera": "earwig",
    "Mecoptera": "scorpionfly", "Raphidioptera": "snakefly", "Megaloptera": "alderfly",
    "Thysanoptera": "thrips", "Psocodea": "barkfly or louse", "Psocoptera": "barkfly",
    "Blattodea": "cockroach", "Siphonaptera": "flea", "Strepsiptera": "twisted-wing parasite",
    "Julida": "millipede", "Polydesmida": "millipede", "Chordeumatida": "millipede",
    "Glomerida": "pill millipede", "Polyzoniida": "millipede", "Polyxenida": "bristly millipede",
    "Lithobiomorpha": "centipede", "Geophilomorpha": "centipede",
    "Scolopendromorpha": "centipede", "Entomobryomorpha": "springtail",
    "Poduromorpha": "springtail", "Symphypleona": "springtail", "Collembola": "springtail",
    "Stylommatophora": "land snail or slug", "Hygrophila": "freshwater snail",
    "Mesostigmata": "mite", "Trombidiformes": "mite", "Sarcoptiformes": "mite",
    "Ixodida": "tick", "Amphipoda": "amphipod", "Haplotaxida": "earthworm",
    "Crassiclitellata": "earthworm",
}


def _with_article(noun: str) -> str:
    return ("An " if noun[:1].lower() in "aeiou" else "A ") + noun


def group_description(family="", order="") -> str:
    """'A ground beetle', 'A spider' -- or '' where the group is not in the table."""
    noun = FAMILY_NOUN.get((family or "").strip()) or ORDER_NOUN.get((order or "").strip())
    return _with_article(noun) if noun else ""


def vernacular(common="", family="", order="") -> str:
    """The common name, or a group description where there is none (blank if unknown)."""
    return (common or "").strip() or group_description(family, order)


def is_description(common, shown) -> bool:
    """True where `shown` is a fallback description rather than a real common name."""
    return bool(shown) and not (common or "").strip()


# ---- what the SQI number means ----------------------------------------------
SQI_SCALE = ("SQI (Species Quality Index): the mean Species Quality Score of the species "
             "Pantheon analysed, × 100. A species of no conservation status scores 1, "
             "Nationally Scarce or Notable 4, Nationally Rare or Vulnerable 8, Endangered 16 "
             "and Critically Endangered 32; species analysed without a score count as 0. "
             "So 100 means every species is common, and the higher the figure the larger "
             "the share of scarce and threatened species. No published benchmarks.")

SQI_CAPTION = "SQI: Species Quality Index — 100 = all species common; higher = more scarce species"

SQI_TOOLTIP = SQI_SCALE + "\nPantheon flags an SQI from fewer than 15 scoring species (▲)."
