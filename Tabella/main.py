#!/usr/bin/env python3
"""
Field Entry App - Main Entry Point.

Lightweight standalone application for field data entry with
UKSI species autocomplete and VC auto-lookup.

Run: python scripts/field_entry/main.py
  or: python -m scripts.field_entry.main
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt

from .uksi_lookup import UKSILookup
from .vc_lookup import VCLookup
from .settings import Settings
from .window import FieldEntryWindow


def find_data_directory() -> Path:
    """
    Find the data directory containing databases.
    
    Searches multiple locations to support different run contexts.
    """
    # Try various relative paths
    candidates = [
        Path('data'),
        Path('../data'),
        Path('../../data'),
        Path.cwd() / 'data',
    ]
    
    # Also try paths relative to this script
    script_dir = Path(__file__).parent
    candidates.extend([
        script_dir / '../../data',
        script_dir / '../../../data',
    ])
    
    for path in candidates:
        resolved = path.resolve()
        if resolved.exists() and (resolved / 'uksi.db').exists():
            return resolved
    
    return None


def main():
    """Main entry point."""
    # Create application
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setApplicationName('Observatum Field Entry')
    app.setOrganizationName('Observatum')
    
    # Find data directory
    data_dir = find_data_directory()
    
    if not data_dir:
        QMessageBox.critical(
            None,
            "Database Not Found",
            "Could not find the data directory.\n\n"
            "Please ensure the data folder exists with uksi.db and vc_lookup.db.\n\n"
            "Expected locations:\n"
            "• data/uksi.db\n"
            "• data/vc_lookup.db"
        )
        return 1
    
    # Load settings
    settings = Settings(data_dir / 'field_entry_settings.json')
    
    # Initialize UKSI lookup
    uksi_path = data_dir / 'uksi.db'
    uksi = UKSILookup(uksi_path)
    
    if not uksi.connect():
        QMessageBox.critical(
            None,
            "Database Error",
            f"Could not connect to UKSI database.\n\n"
            f"Path: {uksi_path}\n\n"
            "Species autocomplete will not work."
        )
        return 1
    
    # Initialize VC lookup
    vc_path = data_dir / 'vc_lookup.db'
    vc_lookup = VCLookup(vc_path)
    
    if not vc_lookup.connect():
        # VC lookup is optional - just warn
        QMessageBox.warning(
            None,
            "VC Lookup Unavailable",
            f"Could not connect to VC lookup database.\n\n"
            f"Path: {vc_path}\n\n"
            "Vice County auto-lookup will not work.\n"
            "You can still enter data manually."
        )
    
    # Create and show main window
    window = FieldEntryWindow(uksi, vc_lookup, settings, data_dir)
    window.show()
    
    # Run application
    result = app.exec()
    
    # Cleanup
    uksi.close()
    vc_lookup.close()
    
    return result


if __name__ == '__main__':
    sys.exit(main())
