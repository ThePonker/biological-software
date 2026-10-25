"""
Input Validators.

Validation functions for user input.
"""

import re
from typing import List


class Validators:
    """Collection of input validators."""
    
    @staticmethod
    def validate_grid_ref(grid_ref: str) -> bool:
        """Validate an OS Grid Reference."""
        if not grid_ref:
            return False
        
        # Remove spaces and uppercase
        gr = grid_ref.replace(' ', '').upper()
        
        # Pattern: 2 letters + even number of digits (2-10)
        pattern = r'^[A-Z]{2}\d{2,10}$'
        if not re.match(pattern, gr):
            return False
        
        # Check even number of digits
        digits = len(gr) - 2
        return digits % 2 == 0
    
    @staticmethod
    def validate_date(date_str: str) -> bool:
        """Validate a date string."""
        from .date_utils import parse_display_date
        return parse_display_date(date_str) is not None
    
    @staticmethod
    def validate_required(value: str) -> bool:
        """Validate that a value is not empty."""
        return bool(value and value.strip())
    
    @staticmethod
    def validate_numeric(value: str, min_val: float = None, max_val: float = None) -> bool:
        """Validate a numeric value."""
        try:
            num = float(value)
            if min_val is not None and num < min_val:
                return False
            if max_val is not None and num > max_val:
                return False
            return True
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_integer(value: str, min_val: int = None, max_val: int = None) -> bool:
        """Validate an integer value."""
        try:
            num = int(value)
            if min_val is not None and num < min_val:
                return False
            if max_val is not None and num > max_val:
                return False
            return True
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_in_list(value: str, valid_options: List[str], case_sensitive: bool = False) -> bool:
        """Validate that a value is in a list of options."""
        if not case_sensitive:
            value = value.lower()
            valid_options = [opt.lower() for opt in valid_options]
        return value in valid_options
    
    @staticmethod
    def validate_specimen_code(code: str) -> bool:
        """Validate a specimen code format."""
        if not code:
            return False
        # Allow alphanumeric with hyphens and underscores
        pattern = r'^[A-Za-z0-9_-]+$'
        return bool(re.match(pattern, code))
    
    @staticmethod
    def validate_tvk(tvk: str) -> bool:
        """Validate a TaxonVersionKey format."""
        if not tvk:
            return False
        # TVK is 16 characters, alphanumeric
        pattern = r'^[A-Z]{6}\d{10}$'
        return bool(re.match(pattern, tvk))
    
    @classmethod
    def validate_observation_record(cls, record: dict) -> List[str]:
        """
        Validate an observation record.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        if not cls.validate_required(record.get('species_name', '')):
            errors.append("Species name is required")
        
        if not cls.validate_required(record.get('date', '')):
            errors.append("Date is required")
        elif not cls.validate_date(record.get('date', '')):
            errors.append("Invalid date format")
        
        grid_ref = record.get('grid_ref', '')
        if grid_ref and not cls.validate_grid_ref(grid_ref):
            errors.append("Invalid grid reference format")
        
        quantity = record.get('quantity', '1')
        if quantity and not cls.validate_integer(str(quantity), min_val=1):
            errors.append("Quantity must be a positive integer")
        
        return errors
