"""
Field Entry App - Standalone field data entry tool.

A lightweight Excel-like interface for entering biological records
with UKSI species autocomplete and Vice County auto-lookup.

Features:
- Species autocomplete from UKSI database (including synonyms)
- Genus and family-level search support
- Auto-population of taxonomy (TVK, Common Name, Family, Order)
- Grid reference validation with visual feedback
- Vice county auto-lookup from grid reference
- Quick Fill bar for bulk applying values
- Persistent settings for Recorder/Determiner defaults
- 1000 rows on startup for rapid data entry
- Excel-like editing (copy, paste, undo, redo)
- Find & Replace (Ctrl+H)
- Column visibility management
- Auto-save with crash recovery
- CSV import/export in iRecord format

Usage:
    python -m scripts.field_entry
    
    Or run field_entry.bat from the project root.
"""

__version__ = '3.0.0'

def main():
    """Entry point for the application."""
    from .main import main as _main
    return _main()
