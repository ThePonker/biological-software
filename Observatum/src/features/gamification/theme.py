"""
Observatum V2 Gamification Theme
================================
All design tokens, colours, and styling constants.
Dark Victorian naturalist aesthetic.

Single source of truth - change values here to update everywhere.
"""

from typing import Dict, Optional


# =============================================================================
# BACKGROUND & BASE COLOURS
# =============================================================================

BACKGROUND = {
    "primary": "#1a1a2e",      # Main window background
    "secondary": "#252542",    # Card/panel background
    "surface": "#2a2a3e",      # Elevated surfaces
    "border": "#333355",       # Borders
}

TEXT = {
    "primary": "#eeeeee",
    "secondary": "#aaaaaa",
    "muted": "#888888",
    "accent": "#c9a227",       # Gold accent
}

PAPER = {
    "cream": "#f5f0e6",        # Light cream for hovers
    "parchment": "#e8dcc8",    # Darker parchment
    "aged": "#d4c4a8",         # Aged paper
}


# =============================================================================
# TROPHY TIER COLOURS (Medals & Rosettes)
# =============================================================================

TROPHY_TIERS = {
    "bronze": {
        "primary": "#cd7f32",
        "highlight": "#ffc080",
        "shadow": "#602810",
        "vignette_light": "#503828",
        "vignette_dark": "#281810",
    },
    "silver": {
        "primary": "#c8c8c8",
        "highlight": "#ffffff",
        "shadow": "#505050",
        "vignette_light": "#404050",
        "vignette_dark": "#1a1a28",
    },
    "gold": {
        "primary": "#ffc000",
        "highlight": "#ffffa0",
        "shadow": "#705000",
        "vignette_light": "#403820",
        "vignette_dark": "#1a1808",
    },
    "platinum": {
        "primary": "#d8d8e8",
        "highlight": "#ffffff",
        "shadow": "#606080",
        "vignette_light": "#454560",
        "vignette_dark": "#1a1a30",
        "glow": "rgba(220, 225, 240, 0.5)",
    },
}


# =============================================================================
# TAXONOMIC GROUP COLOURS (Family Ribbons & Medals)
# =============================================================================

TAXONOMIC_GROUPS = {
    "insects": {
        "primary": "#c9a227",
        "highlight": "#e8b84a",
        "shadow": "#8b6914",
        "vignette_light": "#3a3425",
        "vignette_dark": "#1f1a10",
    },
    "other_invertebrates": {
        "primary": "#a07850",
        "highlight": "#c4956a",
        "shadow": "#6b4f35",
        "vignette_light": "#352a20",
        "vignette_dark": "#1a1510",
    },
    "vertebrates": {
        "primary": "#2d8a8a",
        "highlight": "#5ab5b0",
        "shadow": "#1a5f60",
        "vignette_light": "#1f3535",
        "vignette_dark": "#101a1a",
    },
    "plants": {
        "primary": "#4a7c45",
        "highlight": "#6b9b5a",
        "shadow": "#2d5a2a",
        "vignette_light": "#253025",
        "vignette_dark": "#101810",
    },
    "fungi": {
        "primary": "#7c5a78",
        "highlight": "#a87ca0",
        "shadow": "#503850",
        "vignette_light": "#302530",
        "vignette_dark": "#181018",
    },
    "other": {
        "primary": "#a89880",
        "highlight": "#c8b8a0",
        "shadow": "#787060",
        "vignette_light": "#302d28",
        "vignette_dark": "#181715",
    },
}


# =============================================================================
# VICE COUNTY REGIONAL COLOURS
# =============================================================================

VC_REGIONS = {
    "england": {
        "primary": "#CE1124",
        "highlight": "#ff4050",
        "shadow": "#900a18",
        "vignette_light": "#401520",
        "vignette_dark": "#200a10",
        "vc_range": (1, 63),
        "letter": "E",
    },
    "wales": {
        "primary": "#00AB39",
        "highlight": "#40e070",
        "shadow": "#007028",
        "vignette_light": "#153520",
        "vignette_dark": "#0a1a10",
        "vc_range": (41, 52),
        "letter": "W",
    },
    "scotland": {
        "primary": "#0065BD",
        "highlight": "#40a0f0",
        "shadow": "#004080",
        "vignette_light": "#152540",
        "vignette_dark": "#0a1220",
        "vc_range": (72, 112),
        "letter": "S",
    },
    "ireland": {
        "primary": "#169B62",
        "highlight": "#40d890",
        "shadow": "#0a6840",
        "vignette_light": "#153828",
        "vignette_dark": "#0a1c14",
        "vc_range": None,  # H1-H40
        "letter": "I",
    },
}


# =============================================================================
# RARITY TIER COLOURS (Pins)
# =============================================================================

RARITY_TIERS = {
    "uncommon": {
        "primary": "#60a8e0",
        "highlight": "#a0d0f0",
        "shadow": "#3080c0",
        "vignette_light": "#203848",
        "vignette_dark": "#101c28",
    },
    "rare": {
        "primary": "#20c0a0",
        "highlight": "#50e0c0",
        "shadow": "#109070",
        "vignette_light": "#183830",
        "vignette_dark": "#0c1c18",
    },
    "very_rare": {
        "primary": "#ffc020",
        "highlight": "#ffe060",
        "shadow": "#d09000",
        "vignette_light": "#403818",
        "vignette_dark": "#201c0c",
    },
    "critical": {
        "primary": "#e03050",
        "highlight": "#ff6070",
        "shadow": "#a01830",
        "vignette_light": "#401828",
        "vignette_dark": "#200c14",
    },
    "protected": {
        "primary": "#a060d0",
        "highlight": "#d090f0",
        "shadow": "#7030a0",
        "vignette_light": "#382048",
        "vignette_dark": "#1c1028",
        "glow": "rgba(180, 100, 220, 0.5)",
    },
}

# Mapping from UKSI designations to our tiers
RARITY_DESIGNATION_MAP = {
    "NS": "uncommon",
    "NR": "rare",
    "RDB3": "rare",
    "Nb": "rare",
    "Na": "rare",
    "RDB2": "very_rare",
    "RDBI": "very_rare",
    "VU": "very_rare",
    "RDB1": "critical",
    "EN": "critical",
    "CR": "critical",
    "Schedule 5": "protected",
    "Schedule 8": "protected",
}


# =============================================================================
# PROGRESSION TIER COLOURS (6 stages for Shields)
# =============================================================================

PROGRESSION_STAGES = {
    "beginner": {
        "tiers": (1, 2, 3, 4),
        "primary": "#6a9058",
        "highlight": "#90b080",
        "shadow": "#4a7040",
        "vignette_light": "#283828",
        "vignette_dark": "#141c14",
    },
    "developing": {
        "tiers": (5, 6, 7, 8),
        "primary": "#40a098",
        "highlight": "#60c0b8",
        "shadow": "#207870",
        "vignette_light": "#1a3535",
        "vignette_dark": "#0c1a1a",
    },
    "experienced": {
        "tiers": (9, 10, 11, 12),
        "primary": "#4080c0",
        "highlight": "#70a8e0",
        "shadow": "#285898",
        "vignette_light": "#1a2840",
        "vignette_dark": "#0c1420",
    },
    "advanced": {
        "tiers": (13, 14, 15, 16),
        "primary": "#9058b0",
        "highlight": "#b080d0",
        "shadow": "#684090",
        "vignette_light": "#302040",
        "vignette_dark": "#181020",
    },
    "master": {
        "tiers": (17, 18, 19),
        "primary": "#e0b020",
        "highlight": "#ffd860",
        "shadow": "#b08800",
        "vignette_light": "#383020",
        "vignette_dark": "#1c1810",
        "glow": "rgba(224, 176, 32, 0.4)",
    },
    "platinum": {
        "tiers": (20,),
        "primary": "#d8d8e8",
        "highlight": "#f0f0f8",
        "shadow": "#606080",
        "vignette_light": "#454560",
        "vignette_dark": "#1a1a30",
        "glow": "rgba(220, 225, 240, 0.5)",
    },
}


# =============================================================================
# TIER DEFINITIONS (All 20)
# =============================================================================

TIERS = [
    # Scale 1: 100 species per tier (Tiers 1-4)
    {"tier": 1, "name": "Junior Naturalist", "min_species": 0, "max_species": 100, "stage": "beginner"},
    {"tier": 2, "name": "Apprentice Naturalist", "min_species": 101, "max_species": 200, "stage": "beginner"},
    {"tier": 3, "name": "Budding Naturalist", "min_species": 201, "max_species": 300, "stage": "beginner"},
    {"tier": 4, "name": "Keen Naturalist", "min_species": 301, "max_species": 400, "stage": "beginner"},
    # Scale 2: 500 species per tier (Tiers 5-8)
    {"tier": 5, "name": "Dedicated Naturalist", "min_species": 401, "max_species": 900, "stage": "developing"},
    {"tier": 6, "name": "Practised Naturalist", "min_species": 901, "max_species": 1400, "stage": "developing"},
    {"tier": 7, "name": "Skilled Naturalist", "min_species": 1401, "max_species": 1900, "stage": "developing"},
    {"tier": 8, "name": "Seasoned Naturalist", "min_species": 1901, "max_species": 2400, "stage": "developing"},
    # Scale 3: 1000 species per tier (Tiers 9-12)
    {"tier": 9, "name": "Accomplished Naturalist", "min_species": 2401, "max_species": 3400, "stage": "experienced"},
    {"tier": 10, "name": "Expert Naturalist", "min_species": 3401, "max_species": 4400, "stage": "experienced"},
    {"tier": 11, "name": "Adept Naturalist", "min_species": 4401, "max_species": 5400, "stage": "experienced"},
    {"tier": 12, "name": "Proficient Naturalist", "min_species": 5401, "max_species": 6400, "stage": "experienced"},
    # Scale 4: 5000 species per tier (Tiers 13-16)
    {"tier": 13, "name": "Distinguished Naturalist", "min_species": 6401, "max_species": 11400, "stage": "advanced"},
    {"tier": 14, "name": "Eminent Naturalist", "min_species": 11401, "max_species": 16400, "stage": "advanced"},
    {"tier": 15, "name": "Renowned Naturalist", "min_species": 16401, "max_species": 21400, "stage": "advanced"},
    {"tier": 16, "name": "Illustrious Naturalist", "min_species": 21401, "max_species": 26400, "stage": "advanced"},
    # Scale 5: 10000 species per tier (Tiers 17-20)
    {"tier": 17, "name": "Grand Naturalist", "min_species": 26401, "max_species": 36400, "stage": "master"},
    {"tier": 18, "name": "Supreme Naturalist", "min_species": 36401, "max_species": 46400, "stage": "master"},
    {"tier": 19, "name": "Legendary Naturalist", "min_species": 46401, "max_species": 56400, "stage": "master"},
    {"tier": 20, "name": "Eternal Guardian of Living Knowledge", "min_species": 56401, "max_species": None, "stage": "platinum"},
]


# =============================================================================
# FAMILY DEPTH THRESHOLDS
# =============================================================================

FAMILY_SIZE_THRESHOLDS = {
    "tiny": {"min": 1, "max": 2, "bronze": 1, "silver": 1, "gold_pct": 1.0},
    "very_small": {"min": 3, "max": 5, "bronze": 2, "silver": 3, "gold_pct": 0.5},
    "small": {"min": 6, "max": 15, "bronze": 3, "silver": 5, "gold_pct": 0.5},
    "medium": {"min": 16, "max": 30, "bronze": 5, "silver": 10, "gold_pct": 0.5},
    "large": {"min": 31, "max": 75, "bronze": 8, "silver": 20, "gold_pct": 0.5},
    "very_large": {"min": 76, "max": 150, "bronze": 12, "silver": 35, "gold_pct": 0.5},
    "huge": {"min": 151, "max": 300, "bronze": 20, "silver": 60, "gold_pct": 0.5},
    "massive": {"min": 301, "max": 500, "bronze": 30, "silver": 100, "gold_pct": 0.5},
    "giant": {"min": 501, "max": None, "bronze": 50, "silver": 150, "gold_pct": 0.5},
}


# =============================================================================
# RARE SPECIES MILESTONES
# =============================================================================

RARE_MILESTONES = [
    {"name": "First Find", "threshold": 1, "trophy_tier": "bronze"},
    {"name": "Keen Eye", "threshold": 10, "trophy_tier": "bronze"},
    {"name": "Rarity Seeker", "threshold": 25, "trophy_tier": "silver"},
    {"name": "Rarity Specialist", "threshold": 50, "trophy_tier": "silver"},
    {"name": "Rarity Master", "threshold": 100, "trophy_tier": "gold"},
    {"name": "Rarity Legend", "threshold": 250, "trophy_tier": "platinum"},
]


# =============================================================================
# ICON SIZES
# =============================================================================

ICON_SIZES = {
    "small": 48,
    "medium": 80,
    "large": 120,
}


# =============================================================================
# UI SETTINGS
# =============================================================================

UI_SETTINGS = {
    "font_family": "Georgia",
    "font_family_fallback": "serif",
    "animation": False,
    "notification_timeout_ms": 10000,
    "glow_blur_radius": 8,
}


# =============================================================================
# ORDER → TAXONOMIC GROUP MAPPING
# =============================================================================

ORDER_TO_GROUP = {
    # Insects
    "Coleoptera": "insects",
    "Lepidoptera": "insects",
    "Diptera": "insects",
    "Hymenoptera": "insects",
    "Hemiptera": "insects",
    "Odonata": "insects",
    "Orthoptera": "insects",
    "Trichoptera": "insects",
    "Ephemeroptera": "insects",
    "Plecoptera": "insects",
    "Neuroptera": "insects",
    "Mecoptera": "insects",
    "Dermaptera": "insects",
    "Blattodea": "insects",
    "Mantodea": "insects",
    "Phasmida": "insects",
    "Thysanoptera": "insects",
    "Psocoptera": "insects",
    "Phthiraptera": "insects",
    "Siphonaptera": "insects",
    "Raphidioptera": "insects",
    "Megaloptera": "insects",
    "Strepsiptera": "insects",
    
    # Other Invertebrates
    "Araneae": "other_invertebrates",
    "Opiliones": "other_invertebrates",
    "Acari": "other_invertebrates",
    "Pseudoscorpiones": "other_invertebrates",
    "Isopoda": "other_invertebrates",
    "Amphipoda": "other_invertebrates",
    "Decapoda": "other_invertebrates",
    "Chilopoda": "other_invertebrates",
    "Diplopoda": "other_invertebrates",
    "Gastropoda": "other_invertebrates",
    "Bivalvia": "other_invertebrates",
    
    # Vertebrates
    "Passeriformes": "vertebrates",
    "Anseriformes": "vertebrates",
    "Charadriiformes": "vertebrates",
    "Accipitriformes": "vertebrates",
    "Strigiformes": "vertebrates",
    "Columbiformes": "vertebrates",
    "Piciformes": "vertebrates",
    "Squamata": "vertebrates",
    "Testudines": "vertebrates",
    "Anura": "vertebrates",
    "Caudata": "vertebrates",
    "Rodentia": "vertebrates",
    "Chiroptera": "vertebrates",
    "Carnivora": "vertebrates",
    "Cetartiodactyla": "vertebrates",
    "Eulipotyphla": "vertebrates",
    "Lagomorpha": "vertebrates",
    
    # Fungi
    "Agaricales": "fungi",
    "Boletales": "fungi",
    "Polyporales": "fungi",
    "Russulales": "fungi",
    "Pezizales": "fungi",
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_tier_for_species_count(count: int) -> dict:
    """Return tier info for a given species count."""
    for tier in TIERS:
        if tier["max_species"] is None:
            if count >= tier["min_species"]:
                return tier
        elif tier["min_species"] <= count <= tier["max_species"]:
            return tier
    return TIERS[0]


def get_stage_colours(stage: str) -> dict:
    """Return colour palette for a progression stage."""
    return PROGRESSION_STAGES.get(stage, PROGRESSION_STAGES["beginner"])


def get_family_thresholds(family_size: int) -> dict:
    """Return trophy thresholds for a family of given size."""
    for category, thresholds in FAMILY_SIZE_THRESHOLDS.items():
        max_size = thresholds["max"]
        if max_size is None:
            if family_size >= thresholds["min"]:
                return thresholds
        elif thresholds["min"] <= family_size <= max_size:
            return thresholds
    return FAMILY_SIZE_THRESHOLDS["tiny"]


def get_rarity_tier(designation: str) -> Optional[str]:
    """Return rarity tier name for a designation string."""
    if not designation:
        return None
    designation = designation.strip()
    # Direct lookup
    if designation in RARITY_DESIGNATION_MAP:
        return RARITY_DESIGNATION_MAP[designation]
    # Check if designation contains any key
    for key, tier in RARITY_DESIGNATION_MAP.items():
        if key in designation:
            return tier
    return None


def get_region_for_vc(vc_number: int) -> str:
    """Return region name for a vice county number."""
    if vc_number is None:
        return "england"
    # Wales is 41-52 (subset of what would be England range)
    if 41 <= vc_number <= 52:
        return "wales"
    # England is 1-40 and 53-71
    if (1 <= vc_number <= 40) or (53 <= vc_number <= 71):
        return "england"
    # Scotland is 72-112
    if 72 <= vc_number <= 112:
        return "scotland"
    return "england"


def get_taxonomic_group(order_name: str) -> str:
    """Return taxonomic group for an order name."""
    if not order_name:
        return "other"
    return ORDER_TO_GROUP.get(order_name, "other")


def get_vc_counts() -> Dict[str, int]:
    """Return count of VCs per region."""
    return {
        "england": 63,  # 1-40 + 53-71 (excluding Wales)
        "wales": 12,    # 41-52
        "scotland": 41, # 72-112
        "ireland": 40,  # H1-H40 (future)
        "total": 112,   # GB total (excluding Ireland for now)
    }


# =============================================================================
# ONE-TIME ACHIEVEMENTS (Daily/Annual Records)
# =============================================================================

# Taxonomic group colours for seals
SEAL_COLOURS = {
    "general": "#c9a227",      # Gold
    "birds": "#2d8a8a",        # Teal (vertebrates)
    "butterflies": "#c9a227",  # Gold (insects)
    "moths": "#c9a227",        # Gold (insects)
    "dragonflies": "#c9a227",  # Gold (insects)
    "plants": "#4a7c45",       # Green
    "hoverflies": "#c9a227",   # Gold (insects)
    "beetles": "#c9a227",      # Gold (insects)
    "aculeates": "#c9a227",    # Gold (insects)
    "spiders": "#a07850",      # Brown (other invertebrates)
    "fungi": "#7c5a78",        # Purple
}

# Icon file paths for seal centre icons (relative to assets/icons/groups/)
# When file exists, it will be used. Otherwise falls back to generic sun/calendar.
GROUP_ICONS = {
    "general": None,                    # Use sun/calendar
    "birds": "birds.svg",               # Bird silhouette
    "butterflies": "butterflies.svg",   # Butterfly silhouette
    "moths": "moths.svg",               # Moth silhouette
    "dragonflies": "dragonflies.svg",   # Dragonfly silhouette
    "plants": "plants.svg",             # Leaf/flower silhouette
    "hoverflies": "hoverflies.svg",     # Hoverfly silhouette
    "beetles": "beetles.svg",           # Beetle silhouette
    "aculeates": "aculeates.svg",       # Bee silhouette
    "spiders": "spiders.svg",           # Spider silhouette
    "fungi": "fungi.svg",               # Mushroom silhouette
}

# Orders that belong to each achievement group (for filtering observations)
ACHIEVEMENT_GROUP_ORDERS = {
    "general": None,  # All orders
    "birds": ["Passeriformes", "Anseriformes", "Charadriiformes", "Accipitriformes", 
              "Strigiformes", "Columbiformes", "Piciformes", "Falconiformes",
              "Gruiformes", "Podicipediformes", "Gaviiformes", "Procellariiformes",
              "Pelecaniformes", "Suliformes", "Ciconiiformes", "Phoenicopteriformes",
              "Galliformes", "Caprimulgiformes", "Apodiformes", "Cuculiformes",
              "Coraciiformes", "Bucerotiformes"],
    "butterflies": ["Lepidoptera"],  # Filtered to Rhopalocera families
    "moths": ["Lepidoptera"],  # Filtered to Heterocera families
    "dragonflies": ["Odonata"],
    "plants": None,  # Kingdom = Plantae
    "hoverflies": ["Diptera"],  # Family = Syrphidae
    "beetles": ["Coleoptera"],
    "aculeates": ["Hymenoptera"],  # Filtered to aculeate families
    "spiders": ["Araneae"],
    "fungi": None,  # Kingdom = Fungi
}

# Butterfly families (Rhopalocera)
BUTTERFLY_FAMILIES = [
    "Papilionidae", "Pieridae", "Lycaenidae", "Nymphalidae", 
    "Hesperiidae", "Riodinidae"
]

# Hoverfly family
HOVERFLY_FAMILIES = ["Syrphidae"]

# Aculeate families (bees, wasps, ants)
ACULEATE_FAMILIES = [
    "Apidae", "Megachilidae", "Andrenidae", "Halictidae", "Colletidae",
    "Melittidae", "Vespidae", "Pompilidae", "Crabronidae", "Sphecidae",
    "Formicidae", "Mutillidae", "Tiphiidae", "Chrysididae"
]

ONE_TIME_ACHIEVEMENTS = [
    # =========================================================================
    # GENERAL - Daily
    # =========================================================================
    {"id": "gen_day_10", "name": "The Apprentice's Outing", "threshold": 10, "period": "daily", "group": "general"},
    {"id": "gen_day_25", "name": "A Productive Ramble", "threshold": 25, "period": "daily", "group": "general"},
    {"id": "gen_day_50", "name": "The Half-Century Mark", "threshold": 50, "period": "daily", "group": "general"},
    {"id": "gen_day_100", "name": "The Centurion's Honour", "threshold": 100, "period": "daily", "group": "general"},
    {"id": "gen_day_200", "name": "The Double Centurion", "threshold": 200, "period": "daily", "group": "general"},
    {"id": "gen_day_300", "name": "The Tercentenary Achievement", "threshold": 300, "period": "daily", "group": "general"},
    {"id": "gen_day_400", "name": "The Quadricentennial", "threshold": 400, "period": "daily", "group": "general"},
    {"id": "gen_day_500", "name": "The Quingentenary Triumph", "threshold": 500, "period": "daily", "group": "general"},
    {"id": "gen_day_1000", "name": "The Grand Millenary", "threshold": 1000, "period": "daily", "group": "general"},
    
    # GENERAL - Annual
    {"id": "gen_year_100", "name": "The Amateur's Pursuit", "threshold": 100, "period": "annual", "group": "general"},
    {"id": "gen_year_500", "name": "The Devoted Naturalist", "threshold": 500, "period": "annual", "group": "general"},
    {"id": "gen_year_1000", "name": "The Seasoned Collector", "threshold": 1000, "period": "annual", "group": "general"},
    {"id": "gen_year_2000", "name": "The Comprehensive Recorder", "threshold": 2000, "period": "annual", "group": "general"},
    {"id": "gen_year_3000", "name": "The Distinguished Cataloguer", "threshold": 3000, "period": "annual", "group": "general"},
    {"id": "gen_year_4000", "name": "The Eminent Surveyor", "threshold": 4000, "period": "annual", "group": "general"},
    {"id": "gen_year_5000", "name": "The Illustrious Chronicler", "threshold": 5000, "period": "annual", "group": "general"},
    
    # =========================================================================
    # BIRDS - Daily
    # =========================================================================
    {"id": "bird_day_25", "name": "The Morning's Chorus", "threshold": 25, "period": "daily", "group": "birds"},
    {"id": "bird_day_50", "name": "A Respectable Day's Ornithology", "threshold": 50, "period": "daily", "group": "birds"},
    {"id": "bird_day_100", "name": "The Ornithologist's Century", "threshold": 100, "period": "daily", "group": "birds"},
    {"id": "bird_day_150", "name": "The Exceptional Avifaunal Survey", "threshold": 150, "period": "daily", "group": "birds"},
    
    # BIRDS - Annual
    {"id": "bird_year_100", "name": "The Parish Ornithologist", "threshold": 100, "period": "annual", "group": "birds"},
    {"id": "bird_year_150", "name": "The County Recorder", "threshold": 150, "period": "annual", "group": "birds"},
    {"id": "bird_year_200", "name": "The Diligent Observer", "threshold": 200, "period": "annual", "group": "birds"},
    {"id": "bird_year_250", "name": "The Keen-Eyed Watcher", "threshold": 250, "period": "annual", "group": "birds"},
    {"id": "bird_year_300", "name": "The Accomplished Ornithologist", "threshold": 300, "period": "annual", "group": "birds"},
    {"id": "bird_year_350", "name": "The Distinguished Ornithologist", "threshold": 350, "period": "annual", "group": "birds"},
    
    # =========================================================================
    # BUTTERFLIES - Daily
    # =========================================================================
    {"id": "bfly_day_10", "name": "The Lepidopterist's Stroll", "threshold": 10, "period": "daily", "group": "butterflies"},
    {"id": "bfly_day_20", "name": "A Fine Day's Netting", "threshold": 20, "period": "daily", "group": "butterflies"},
    {"id": "bfly_day_30", "name": "The Abundant Meadow", "threshold": 30, "period": "daily", "group": "butterflies"},
    {"id": "bfly_day_40", "name": "The Exceptional Emergence", "threshold": 40, "period": "daily", "group": "butterflies"},
    
    # BUTTERFLIES - Annual
    {"id": "bfly_year_30", "name": "The Amateur's Collection", "threshold": 30, "period": "annual", "group": "butterflies"},
    {"id": "bfly_year_40", "name": "The Enthusiast's Cabinet", "threshold": 40, "period": "annual", "group": "butterflies"},
    {"id": "bfly_year_50", "name": "The Accomplished Cabinet", "threshold": 50, "period": "annual", "group": "butterflies"},
    {"id": "bfly_year_55", "name": "The Complete British Series", "threshold": 55, "period": "annual", "group": "butterflies"},
    
    # =========================================================================
    # MOTHS - Nightly
    # =========================================================================
    {"id": "moth_night_25", "name": "The Lamplighter's Reward", "threshold": 25, "period": "daily", "group": "moths"},
    {"id": "moth_night_50", "name": "A Profitable Evening", "threshold": 50, "period": "daily", "group": "moths"},
    {"id": "moth_night_100", "name": "The Bountiful Trap", "threshold": 100, "period": "daily", "group": "moths"},
    {"id": "moth_night_200", "name": "The Magnificent Assembly", "threshold": 200, "period": "daily", "group": "moths"},
    {"id": "moth_night_300", "name": "The Entomologist's Treasure", "threshold": 300, "period": "daily", "group": "moths"},
    
    # MOTHS - Annual
    {"id": "moth_year_250", "name": "The Nocturnal Apprentice", "threshold": 250, "period": "annual", "group": "moths"},
    {"id": "moth_year_500", "name": "The Devoted Moth-Hunter", "threshold": 500, "period": "annual", "group": "moths"},
    {"id": "moth_year_750", "name": "The Seasoned Noctuist", "threshold": 750, "period": "annual", "group": "moths"},
    {"id": "moth_year_1000", "name": "The Distinguished Heterocera Scholar", "threshold": 1000, "period": "annual", "group": "moths"},
    {"id": "moth_year_1500", "name": "The Grand Master of Moths", "threshold": 1500, "period": "annual", "group": "moths"},
    
    # =========================================================================
    # DRAGONFLIES - Daily
    # =========================================================================
    {"id": "odo_day_10", "name": "The Waterside Wanderer", "threshold": 10, "period": "daily", "group": "dragonflies"},
    {"id": "odo_day_20", "name": "The Keen Dragon-Hunter", "threshold": 20, "period": "daily", "group": "dragonflies"},
    {"id": "odo_day_30", "name": "The Exceptional Odonatist", "threshold": 30, "period": "daily", "group": "dragonflies"},
    
    # DRAGONFLIES - Annual
    {"id": "odo_year_20", "name": "The Pond Enthusiast", "threshold": 20, "period": "annual", "group": "dragonflies"},
    {"id": "odo_year_30", "name": "The Wetland Devotee", "threshold": 30, "period": "annual", "group": "dragonflies"},
    {"id": "odo_year_40", "name": "The Complete Dragon Master", "threshold": 40, "period": "annual", "group": "dragonflies"},
    
    # =========================================================================
    # PLANTS - Daily
    # =========================================================================
    {"id": "plant_day_50", "name": "The Botanist's Constitutional", "threshold": 50, "period": "daily", "group": "plants"},
    {"id": "plant_day_100", "name": "The Field Naturalist's Survey", "threshold": 100, "period": "daily", "group": "plants"},
    {"id": "plant_day_200", "name": "The Comprehensive Flora", "threshold": 200, "period": "daily", "group": "plants"},
    {"id": "plant_day_300", "name": "The Botanical Expedition", "threshold": 300, "period": "daily", "group": "plants"},
    
    # PLANTS - Annual
    {"id": "plant_year_200", "name": "The Herbarium Founder", "threshold": 200, "period": "annual", "group": "plants"},
    {"id": "plant_year_500", "name": "The Devoted Botanist", "threshold": 500, "period": "annual", "group": "plants"},
    {"id": "plant_year_1000", "name": "The Flora Compiler", "threshold": 1000, "period": "annual", "group": "plants"},
    {"id": "plant_year_1500", "name": "The Distinguished Phytologist", "threshold": 1500, "period": "annual", "group": "plants"},
    
    # =========================================================================
    # HOVERFLIES - Daily
    # =========================================================================
    {"id": "hover_day_10", "name": "The Flower Visitor's Observer", "threshold": 10, "period": "daily", "group": "hoverflies"},
    {"id": "hover_day_20", "name": "The Syrphid Enthusiast", "threshold": 20, "period": "daily", "group": "hoverflies"},
    {"id": "hover_day_30", "name": "The Accomplished Dipterist", "threshold": 30, "period": "daily", "group": "hoverflies"},
    {"id": "hover_day_40", "name": "The Exceptional Syrphidologist", "threshold": 40, "period": "daily", "group": "hoverflies"},
    
    # HOVERFLIES - Annual
    {"id": "hover_year_50", "name": "The Novice Syrphidologist", "threshold": 50, "period": "annual", "group": "hoverflies"},
    {"id": "hover_year_100", "name": "The Practised Hoverfly Hunter", "threshold": 100, "period": "annual", "group": "hoverflies"},
    {"id": "hover_year_150", "name": "The Distinguished Dipterist", "threshold": 150, "period": "annual", "group": "hoverflies"},
    {"id": "hover_year_200", "name": "The Syrphid Grand Master", "threshold": 200, "period": "annual", "group": "hoverflies"},
    
    # =========================================================================
    # BEETLES - Daily
    # =========================================================================
    {"id": "beetle_day_20", "name": "The Beetle Collector's Day", "threshold": 20, "period": "daily", "group": "beetles"},
    {"id": "beetle_day_50", "name": "The Productive Excursion", "threshold": 50, "period": "daily", "group": "beetles"},
    {"id": "beetle_day_100", "name": "The Coleopterist's Triumph", "threshold": 100, "period": "daily", "group": "beetles"},
    
    # BEETLES - Annual
    {"id": "beetle_year_100", "name": "The Novice Coleopterist", "threshold": 100, "period": "annual", "group": "beetles"},
    {"id": "beetle_year_250", "name": "The Devoted Beetle Hunter", "threshold": 250, "period": "annual", "group": "beetles"},
    {"id": "beetle_year_500", "name": "The Accomplished Coleopterist", "threshold": 500, "period": "annual", "group": "beetles"},
    {"id": "beetle_year_1000", "name": "The Grand Coleopterist", "threshold": 1000, "period": "annual", "group": "beetles"},
    
    # =========================================================================
    # BEES, WASPS & ANTS - Daily
    # =========================================================================
    {"id": "acul_day_10", "name": "The Apiarist's Observation", "threshold": 10, "period": "daily", "group": "aculeates"},
    {"id": "acul_day_25", "name": "The Hymenopterist's Harvest", "threshold": 25, "period": "daily", "group": "aculeates"},
    {"id": "acul_day_40", "name": "The Exceptional Aculeate Survey", "threshold": 40, "period": "daily", "group": "aculeates"},
    
    # BEES, WASPS & ANTS - Annual
    {"id": "acul_year_50", "name": "The Novice Hymenopterist", "threshold": 50, "period": "annual", "group": "aculeates"},
    {"id": "acul_year_100", "name": "The Industrious Recorder", "threshold": 100, "period": "annual", "group": "aculeates"},
    {"id": "acul_year_150", "name": "The Distinguished Aculeate Scholar", "threshold": 150, "period": "annual", "group": "aculeates"},
    {"id": "acul_year_200", "name": "The Hymenoptera Grand Master", "threshold": 200, "period": "annual", "group": "aculeates"},
    
    # =========================================================================
    # SPIDERS - Daily
    # =========================================================================
    {"id": "spider_day_10", "name": "The Web Seeker", "threshold": 10, "period": "daily", "group": "spiders"},
    {"id": "spider_day_25", "name": "The Arachnologist's Day", "threshold": 25, "period": "daily", "group": "spiders"},
    {"id": "spider_day_50", "name": "The Spider Hunter's Triumph", "threshold": 50, "period": "daily", "group": "spiders"},
    
    # SPIDERS - Annual
    {"id": "spider_year_50", "name": "The Novice Arachnologist", "threshold": 50, "period": "annual", "group": "spiders"},
    {"id": "spider_year_100", "name": "The Practised Spider Scholar", "threshold": 100, "period": "annual", "group": "spiders"},
    {"id": "spider_year_200", "name": "The Distinguished Arachnologist", "threshold": 200, "period": "annual", "group": "spiders"},
    {"id": "spider_year_300", "name": "The Arachnid Grand Master", "threshold": 300, "period": "annual", "group": "spiders"},
    
    # =========================================================================
    # FUNGI - Daily
    # =========================================================================
    {"id": "fungi_day_20", "name": "The Woodland Foray", "threshold": 20, "period": "daily", "group": "fungi"},
    {"id": "fungi_day_50", "name": "The Mycologist's Ramble", "threshold": 50, "period": "daily", "group": "fungi"},
    {"id": "fungi_day_100", "name": "The Bountiful Foray", "threshold": 100, "period": "daily", "group": "fungi"},
    {"id": "fungi_day_150", "name": "The Exceptional Fungal Harvest", "threshold": 150, "period": "daily", "group": "fungi"},
    
    # FUNGI - Annual
    {"id": "fungi_year_100", "name": "The Novice Mycologist", "threshold": 100, "period": "annual", "group": "fungi"},
    {"id": "fungi_year_250", "name": "The Devoted Fungus Hunter", "threshold": 250, "period": "annual", "group": "fungi"},
    {"id": "fungi_year_500", "name": "The Accomplished Mycologist", "threshold": 500, "period": "annual", "group": "fungi"},
    {"id": "fungi_year_750", "name": "The Distinguished Mycologist", "threshold": 750, "period": "annual", "group": "fungi"},
]


def get_achievements_by_group(group: str) -> list:
    """Return all achievements for a specific taxonomic group."""
    return [a for a in ONE_TIME_ACHIEVEMENTS if a["group"] == group]


def get_achievements_by_period(period: str) -> list:
    """Return all achievements for a specific period (daily/annual)."""
    return [a for a in ONE_TIME_ACHIEVEMENTS if a["period"] == period]


def get_seal_colour(group: str) -> str:
    """Return the seal colour for a taxonomic group."""
    return SEAL_COLOURS.get(group, "#c9a227")
