"""
Field Entry App - Constants and Configuration.

Column definitions, dropdown options, colors, and CSV mappings.
"""

from typing import List, Tuple, Optional

# =============================================================================
# DROPDOWN OPTIONS (matching Observatum quick entry form)
# =============================================================================

SEX_OPTIONS = ['', 'Female', 'Male', 'Mixed', 'Not recorded']

STAGE_OPTIONS = ['', 'Adult', 'Larva', 'Pupa', 'Egg', 'Nymph', 'Teneral', 'Not recorded']

CERTAINTY_OPTIONS = ['Certain', 'Likely', 'Uncertain']  # Default is first item

# Updated to match iRecord Sample Method termlist
METHOD_OPTIONS = [
    '', 'Field observation', 'Hand search', 'Sweep netting', 'Beating',
    'Grubbing', 'Pitfall trap', 'Light trap', 'Light (MV)', 'Light (LED)',
    'Light (actinic)', 'Malaise trap', 'Flight interception trap',
    'Water trap', 'Pan trap', 'Pheromone trap', 'Window trap',
    'Emergence trap', 'Suction trap', 'Netting', 'Dredging',
    'Litter sieving', 'Bark sieving', 'Carrion trap', 'Dung trap',
    'Reared/bred', 'Dissection', 'Microscopy', 'DNA analysis',
    'Sound recording', 'Trail camera', 'Collected', 'Other'
]

# Data Type - Personal or Commercial recording
DATA_TYPE_OPTIONS = ['Personal', 'Commercial']

# Never Upload options - clearer wording
NEVER_UPLOAD_OPTIONS = ['', 'Never Upload']  # Blank = will upload, text = won't


# =============================================================================
# COLUMN DEFINITIONS
# =============================================================================

# Column tuple: (name, width, editable, auto_populated, combo_options, sticky)
# - name: Display name in header
# - width: Default pixel width
# - editable: Whether user can edit
# - auto_populated: Whether value comes from lookup
# - combo_options: List of dropdown options or None
# - sticky: Whether field can use sticky defaults

COLUMNS = [
    # Species and taxonomy
    ('Species', 200, True, False, None, True),
    ('TVK', 120, False, True, None, False),
    ('Common Name', 150, False, True, None, False),
    ('Family', 100, False, True, None, False),
    ('Order', 100, False, True, None, False),
    
    # Location and date
    ('Date', 100, True, False, None, True),
    ('Grid Ref', 100, True, False, None, True),
    ('Vice County', 120, False, True, None, False),
    ('Location', 150, True, False, None, True),
    
    # Record details
    ('Qty', 50, True, False, None, True),
    ('Sex', 80, True, False, SEX_OPTIONS, True),
    ('Stage', 90, True, False, STAGE_OPTIONS, True),
    ('Method', 120, True, False, METHOD_OPTIONS, True),
    ('Certainty', 90, True, False, CERTAINTY_OPTIONS, True),
    
    # People
    ('Recorder', 120, True, False, None, True),
    ('Determiner', 120, True, False, None, True),
    
    # Notes and flags
    ('Comment', 180, True, False, None, True),
    ('Data Type', 90, True, False, DATA_TYPE_OPTIONS, True),
    ('Never Upload', 100, True, False, NEVER_UPLOAD_OPTIONS, True),
]

# Column indices for quick reference
COL_SPECIES = 0
COL_TVK = 1
COL_COMMON_NAME = 2
COL_FAMILY = 3
COL_ORDER = 4
COL_DATE = 5
COL_GRID_REF = 6
COL_VICE_COUNTY = 7
COL_LOCATION = 8
COL_QTY = 9
COL_SEX = 10
COL_STAGE = 11
COL_METHOD = 12
COL_CERTAINTY = 13
COL_RECORDER = 14
COL_DETERMINER = 15
COL_COMMENT = 16
COL_DATA_TYPE = 17
COL_NEVER_UPLOAD = 18

# Auto-populated columns (from lookups)
AUTO_POPULATED_COLS = [COL_TVK, COL_COMMON_NAME, COL_FAMILY, COL_ORDER, COL_VICE_COUNTY]

# Sticky-enabled columns
STICKY_COLS = [i for i, col in enumerate(COLUMNS) if col[5]]


# =============================================================================
# COLORS (Victorian Naturalist theme)
# =============================================================================

COLORS = {
    # Background
    'bg': '#f8f6f3',
    'surface': '#ffffff',
    'surface_alt': '#f5f4f2',
    
    # Borders
    'border': '#d4d0c8',
    'border_strong': '#b8b4ac',
    
    # Header
    'header_bg': '#e8e4dc',
    'header_text': '#4a4a4a',
    
    # Cells
    'readonly_bg': '#f0eeea',
    'selected_bg': '#cce5ff',
    'grid': '#e0ddd8',
    
    # Validation
    'error_bg': '#fee',
    'error_text': '#c00',
    'warning_bg': '#fff8e0',
    'warning_text': '#996600',
    'success_text': '#2e7d32',
    
    # Accents
    'accent': '#4a7c59',
    'accent_hover': '#3d6649',
    'text': '#333333',
    'text_secondary': '#666666',
}


# =============================================================================
# CSV FIELD MAPPING (iRecord format)
# =============================================================================

# Maps iRecord CSV column names to our internal column indices
IRECORD_COLUMN_MAP = {
    # Species
    'Taxon': COL_SPECIES,
    'Species': COL_SPECIES,
    'Scientific name': COL_SPECIES,
    'TaxonVersionKey': COL_TVK,
    'TVK': COL_TVK,
    'Common name': COL_COMMON_NAME,
    'Vernacular': COL_COMMON_NAME,
    'Family': COL_FAMILY,
    'Order': COL_ORDER,
    
    # Location
    'Date': COL_DATE,
    'Date from': COL_DATE,
    'Original map ref': COL_GRID_REF,
    'Grid ref': COL_GRID_REF,
    'Grid reference': COL_GRID_REF,
    'VC number': COL_VICE_COUNTY,
    'Vice County': COL_VICE_COUNTY,
    'Site name': COL_LOCATION,
    'Location': COL_LOCATION,
    'Location name': COL_LOCATION,
    
    # Record details
    'Quantity': COL_QTY,
    'Count': COL_QTY,
    'Abundance': COL_QTY,
    'Sex': COL_SEX,
    'Stage': COL_STAGE,
    'Life stage': COL_STAGE,
    'Sample method': COL_METHOD,
    'Method': COL_METHOD,
    'Recorder certainty': COL_CERTAINTY,
    'Certainty': COL_CERTAINTY,
    
    # People
    'Recorder': COL_RECORDER,
    'Recorded by': COL_RECORDER,
    'Determiner': COL_DETERMINER,
    'Determined by': COL_DETERMINER,
    'Identifier': COL_DETERMINER,
    
    # Notes and flags
    'Comment': COL_COMMENT,
    'Comments': COL_COMMENT,
    'Notes': COL_COMMENT,
    'Data type': COL_DATA_TYPE,
    'Exclude from iRecord': COL_NEVER_UPLOAD,
    'Never upload': COL_NEVER_UPLOAD,
}

# CSV export headers (iRecord format)
CSV_EXPORT_HEADERS = [
    'Taxon',
    'TaxonVersionKey', 
    'Common name',
    'Family',
    'Order',
    'Date',
    'Grid ref',
    'Vice County',
    'Site name',
    'Quantity',
    'Sex',
    'Stage',
    'Sample method',
    'Recorder certainty',
    'Recorder',
    'Determiner',
    'Comment',
    'Data type',
    'Exclude from iRecord',
]
