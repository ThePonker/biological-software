"""
Export Service.

Handles export of data to various formats (CSV, etc.).
"""

from typing import List, Dict
from pathlib import Path
import csv


class ExportService:
    """
    Service for data export.
    
    Features:
    - CSV export
    - Column configuration
    - Date formatting
    """
    
    @staticmethod
    def export_to_csv(
        data: List[Dict],
        filepath: str,
        columns: List[str] = None,
        headers: Dict[str, str] = None
    ) -> bool:
        """
        Export data to CSV file.
        
        Args:
            data: List of record dicts
            filepath: Output file path
            columns: Column keys to include (None = all)
            headers: Column key to header name mapping
            
        Returns:
            True if successful
        """
        if not data:
            return False
        
        try:
            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Determine columns
            if columns is None:
                columns = list(data[0].keys())
            
            # Determine headers
            if headers is None:
                headers = {col: col for col in columns}
            
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write header row
                header_row = [headers.get(col, col) for col in columns]
                writer.writerow(header_row)
                
                # Write data rows
                for record in data:
                    row = [record.get(col, '') for col in columns]
                    writer.writerow(row)
            
            return True
            
        except Exception as e:
            print(f"Export error: {e}")
            return False
    
    @staticmethod
    def get_observation_columns() -> tuple:
        """Get default columns for observation export."""
        columns = [
            'species_name', 'common_name', 'date', 'location', 'grid_ref',
            'vice_county', 'recorder', 'determiner', 'sex', 'stage',
            'quantity', 'method', 'type', 'comment', 'verification_status'
        ]
        headers = {
            'species_name': 'Species',
            'common_name': 'Common Name',
            'date': 'Date',
            'location': 'Location',
            'grid_ref': 'Grid Ref',
            'vice_county': 'Vice County',
            'recorder': 'Recorder',
            'determiner': 'Determiner',
            'sex': 'Sex',
            'stage': 'Stage',
            'quantity': 'Quantity',
            'method': 'Sample Method',
            'type': 'Observation Type',
            'comment': 'Comment',
            'verification_status': 'Verification'
        }
        return columns, headers
    
    @staticmethod
    def get_specimen_columns() -> tuple:
        """Get default columns for specimen export."""
        columns = [
            'specimen_code', 'species_name', 'common_name', 'date_collected',
            'location', 'grid_ref', 'vice_county', 'collector', 'determiner',
            'sex', 'preparation_type', 'storage_location', 'notes'
        ]
        headers = {
            'specimen_code': 'Specimen Code',
            'species_name': 'Species',
            'common_name': 'Common Name',
            'date_collected': 'Date Collected',
            'location': 'Location',
            'grid_ref': 'Grid Ref',
            'vice_county': 'Vice County',
            'collector': 'Collector',
            'determiner': 'Determiner',
            'sex': 'Sex',
            'preparation_type': 'Preparation',
            'storage_location': 'Storage Location',
            'notes': 'Notes'
        }
        return columns, headers

    @staticmethod
    def get_irecord_columns() -> tuple:
        """Get columns for iRecord-compatible CSV export.
        
        Maps observatum_key to 'External key' for iRecord sync.
        Uses iRecord's expected column headers.
        """
        columns = [
            'observatum_key', 'species_name', 'common_name', 'date', 
            'grid_ref', 'site_name', 'vice_county',
            'recorder', 'determiner', 'sex', 'stage', 'quantity',
            'method', 'comment',
            'record_type', 'project_name'
        ]
        headers = {
            'observatum_key': 'External key',
            'species_name': 'Species',
            'common_name': 'Common name',
            'date': 'Date',
            'grid_ref': 'Spatial reference',
            'site_name': 'Location name',
            'vice_county': 'Vice county',
            'recorder': 'Recorder',
            'determiner': 'Determiner',
            'sex': 'Sex',
            'stage': 'Stage',
            'quantity': 'Quantity',
            'method': 'Sample method',
            'comment': 'Comment',
            'record_type': 'Observatum type',
            'project_name': 'Project'
        }
        return columns, headers
