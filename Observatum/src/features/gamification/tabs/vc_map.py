"""
Vice Counties Map Widget.

Displays an interactive UK map with highlighted vice counties.
Uses a simplified schematic representation of the 112 Watsonian vice counties.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtGui import QPainter

from ..theme import BACKGROUND, TEXT, VC_REGIONS


# Vice county approximate grid positions (row, col) for schematic map
# This creates a recognizable UK shape using a grid layout
# Grid is roughly 12 cols x 20 rows

VC_POSITIONS = {
    # Scotland - Northern (VCs 107-112)
    108: (0, 5), 109: (0, 6), 110: (1, 4), 111: (1, 5), 112: (1, 6),
    107: (2, 4),
    # Scotland - Central/Highland (VCs 96-106)
    105: (2, 5), 106: (2, 6), 104: (3, 4), 96: (3, 5), 97: (3, 6),
    98: (4, 4), 99: (4, 5), 100: (4, 6), 101: (5, 5), 102: (5, 6),
    103: (4, 3),
    # Scotland - West/Central (VCs 72-95)
    95: (5, 4), 94: (6, 3), 93: (6, 4), 92: (6, 5), 91: (7, 4),
    90: (7, 5), 89: (7, 6), 88: (8, 4), 87: (8, 5), 86: (8, 6),
    85: (9, 4), 84: (9, 5), 83: (9, 6), 82: (10, 5), 81: (10, 6),
    80: (10, 7), 79: (11, 5), 78: (11, 6), 77: (11, 7), 76: (12, 6),
    75: (12, 7), 74: (12, 5), 73: (13, 6), 72: (13, 7),
    
    # Northern England (VCs 66-71)
    70: (13, 8), 69: (14, 6), 68: (14, 7), 67: (14, 8), 66: (15, 6),
    71: (12, 3),  # Isle of Man
    
    # Northern England (VCs 62-65)
    65: (15, 7), 64: (15, 8), 63: (16, 6), 62: (16, 7),
    
    # North West England (VCs 58-61)
    61: (16, 5), 60: (17, 5), 59: (17, 6), 58: (17, 4),
    
    # Yorkshire/Midlands (VCs 54-57, 36-40)
    57: (16, 8), 56: (17, 7), 55: (17, 8), 54: (18, 7),
    40: (18, 6), 39: (18, 5), 38: (18, 4), 37: (19, 5), 36: (19, 6),
    
    # Wales (VCs 41-52)
    52: (15, 3), 51: (15, 4), 50: (16, 3), 49: (16, 4), 48: (17, 2),
    47: (17, 3), 46: (18, 2), 45: (18, 3), 44: (19, 2), 43: (19, 3),
    42: (20, 2), 41: (20, 3),
    
    # West Midlands (VCs 32-35)
    35: (19, 4), 34: (20, 4), 33: (20, 5), 32: (21, 5),
    
    # East Midlands (VCs 22-31, 53)
    53: (18, 8), 31: (19, 7), 30: (19, 8), 29: (20, 6), 28: (20, 7),
    27: (20, 8), 26: (21, 7), 25: (21, 8), 24: (21, 6), 23: (22, 6),
    22: (22, 7),
    
    # East Anglia (VCs 19-21)
    21: (21, 9), 20: (22, 8), 19: (22, 9),
    
    # South East (VCs 13-18)
    18: (23, 6), 17: (23, 7), 16: (23, 8), 15: (24, 7), 14: (24, 8),
    13: (24, 6),
    
    # South Central (VCs 7-12)
    12: (23, 5), 11: (24, 5), 10: (25, 5), 9: (25, 6), 8: (24, 4),
    7: (25, 4),
    
    # South West (VCs 1-6)
    6: (23, 4), 5: (24, 3), 4: (25, 3), 3: (26, 2), 2: (26, 3),
    1: (27, 1),
}


def get_region_for_vc(vc_number: int) -> str:
    """Return the region name for a VC number."""
    if 41 <= vc_number <= 52:
        return "wales"
    elif 72 <= vc_number <= 112:
        return "scotland"
    elif vc_number == 71:  # Isle of Man
        return "england"
    else:
        return "england"


class VCMapWidget(QWidget):
    """
    Widget displaying a schematic UK map with vice counties.
    """
    
    CELL_SIZE = 22
    CELL_GAP = 2
    GRID_COLS = 12
    GRID_ROWS = 28
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.visited_vcs = set()
        self.setMinimumSize(
            self.GRID_COLS * (self.CELL_SIZE + self.CELL_GAP) + 40,
            self.GRID_ROWS * (self.CELL_SIZE + self.CELL_GAP) + 40
        )
    
    def set_visited(self, vc_numbers: list):
        """Set which VCs have been visited."""
        self.visited_vcs = set(vc_numbers)
        self.update()
    
    def generate_svg(self) -> str:
        """Generate SVG map with current visited state."""
        width = self.GRID_COLS * (self.CELL_SIZE + self.CELL_GAP) + 40
        height = self.GRID_ROWS * (self.CELL_SIZE + self.CELL_GAP) + 40
        
        svg_parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">',
            f'<rect width="{width}" height="{height}" fill="transparent"/>',
        ]
        
        # Draw each VC cell
        for vc_num, (row, col) in VC_POSITIONS.items():
            x = 20 + col * (self.CELL_SIZE + self.CELL_GAP)
            y = 20 + row * (self.CELL_SIZE + self.CELL_GAP)
            
            region = get_region_for_vc(vc_num)
            region_colours = VC_REGIONS.get(region, VC_REGIONS["england"])
            
            if vc_num in self.visited_vcs:
                # Visited - full colour
                fill = region_colours["primary"]
                stroke = region_colours["highlight"]
                opacity = "1"
            else:
                # Unvisited - dimmed
                fill = BACKGROUND["surface"]
                stroke = BACKGROUND["border"]
                opacity = "0.5"
            
            # Draw rounded rectangle for each VC
            svg_parts.append(
                f'<rect x="{x}" y="{y}" width="{self.CELL_SIZE}" height="{self.CELL_SIZE}" '
                f'rx="3" ry="3" fill="{fill}" stroke="{stroke}" stroke-width="1" opacity="{opacity}">'
                f'<title>VC{vc_num}</title></rect>'
            )
            
            # Add VC number text (small)
            text_x = x + self.CELL_SIZE // 2
            text_y = y + self.CELL_SIZE // 2 + 3
            text_colour = "#ffffff" if vc_num in self.visited_vcs else TEXT["muted"]
            svg_parts.append(
                f'<text x="{text_x}" y="{text_y}" text-anchor="middle" '
                f'font-size="8" font-family="sans-serif" fill="{text_colour}">{vc_num}</text>'
            )
        
        # Add region labels
        labels = [
            ("Scotland", 150, 100),
            ("Wales", 60, 450),
            ("England", 180, 500),
        ]
        for label, lx, ly in labels:
            svg_parts.append(
                f'<text x="{lx}" y="{ly}" text-anchor="middle" '
                f'font-size="11" font-family="sans-serif" fill="{TEXT["secondary"]}" '
                f'font-weight="bold">{label}</text>'
            )
        
        svg_parts.append('</svg>')
        return '\n'.join(svg_parts)


def create_vc_map_svg(visited_vcs: list) -> str:
    """
    Create an SVG string for the VC map with visited counties highlighted.
    
    Args:
        visited_vcs: List of VC numbers that have been visited
    
    Returns:
        SVG string
    """
    widget = VCMapWidget()
    widget.set_visited(visited_vcs)
    return widget.generate_svg()
