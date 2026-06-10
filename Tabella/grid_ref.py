"""
Field Entry App - Grid Reference Validation.

Validates British/Irish grid references and extracts 1km squares.
"""

import re
from typing import Tuple, Optional


# OS Grid letter squares (100km)
OS_GRID_LETTERS = {
    'H': (0, 10), 'J': (1, 10),
    'N': (0, 9), 'O': (1, 9),
    'S': (0, 8), 'T': (1, 8),
    'W': (0, 7), 'X': (1, 7), 'Y': (2, 7), 'Z': (3, 7),
    'A': (0, 6), 'B': (1, 6), 'C': (2, 6), 'D': (3, 6),
    'F': (0, 5), 'G': (1, 5), 'H': (2, 5), 'J': (3, 5),
    'L': (0, 4), 'M': (1, 4), 'N': (2, 4), 'O': (3, 4),
    'Q': (0, 3), 'R': (1, 3), 'S': (2, 3), 'T': (3, 3),
    'V': (0, 2), 'W': (1, 2), 'X': (2, 2), 'Y': (3, 2), 'Z': (4, 2),
}

# British National Grid 100km squares
BNG_SQUARES = {
    'SV', 'SW', 'SX', 'SY', 'SZ', 'TV',
    'SR', 'SS', 'ST', 'SU', 'TQ', 'TR',
    'SM', 'SN', 'SO', 'SP', 'TL', 'TM',
    'SH', 'SJ', 'SK', 'TF', 'TG',
    'SC', 'SD', 'SE', 'TA',
    'NW', 'NX', 'NY', 'NZ', 'OV',
    'NR', 'NS', 'NT', 'NU',
    'NL', 'NM', 'NN', 'NO',
    'NF', 'NG', 'NH', 'NJ', 'NK',
    'NA', 'NB', 'NC', 'ND',
    'HW', 'HX', 'HY', 'HZ',
    'HP', 'HT', 'HU',
}

# Irish Grid 100km squares
IRISH_SQUARES = {
    'A', 'B', 'C', 'D', 'F', 'G', 'H', 'J', 'L', 'M',
    'N', 'O', 'Q', 'R', 'S', 'T', 'V', 'W', 'X', 'Y',
}


class GridRefValidator:
    """Validates British and Irish grid references."""
    
    # Regex patterns for different formats
    PATTERNS = [
        # British: 2 letters + even digits (e.g., TF1234, TF123456)
        re.compile(r'^([A-HJ-Z]{2})(\d{4}|\d{6}|\d{8}|\d{10})$', re.IGNORECASE),
        # Irish: 1 letter + even digits (e.g., H1234)
        re.compile(r'^([A-HJ-Z])(\d{4}|\d{6}|\d{8}|\d{10})$', re.IGNORECASE),
        # DINTY tetrad format: 2 letters + 2 digits + letter (e.g., TF12A)
        re.compile(r'^([A-HJ-Z]{2})(\d{2})([A-NP-Z])$', re.IGNORECASE),
    ]
    
    @classmethod
    def validate(cls, grid_ref: str) -> Tuple[bool, str]:
        """
        Validate a grid reference.
        
        Args:
            grid_ref: Grid reference string
            
        Returns:
            Tuple of (is_valid, message)
        """
        if not grid_ref:
            return False, "Grid reference is required"
        
        grid_ref = grid_ref.strip().upper()
        
        # Check British format
        match = cls.PATTERNS[0].match(grid_ref)
        if match:
            letters = match.group(1)
            if letters not in BNG_SQUARES:
                return False, f"Invalid 100km square: {letters}"
            return True, "Valid British grid reference"
        
        # Check Irish format
        match = cls.PATTERNS[1].match(grid_ref)
        if match:
            letter = match.group(1)
            if letter not in IRISH_SQUARES:
                return False, f"Invalid Irish grid letter: {letter}"
            return True, "Valid Irish grid reference"
        
        # Check DINTY tetrad format
        match = cls.PATTERNS[2].match(grid_ref)
        if match:
            letters = match.group(1)
            if letters not in BNG_SQUARES:
                return False, f"Invalid 100km square: {letters}"
            return True, "Valid tetrad reference"
        
        return False, "Invalid grid reference format"
    
    @classmethod
    def extract_1km_square(cls, grid_ref: str) -> Optional[str]:
        """
        Extract the 1km grid square from a grid reference.
        
        Args:
            grid_ref: Valid grid reference
            
        Returns:
            1km square string (e.g., "TF1219") or None if invalid
        """
        if not grid_ref:
            return None
            
        grid_ref = grid_ref.strip().upper()
        
        # British format
        match = cls.PATTERNS[0].match(grid_ref)
        if match:
            letters = match.group(1)
            digits = match.group(2)
            
            # Get precision
            digit_pairs = len(digits) // 2
            
            if digit_pairs >= 2:
                # Extract 1km square (first 2 digits of each coordinate)
                easting = digits[:digit_pairs][:2]
                northing = digits[digit_pairs:][:2]
                return f"{letters}{easting}{northing}"
            else:
                # 10km square - return as-is
                return f"{letters}{digits}"
        
        # Irish format
        match = cls.PATTERNS[1].match(grid_ref)
        if match:
            letter = match.group(1)
            digits = match.group(2)
            
            digit_pairs = len(digits) // 2
            
            if digit_pairs >= 2:
                easting = digits[:digit_pairs][:2]
                northing = digits[digit_pairs:][:2]
                return f"{letter}{easting}{northing}"
            else:
                return f"{letter}{digits}"
        
        # DINTY tetrad format - convert to 1km
        match = cls.PATTERNS[2].match(grid_ref)
        if match:
            letters = match.group(1)
            digits = match.group(2)
            tetrad = match.group(3)
            
            # Tetrad letters map to position within 10km square
            # A-E = row 0, F-K = row 1, L-P = row 2, Q-U = row 3, V-Z = row 4
            tetrad_map = {
                'A': (0, 0), 'B': (2, 0), 'C': (4, 0), 'D': (6, 0), 'E': (8, 0),
                'F': (0, 2), 'G': (2, 2), 'H': (4, 2), 'I': (6, 2), 'J': (8, 2),
                'K': (0, 4), 'L': (2, 4), 'M': (4, 4), 'N': (6, 4), 'P': (8, 4),
                'Q': (0, 6), 'R': (2, 6), 'S': (4, 6), 'T': (6, 6), 'U': (8, 6),
                'V': (0, 8), 'W': (2, 8), 'X': (4, 8), 'Y': (6, 8), 'Z': (8, 8),
            }
            
            if tetrad in tetrad_map:
                e_offset, n_offset = tetrad_map[tetrad]
                base_e = int(digits[0]) * 10
                base_n = int(digits[1]) * 10
                # Use centre of tetrad for 1km reference
                e = (base_e + e_offset + 1) // 10
                n = (base_n + n_offset + 1) // 10
                return f"{letters}{digits[0]}{e % 10}{digits[1]}{n % 10}"
        
        return None
    
    @classmethod
    def get_precision(cls, grid_ref: str) -> Optional[int]:
        """
        Get the precision (in metres) of a grid reference.
        
        Returns:
            Precision in metres, or None if invalid
        """
        if not grid_ref:
            return None
            
        grid_ref = grid_ref.strip().upper()
        
        # British format
        match = cls.PATTERNS[0].match(grid_ref)
        if match:
            digits = match.group(2)
            digit_pairs = len(digits) // 2
            precisions = {1: 10000, 2: 1000, 3: 100, 4: 10, 5: 1}
            return precisions.get(digit_pairs)
        
        # Irish format
        match = cls.PATTERNS[1].match(grid_ref)
        if match:
            digits = match.group(2)
            digit_pairs = len(digits) // 2
            precisions = {1: 10000, 2: 1000, 3: 100, 4: 10, 5: 1}
            return precisions.get(digit_pairs)
        
        # DINTY tetrad
        match = cls.PATTERNS[2].match(grid_ref)
        if match:
            return 2000  # Tetrad = 2km
        
        return None
