"""
Application Constants.

Controlled value lists and configuration constants.

Note: Application metadata (APP_NAME, APP_VERSION) is in src.core.config.AppConfig
"""

# =============================================================================
# CONTROLLED VALUE LISTS
# =============================================================================

SEX_OPTIONS = ['Female', 'Male', 'Mixed', 'Not recorded']

# iRecord Stage/Life stage termlist
STAGE_OPTIONS = [
    '', 'Adult', 'Teneral', 'Pupa', 'Larva', 'Immature', 'Nymph',
    'Larval web', 'Larval case', 'Leaf-mine', 'Egg', 'Other',
    'Exuvia', 'Flowering', 'Fruiting', 'Gall', 'Not recorded',
    'Spawn', 'Vegetative', 'Juvenile', 'Tadpole', 'Nest',
    'Mature', 'Seedling'
]

CERTAINTY_OPTIONS = ['Certain', 'Likely', 'Uncertain']

# iRecord Sample Method termlist (from https://irecord.org.uk)
SAMPLE_METHOD_OPTIONS = [
    '', 'Unknown', 'Field Observation', 'Quadrat', 'Transect', 'Net',
    'Pitfall Trap', 'Light Trap', 'Transect Section', 'Parent sample',
    'Child sample', 'Timed Count', 'Timed Count Count', 'TreeInitialRegistration',
    'TreeVisit', 'Garden Bird Survey count', 'Visit', 'Seasearch buddy pair',
    'Seasearch habitat', 'Grid square', 'MV Light', 'Actinic Light',
    'Daytime observation', 'Dusking', 'Attracted to a lighted window',
    'Sugaring', 'Wine Roping', 'Beating tray', 'Pheromone trap',
    'Other method (add comment)'
]


VERIFICATION_STATUS_OPTIONS = ['Accepted', 'Unconfirmed', 'Pending', 'Rejected']

# Darwin Core basis of record
BASIS_OF_RECORD_OPTIONS = [
    '', 'HumanObservation', 'MachineObservation', 'PreservedSpecimen',
    'FossilSpecimen', 'LivingSpecimen', 'MaterialSample'
]

# Occurrence status
OCCURRENCE_STATUS_OPTIONS = ['', 'present', 'absent']

# iRecord date type codes
DATE_TYPE_OPTIONS = [
    '',    # Unknown
    'D',   # Day (exact date)
    'DD',  # Day range
    'O',   # Month (1st-15th)
    'OO',  # Month range (1st-15th)
    'P',   # Month (16th-end)
    'M',   # Month
    'MM',  # Month range
    'Y',   # Year
    'YY',  # Year range
    '-Y',  # To year
    'Y-',  # From year
    'U',   # Unknown
    'C',   # Century
]

PREPARATION_TYPE_OPTIONS = ['Pinned', 'Carded', 'Pointed', 'Alcohol', 'Slide', 'Other']

EMBARGO_STATUS_OPTIONS = ['Active', 'Released', 'None']

# Conservation status options
GB_STATUS_OPTIONS = [
    'Nationally Rare', 'Nationally Scarce', 'Notable', 'Local', 'Common'
]

RED_LIST_OPTIONS = [
    'Extinct', 'Critically Endangered', 'Endangered', 'Vulnerable',
    'Near Threatened', 'Least Concern', 'Data Deficient', 'Not Evaluated'
]

LEGISLATIVE_OPTIONS = [
    'Wildlife & Countryside Act',
    'Habitats Directive Annex II',
    'Habitats Directive Annex IV',
    'NERC Act S.41',
    'Bern Convention'
]

# =============================================================================
# DATE FORMATS
# =============================================================================

DATE_FORMAT_OPTIONS = {
    'dd/mm/yyyy': '%d/%m/%Y',
    'yyyy-mm-dd': '%Y-%m-%d',
    'mm/dd/yyyy': '%m/%d/%Y',
}

DEFAULT_DATE_FORMAT = 'dd/mm/yyyy'

# =============================================================================
# GRID REFERENCE FORMATS
# =============================================================================

GRID_REF_FORMAT_OPTIONS = {
    '4-figure': 4,   # 1km precision
    '6-figure': 6,   # 100m precision
    '8-figure': 8,   # 10m precision
    '10-figure': 10, # 1m precision
}

DEFAULT_GRID_REF_FORMAT = '6-figure'

# =============================================================================
# SYNC SETTINGS
# =============================================================================

SYNC_FREQUENCY_OPTIONS = ['Manual', 'Daily', 'Weekly']

# Fields protected from iRecord sync (never overwritten)
PROTECTED_FIELDS = [
    'site_name_local',
    'internal_notes',
    'observation_id',  # specimen link
    'embargo_status',
    'embargo_until',
]

# =============================================================================
# UI SETTINGS
# =============================================================================

FONT_SIZE_OPTIONS = {
    'Small': 10,
    'Medium': 12,
    'Large': 14,
    'Extra Large': 16,
}

DEFAULT_FONT_SIZE = 'Medium'


# =============================================================================
# TAXONOMIC ORDER POSITIONS
# =============================================================================
# Conventional British entomological sequence (Bradley & Fletcher / Kloet & Hincks)
# Used to compute composite taxonomic_sort_key = (order_position * 1000000) + sort_code

INSECT_ORDER_POSITION = {
    "Archaeognatha":  1,   # Bristletails
    "Zygentoma":      2,   # Silverfish
    "Ephemeroptera":  3,   # Mayflies
    "Odonata":        4,   # Dragonflies & Damselflies
    "Plecoptera":     5,   # Stoneflies
    "Dermaptera":     6,   # Earwigs
    "Orthoptera":     7,   # Grasshoppers & Crickets
    "Dictyoptera":    8,   # Cockroaches
    "Mantodea":       9,   # Mantises
    "Phasmatodea":   10,   # Stick Insects
    "Embioptera":    11,   # Webspinners
    "Psocoptera":    12,   # Barklice
    "Phthiraptera":  13,   # Lice
    "Hemiptera":     14,   # True Bugs
    "Thysanoptera":  15,   # Thrips
    "Megaloptera":   16,   # Alderflies
    "Raphidioptera": 17,   # Snakeflies
    "Neuroptera":    18,   # Lacewings
    "Coleoptera":    19,   # Beetles
    "Strepsiptera":  20,   # Twisted-wing Parasites
    "Mecoptera":     21,   # Scorpionflies
    "Siphonaptera":  22,   # Fleas
    "Diptera":       23,   # True Flies
    "Trichoptera":   24,   # Caddisflies
    "Lepidoptera":   25,   # Moths & Butterflies
    "Hymenoptera":   26,   # Bees, Wasps & Ants
}


def compute_taxonomic_sort_key(order_name: str, sort_code: int) -> int:
    """Compute composite taxonomic sort key from order name and UKSI sort_code."""
    order_pos = INSECT_ORDER_POSITION.get(order_name, 99)
    return (order_pos * 1000000) + (sort_code or 0)
