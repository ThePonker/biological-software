"""
Grid Reference Service.

Utilities for working with OS Grid References.
Handles validation, conversion, and precision detection.
"""

from typing import Optional, Tuple
import re


class GridRefService:
    """
    Service for OS Grid Reference operations.
    
    Features:
    - Validation
    - Precision detection
    - Coordinate conversion (future)
    """
    
    # Valid grid letters (100km squares)
    GRID_LETTERS = {
        'H', 'N', 'S', 'T',  # First letter
    }
    
    # Full list of valid letter pairs for GB
    VALID_SQUARES = {
        'HP', 'HT', 'HU', 'HW', 'HX', 'HY', 'HZ',
        'NA', 'NB', 'NC', 'ND', 'NF', 'NG', 'NH', 'NJ', 'NK', 'NL', 'NM', 'NN', 'NO',
        'NR', 'NS', 'NT', 'NU', 'NW', 'NX', 'NY', 'NZ',
        'OV',
        'SC', 'SD', 'SE', 'SH', 'SJ', 'SK', 'SM', 'SN', 'SO', 'SP', 'SR', 'SS', 'ST',
        'SU', 'SV', 'SW', 'SX', 'SY', 'SZ',
        'TA', 'TF', 'TG', 'TL', 'TM', 'TQ', 'TR', 'TV',
    }
    
    @classmethod
    def validate(cls, grid_ref: str) -> bool:
        """
        Validate a grid reference.
        
        Args:
            grid_ref: Grid reference string
            
        Returns:
            True if valid
        """
        if not grid_ref:
            return False
        
        # Remove spaces and uppercase
        gr = grid_ref.replace(' ', '').upper()
        
        # Check format: 2 letters + even number of digits
        pattern = r'^[A-Z]{2}\d{2,10}$'
        if not re.match(pattern, gr):
            return False
        
        # Check letters are valid
        letters = gr[:2]
        if letters not in cls.VALID_SQUARES:
            return False
        
        # Check even number of digits
        digits = gr[2:]
        if len(digits) % 2 != 0:
            return False
        
        return True
    
    @classmethod
    def get_precision(cls, grid_ref: str) -> Optional[int]:
        """
        Get the precision of a grid reference in metres.
        
        Args:
            grid_ref: Grid reference string
            
        Returns:
            Precision in metres, or None if invalid
        """
        if not cls.validate(grid_ref):
            return None
        
        gr = grid_ref.replace(' ', '').upper()
        digit_count = len(gr) - 2
        
        # Precision based on digit count
        precision_map = {
            2: 10000,   # 10km (e.g., SP51)
            4: 1000,    # 1km (e.g., SP5812)
            6: 100,     # 100m (e.g., SP581123)
            8: 10,      # 10m (e.g., SP58121234)
            10: 1,      # 1m (e.g., SP5812312345)
        }
        
        return precision_map.get(digit_count)
    
    @classmethod
    def format_grid_ref(cls, grid_ref: str, target_precision: int = 6) -> Optional[str]:
        """
        Format a grid reference to a target precision.
        
        Args:
            grid_ref: Grid reference string
            target_precision: Number of digits (2, 4, 6, 8, 10)
            
        Returns:
            Formatted grid reference, or None if invalid
        """
        if not cls.validate(grid_ref):
            return None
        
        gr = grid_ref.replace(' ', '').upper()
        letters = gr[:2]
        digits = gr[2:]
        
        current_len = len(digits)
        target_len = target_precision
        
        if target_len > current_len:
            # Cannot increase precision
            return None
        
        # Truncate to target precision
        half = target_len // 2
        easting = digits[:current_len // 2][:half]
        northing = digits[current_len // 2:][:half]
        
        return f"{letters}{easting}{northing}"
    
    @classmethod
    def to_coordinates(cls, grid_ref: str) -> Optional[Tuple[int, int]]:
        """
        Convert grid reference to easting/northing coordinates.
        
        Args:
            grid_ref: Grid reference string
            
        Returns:
            Tuple of (easting, northing) in metres, or None if invalid
        """
        # TODO: Implement full conversion
        # This requires the grid letter offsets
        return None
