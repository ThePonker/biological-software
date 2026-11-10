# Observation Import Wizard - Refactored Package

## Summary

Complete refactored Observation Import Wizard with NBN/Darwin Core schema support.
Works with the updated 67-column observations table.

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Package exports |
| `import_row.py` | ObservationImportRow dataclass + field mappings |
| `wizard_file_handling.py` | File loading, iRecord detection, column mapping |
| `wizard_validation.py` | Row validation, UKSI lookups, status bars |
| `wizard_pages.py` | All page creation methods |
| `observation_import_wizard.py` | Main wizard class with navigation |

## Key Improvements

### 1. Schema Compatibility
- Fully aligned with 67-column observations table
- All NBN/Darwin Core fields supported
- Works with updated Observation dataclass

### 2. Grouped Column Mapping
- Fields organized into logical groups:
  - Core Fields (species, TVK, date)
  - Location - Grid (grid ref, site, VC)
  - Location - Coordinates (lat, long)
  - People (recorder, determiner, verifier)
  - Occurrence (sex, stage, quantity, method)
  - Notes (comment, biotope, etc.)
  - Identification (taxon rank, qualifier)
  - Verification (status, verifier)
  - Record Identity (iRecord ID, keys, source)
  - Metadata (licence, images, dates)

### 3. iRecord Auto-Detection
- Detects iRecord CSV format automatically
- Can skip mapping page when all columns auto-match
- Uses correct column mappings (Output map ref, not Original map ref)

### 4. Validation Status Bars
- Like Specimen Import Wizard:
  - Valid count (green)
  - Warning count (yellow)
  - Error count (red)
- Progress bar during validation

### 5. CSV Value Priority
- Logic: IF csv_value exists THEN use it, ELSE auto-populate
- Auto-populated fields only filled when CSV is empty:
  - common_name (from TVK lookup)
  - order_name (from TVK lookup)
  - family (from TVK lookup)
  - vc_name (from grid ref/VC number)
  - grid_precision (from grid ref)
  - geodetic_datum (set to WGS84 when coordinates present)

### 6. Bug Fixes
- Qt.CheckState enum comparison (not integer 2)
- UKSI Species object vs dict handling
- Correct INSERT column count (65 values for 67 columns)

## Installation

1. Copy folder to: `src/views/dialogs/observation_import_wizard/`

2. Update imports in calling code:
   ```python
   from src.views.dialogs.observation_import_wizard import ObservationImportWizard
   ```

3. Ensure dependencies:
   - Updated `src/models/observation.py` (with 67-column support)
   - Database migrated with `scripts/migrate_nbn_schema.py`

## Usage

```python
from src.views.dialogs.observation_import_wizard import ObservationImportWizard

# Create wizard
wizard = ObservationImportWizard(
    parent=self,
    uksi_model=uksi,
    vc_service=vc_lookup,
    db=db_manager,
    observation_model=obs_model
)

# Run wizard
if wizard.exec() == QDialog.Accepted:
    print(f"Imported {wizard.imported_count} records")
    print(f"Updated {wizard.updated_count} records")
```

## Testing

Test with iRecord CSV export:
```powershell
python -c "
import sys
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)

from src.models.database import DatabaseManager
db = DatabaseManager()
db.set_paths('data/observatum.db', 'data/uksi.db')

from src.models.uksi import UKSIModel
from src.models.observation import ObservationModel
from src.services.vc_lookup_service import VCLookupService

uksi = UKSIModel(db)
vc = VCLookupService('data/vc_lookup.db')
obs = ObservationModel(db)

from src.views.dialogs.observation_import_wizard import ObservationImportWizard
wizard = ObservationImportWizard(None, uksi, vc, db, obs)
wizard.exec()
"
```
