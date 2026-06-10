"""
Grid Reference Converter Service

Converts between OS Grid References and Lat/Long coordinates.
Wraps OSGridConverter library for Observatum.

Usage:
    from src.services.grid_converter_service import GridConverterService
    
    converter = GridConverterService()
    
    # Grid ref to lat/long
    lat, lon = converter.grid_to_latlon("TQ336805")
    
    # Lat/long to grid ref
    grid_ref = converter.latlon_to_grid(51.5074, -0.1278, precision=6)

Prerequisites:
    pip install OSGridConverter
"""

from typing import Optional, Tuple
import re

try:
    from OSGridConverter import grid2latlong, latlong2grid
    HAS_OSGRID = True
except ImportError:
    HAS_OSGRID = False
    print("[GridConverterService] WARNING: OSGridConverter not installed. Run: pip install OSGridConverter")


class GridConverterService:
    """Service for converting between grid references and lat/long."""
    
    # Valid grid ref pattern (2 letters + even number of digits)
    GRID_REF_PATTERN = re.compile(r'^([A-HJ-Z]{2})(\d{4}|\d{6}|\d{8}|\d{10})$', re.IGNORECASE)
    
    # Irish grid letters
    IRISH_LETTERS = {'A', 'B', 'C', 'D', 'F', 'G', 'H', 'J', 'L', 'M', 'N', 'O', 'Q', 'R', 'S', 'T', 'V', 'W', 'X', 'Y'}
    
    def __init__(self):
        self.available = HAS_OSGRID
    
    def is_available(self) -> bool:
        """Check if the converter is available."""
        return self.available
    
    def normalize_grid_ref(self, grid_ref: str) -> Optional[str]:
        """Normalize a grid reference (uppercase, no spaces)."""
        if not grid_ref:
            return None
        
        # Remove spaces and uppercase
        normalized = grid_ref.replace(" ", "").upper()
        
        # Validate format
        if self.GRID_REF_PATTERN.match(normalized):
            return normalized
        
        return None
    
    def get_precision(self, grid_ref: str) -> Optional[int]:
        """
        Get precision in meters from grid reference.
        
        Returns:
            100000 for 2-digit (10km)
            10000 for 4-digit (1km)
            1000 for 6-digit (100m)
            100 for 8-digit (10m)
            10 for 10-digit (1m)
        """
        normalized = self.normalize_grid_ref(grid_ref)
        if not normalized:
            return None
        
        match = self.GRID_REF_PATTERN.match(normalized)
        if match:
            digits = len(match.group(2))
            precision_map = {
                2: 10000,   # 10km (tetrad-ish)
                4: 1000,    # 1km
                6: 100,     # 100m
                8: 10,      # 10m
                10: 1       # 1m
            }
            return precision_map.get(digits)
        
        return None
    
    def grid_to_latlon(self, grid_ref: str) -> Tuple[Optional[float], Optional[float]]:
        """
        Convert OS Grid Reference to latitude/longitude (WGS84).
        
        Args:
            grid_ref: OS grid reference (e.g., "TQ336805", "SP 123 456")
        
        Returns:
            Tuple of (latitude, longitude) or (None, None) if conversion fails
        """
        if not self.available:
            return None, None
        
        normalized = self.normalize_grid_ref(grid_ref)
        if not normalized:
            return None, None
        
        try:
            result = grid2latlong(normalized)
            return round(result.latitude, 6), round(result.longitude, 6)
        except Exception as e:
            print(f"[GridConverterService] Error converting {grid_ref}: {e}")
            return None, None
    
    def latlon_to_grid(self, latitude: float, longitude: float, precision: int = 6) -> Optional[str]:
        """
        Convert latitude/longitude to OS Grid Reference.
        
        Args:
            latitude: Decimal latitude (WGS84)
            longitude: Decimal longitude (WGS84)
            precision: Number of digits (4, 6, 8, or 10). Default 6 (100m).
        
        Returns:
            Grid reference string or None if conversion fails
        """
        if not self.available:
            return None
        
        # Validate coordinates are roughly in UK/Ireland
        if not (49.0 <= latitude <= 61.0 and -11.0 <= longitude <= 2.0):
            return None
        
        try:
            result = latlong2grid(latitude, longitude)
            grid_str = str(result)
            
            # OSGridConverter returns with spaces, remove them
            grid_str = grid_str.replace(' ', '')
            
            # Format is "XX12345678" - 2 letters + digits
            letters = grid_str[:2]
            digits = grid_str[2:]
            
            # Truncate to requested precision (total digits, split evenly)
            half = precision // 2
            if len(digits) >= precision:
                easting = digits[:half]
                northing = digits[half:precision]
            else:
                # Pad if needed
                easting = digits[:len(digits)//2].ljust(half, '0')
                northing = digits[len(digits)//2:].ljust(half, '0')
            
            return f"{letters}{easting}{northing}"
            
        except Exception as e:
            print(f"[GridConverterService] Error converting ({latitude}, {longitude}): {e}")
            return None
    
    def is_irish_grid(self, grid_ref: str) -> bool:
        """Check if grid reference is Irish National Grid."""
        normalized = self.normalize_grid_ref(grid_ref)
        if normalized and len(normalized) >= 1:
            # Irish grid uses single letter prefix
            return normalized[0] in self.IRISH_LETTERS and normalized[1].isdigit()
        return False
    
    def convert_for_import(self, grid_ref: Optional[str], 
                           latitude: Optional[float], 
                           longitude: Optional[float]) -> dict:
        """
        Prepare location data for import, converting as needed.
        
        Args:
            grid_ref: Grid reference from source data
            latitude: Latitude from source data
            longitude: Longitude from source data
        
        Returns:
            Dict with grid_ref, latitude, longitude, grid_precision, geodetic_datum
        """
        result = {
            'grid_ref': None,
            'grid_precision': None,
            'latitude': None,
            'longitude': None,
            'geodetic_datum': None
        }
        
        # Normalize and validate grid ref if provided
        if grid_ref:
            normalized = self.normalize_grid_ref(grid_ref)
            if normalized:
                result['grid_ref'] = normalized
                result['grid_precision'] = self.get_precision(normalized)
                
                # Convert to lat/long if not provided
                if latitude is None or longitude is None:
                    lat, lon = self.grid_to_latlon(normalized)
                    if lat is not None and lon is not None:
                        result['latitude'] = lat
                        result['longitude'] = lon
                        result['geodetic_datum'] = 'WGS84'
        
        # Use provided lat/long if available
        if latitude is not None and longitude is not None:
            result['latitude'] = latitude
            result['longitude'] = longitude
            result['geodetic_datum'] = 'WGS84'
            
            # Convert to grid ref if not provided
            if not result['grid_ref']:
                grid = self.latlon_to_grid(latitude, longitude, precision=6)
                if grid:
                    result['grid_ref'] = grid
                    result['grid_precision'] = self.get_precision(grid)
        
        return result


# Singleton instance
_instance: Optional[GridConverterService] = None


def get_grid_converter() -> GridConverterService:
    """Get the singleton GridConverterService instance."""
    global _instance
    if _instance is None:
        _instance = GridConverterService()
    return _instance
