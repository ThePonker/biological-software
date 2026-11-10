# Recording Scheme Import Wizard

## Overview

A multi-step wizard for importing recording scheme data into Observatum V2 from:
- **iRecord CSV downloads** - Auto-detects format, maps columns automatically
- **NBN Atlas CSV downloads** - Auto-detects format, includes Darwin Core fields
- **Generic CSV files** - Manual column mapping with fuzzy matching assistance

## Installation

1. Copy the entire `scheme_import_wizard` folder to:
   ```
   src/views/dialogs/scheme_import_wizard/
   ```

2. The folder should contain these files:
   ```
   scheme_import_wizard/
   ├── __init__.py
   ├── scheme_import_wizard.py      (Main wizard class)
   ├── validation_worker.py         (Validation logic)
   ├── wizard_pages_mixin.py        (Page creation)
   ├── wizard_file_mixin.py         (File handling)
   ├── wizard_validation_mixin.py   (Validation UI)
   ├── wizard_import_mixin.py       (Import execution)
   └── CHANGES.md                   (This file)
   ```

3. **Database Schema Update** (if not already done):
   ```sql
   ALTER TABLE recording_scheme ADD COLUMN nbn_atlas_id TEXT;
   ALTER TABLE recording_scheme ADD COLUMN occurrence_id TEXT;
   ALTER TABLE recording_scheme ADD COLUMN taxon_author TEXT;
   ALTER TABLE recording_scheme ADD COLUMN phylum TEXT;
   ALTER TABLE recording_scheme ADD COLUMN class_name TEXT;
   ALTER TABLE recording_scheme ADD COLUMN genus TEXT;
   ALTER TABLE recording_scheme ADD COLUMN country TEXT;
   ALTER TABLE recording_scheme ADD COLUMN state_province TEXT;
   ```

## Usage

### In recording_scheme_tab.py

Add an import button to the toolbar and connect it:

```python
from src.views.dialogs.scheme_import_wizard import SchemeImportWizard

# In toolbar setup:
self.import_btn = QPushButton("Import Data")
self.import_btn.clicked.connect(self._on_import_clicked)

# Handler:
def _on_import_clicked(self):
    wizard = SchemeImportWizard(
        parent=self,
        uksi_model=self.uksi_model,
        vc_service=self.vc_service,
        db=self.db,
    )
    wizard.import_completed.connect(self._on_import_completed)
    wizard.exec()

def _on_import_completed(self, count: int):
    """Refresh the table after import."""
    self._load_data()
    QMessageBox.information(self, "Import Complete", f"Imported {count} records.")
```

## Features

### Mode Selection
- **iRecord**: Detects iRecord CSV format (ID, RecordKey, Taxon, etc.)
- **NBN Atlas**: Detects NBN format (NBN Atlas record ID, Scientific name, etc.)
- **Generic CSV**: Manual mapping with fuzzy matching suggestions

### Auto-Detection
When a file is loaded, the wizard detects if it's iRecord or NBN Atlas format
based on column headers and automatically selects the appropriate mode.

### Column Mapping
- Organized by groups (Required, Location, People, Occurrence, Taxonomy, etc.)
- Auto-maps known columns for iRecord/NBN formats
- Fuzzy matching for generic CSVs
- Required fields marked with *

### Validation
- Live progress with counts (Valid/Warning/Error)
- UKSI species lookup and taxonomy auto-population
- Grid reference validation with VC lookup
- Duplicate detection (by iRecord ID, NBN ID, or species+date+grid)
- Inline editing for generic mode
- Export problems to CSV

### Import Options
- Skip duplicates (default)
- Update existing records with new data
- Progress bar with live counts

## File Structure

| File | Lines | Purpose |
|------|-------|---------|
| scheme_import_wizard.py | ~280 | Main wizard class, navigation |
| validation_worker.py | ~500 | Background validation thread |
| wizard_pages_mixin.py | ~450 | Page UI creation |
| wizard_file_mixin.py | ~300 | File handling, format detection |
| wizard_validation_mixin.py | ~350 | Validation UI, filtering |
| wizard_import_mixin.py | ~250 | Import execution |

## Supported Columns

### iRecord Columns (Auto-mapped)
- ID, RecordKey, External key, Source, Taxon, TaxonVersionKey
- Common name, Taxon group, Kingdom, Order, Family, Rank
- Date interpreted, Date from, Output map ref, Site name
- Vice County, VC number, Latitude, Longitude
- Recorder, Determiner, Sex, Stage, Sample method
- Verification status 1/2, Verifier, Comment, Images, Licence

### NBN Atlas Columns (Auto-mapped)
- NBN Atlas record ID, Occurrence ID, Scientific name, Species ID (TVK)
- Common name, Taxon author, Taxon Rank, Kingdom, Phylum, Class
- Order, Family, Genus, Event Date, Grid reference, Locality
- Country, State/Province, Latitude (WGS84), Longitude (WGS84)
- Recorder, Determiner, Sex, Life stage, Individual count
- Identification verification status, Occurrence remarks, Licence

## Theming

Uses Dusty Purple accent color (TabColors.RECORDING_SCHEME) to match
the Recording Scheme tab styling. All UI components follow the
centralized theme system.

## Dependencies

- PySide6
- src.themes (theme function)
- src.core.config (TabColors, ButtonColors)
- src.services.vc_lookup_service (VCLookupService)
- UKSI model for species lookups
