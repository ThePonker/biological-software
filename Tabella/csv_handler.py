"""
Field Entry App - CSV Import/Export Handler.

Handles importing and exporting CSV files, with iRecord format auto-detection.
"""

import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any

from .constants import (
    COLUMNS, IRECORD_COLUMN_MAP, CSV_EXPORT_HEADERS,
    COL_SPECIES, COL_TVK, COL_COMMON_NAME, COL_FAMILY, COL_ORDER,
    COL_DATE, COL_GRID_REF, COL_VICE_COUNTY, COL_LOCATION,
    COL_QTY, COL_SEX, COL_STAGE, COL_METHOD,
    COL_CERTAINTY, COL_RECORDER, COL_DETERMINER, COL_COMMENT,
    COL_DATA_TYPE, COL_NEVER_UPLOAD
)


class CSVHandler:
    """Handles CSV import and export operations."""
    
    @staticmethod
    def detect_columns(file_path: str) -> Tuple[List[str], Dict[str, int]]:
        """
        Read CSV headers and detect column mapping.
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            Tuple of (headers, mapping) where mapping maps header to column index
        """
        headers = []
        mapping = {}
        
        try:
            with open(file_path, 'r', newline='', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                headers = next(reader, [])
                
                # Try to auto-map columns
                for i, header in enumerate(headers):
                    header_clean = header.strip()
                    
                    # Check exact match first
                    if header_clean in IRECORD_COLUMN_MAP:
                        mapping[header_clean] = IRECORD_COLUMN_MAP[header_clean]
                    else:
                        # Try case-insensitive match
                        header_lower = header_clean.lower()
                        for known_header, col_idx in IRECORD_COLUMN_MAP.items():
                            if known_header.lower() == header_lower:
                                mapping[header_clean] = col_idx
                                break
        
        except Exception as e:
            print(f"[CSVHandler] Error reading headers: {e}")
        
        return headers, mapping
    
    @staticmethod
    def preview_file(file_path: str, max_rows: int = 5) -> Tuple[List[str], List[List[str]], int]:
        """
        Preview a CSV file.
        
        Args:
            file_path: Path to CSV file
            max_rows: Maximum preview rows
            
        Returns:
            Tuple of (headers, preview_rows, total_row_count)
        """
        headers = []
        preview_rows = []
        total_rows = 0
        
        try:
            with open(file_path, 'r', newline='', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                headers = next(reader, [])
                
                for i, row in enumerate(reader):
                    total_rows += 1
                    if i < max_rows:
                        preview_rows.append(row)
        
        except Exception as e:
            print(f"[CSVHandler] Error previewing file: {e}")
        
        return headers, preview_rows, total_rows
    
    @staticmethod
    def import_file(
        file_path: str,
        column_mapping: Dict[str, int],
        skip_header: bool = True
    ) -> List[List[str]]:
        """
        Import CSV file to table data.
        
        Args:
            file_path: Path to CSV file
            column_mapping: Maps CSV column name to table column index
            skip_header: Whether to skip the first row
            
        Returns:
            List of rows, each row is a list of cell values
        """
        rows = []
        
        try:
            with open(file_path, 'r', newline='', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                headers = next(reader, []) if skip_header else None
                
                # Create reverse mapping: csv column index -> table column index
                csv_to_table = {}
                if headers:
                    for csv_idx, header in enumerate(headers):
                        header_clean = header.strip()
                        if header_clean in column_mapping:
                            csv_to_table[csv_idx] = column_mapping[header_clean]
                
                for csv_row in reader:
                    # Create empty row with all columns
                    table_row = [''] * len(COLUMNS)
                    
                    for csv_idx, value in enumerate(csv_row):
                        if csv_idx in csv_to_table:
                            table_col = csv_to_table[csv_idx]
                            table_row[table_col] = value.strip()
                    
                    # Only add rows that have at least species data
                    if table_row[COL_SPECIES].strip():
                        rows.append(table_row)
        
        except Exception as e:
            print(f"[CSVHandler] Error importing file: {e}")
        
        return rows
    
    @staticmethod
    def export_file(
        file_path: str,
        rows: List[List[str]],
        include_empty: bool = False
    ) -> int:
        """
        Export table data to CSV in iRecord format.
        
        Args:
            file_path: Path to save CSV
            rows: List of rows from table
            include_empty: Whether to include rows without species
            
        Returns:
            Number of rows exported
        """
        exported = 0
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write headers
                writer.writerow(CSV_EXPORT_HEADERS)
                
                # Write data rows
                for row in rows:
                    # Skip empty rows unless requested
                    if not include_empty and not row[COL_SPECIES].strip():
                        continue
                    
                    # Map to export format
                    export_row = [
                        row[COL_SPECIES],           # Taxon
                        row[COL_TVK],               # TaxonVersionKey
                        row[COL_COMMON_NAME],       # Common name
                        row[COL_FAMILY],            # Family
                        row[COL_ORDER],             # Order
                        row[COL_DATE],              # Date
                        row[COL_GRID_REF],          # Grid ref
                        row[COL_VICE_COUNTY],       # Vice County
                        row[COL_LOCATION],          # Site name
                        row[COL_QTY],               # Quantity
                        row[COL_SEX],               # Sex
                        row[COL_STAGE],             # Stage
                        row[COL_METHOD],            # Sample method
                        row[COL_CERTAINTY],         # Recorder certainty
                        row[COL_RECORDER],          # Recorder
                        row[COL_DETERMINER],        # Determiner
                        row[COL_COMMENT],           # Comment
                        row[COL_DATA_TYPE],         # Data type
                        row[COL_NEVER_UPLOAD],      # Exclude from iRecord
                    ]
                    
                    writer.writerow(export_row)
                    exported += 1
        
        except Exception as e:
            print(f"[CSVHandler] Error exporting file: {e}")
            return 0
        
        return exported
    
    @staticmethod
    def generate_filename(prefix: str = "field_records") -> str:
        """Generate a timestamped filename."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"{prefix}_{timestamp}.csv"


class ColumnMappingDialog:
    """
    Helper class for column mapping data.
    
    This provides the data structures for the UI to display mapping options.
    """
    
    @staticmethod
    def get_target_columns() -> List[Tuple[int, str]]:
        """
        Get list of target columns for mapping.
        
        Returns:
            List of (column_index, column_name) tuples
        """
        return [
            (i, col[0]) for i, col in enumerate(COLUMNS)
        ]
    
    @staticmethod
    def suggest_mapping(csv_header: str) -> Optional[int]:
        """
        Suggest a column mapping for a CSV header.
        
        Args:
            csv_header: CSV column header
            
        Returns:
            Suggested table column index, or None
        """
        header_clean = csv_header.strip()
        
        # Try exact match
        if header_clean in IRECORD_COLUMN_MAP:
            return IRECORD_COLUMN_MAP[header_clean]
        
        # Try case-insensitive
        header_lower = header_clean.lower()
        for known, idx in IRECORD_COLUMN_MAP.items():
            if known.lower() == header_lower:
                return idx
        
        return None
