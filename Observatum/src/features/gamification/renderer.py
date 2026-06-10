"""
Observatum V2 Gamification Renderer
====================================
SVG rendering for achievement badges, medals, pins, etc.
All 7 shapes: Shield, Badge, Ribbon, Medal, Pin, Rosette, Crown
"""

from pathlib import Path
from typing import Optional

from .theme import (
    TROPHY_TIERS, TAXONOMIC_GROUPS, VC_REGIONS, RARITY_TIERS,
    PROGRESSION_STAGES, ICON_SIZES, GROUP_ICONS, get_stage_colours
)


class AchievementRenderer:
    """
    Renders SVG badges for achievements.
    
    Usage:
        renderer = AchievementRenderer()
        svg = renderer.render_shield(tier=10, stage="experienced", size="medium")
    """
    
    def __init__(self, icons_path: Optional[Path] = None):
        """
        Initialize renderer.
        
        Args:
            icons_path: Path to order icons folder.
        """
        if icons_path:
            self.icons_path = Path(icons_path)
        else:
            self.icons_path = Path(__file__).parent / "assets" / "icons" / "orders"
    
    def get_size(self, size: str) -> int:
        """Get pixel size for named size."""
        return ICON_SIZES.get(size, ICON_SIZES["medium"])
    
    # =========================================================================
    # SHIELD - Progression Tiers
    # =========================================================================
    
    def render_shield(
        self,
        tier: int,
        stage: str,
        size: str = "medium"
    ) -> str:
        """
        Render a shield for progression tiers.
        
        Args:
            tier: Tier number (1-20)
            stage: Stage name (beginner, developing, etc.)
            size: small, medium, or large
        """
        px = self.get_size(size)
        colours = get_stage_colours(stage)
        
        scale = px / 80
        height = int(100 * scale)
        
        glow = ""
        if stage in ("master", "platinum"):
            glow_colour = colours.get("glow", "rgba(200,200,200,0.3)")
            glow = f'filter="drop-shadow(0 0 {8 if stage == "platinum" else 4}px {glow_colour})"'
        
        tier_text = str(tier)
        font_size = 22 if tier >= 10 else 26
        
        svg = f'''<svg viewBox="0 0 80 100" width="{px}" height="{height}" xmlns="http://www.w3.org/2000/svg" {glow}>
  <defs>
    <linearGradient id="shieldGrad_{tier}" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{colours['highlight']}"/>
      <stop offset="100%" style="stop-color:{colours['shadow']}"/>
    </linearGradient>
    <radialGradient id="shieldVig_{tier}" cx="50%" cy="35%" r="60%">
      <stop offset="0%" style="stop-color:{colours['vignette_light']}"/>
      <stop offset="100%" style="stop-color:{colours['vignette_dark']}"/>
    </radialGradient>
  </defs>
  <path fill="url(#shieldVig_{tier})" stroke="url(#shieldGrad_{tier})" stroke-width="3"
        d="M40 5 Q55 5 68 15 Q75 25 75 45 Q75 70 58 85 Q45 98 40 98 Q35 98 22 85 Q5 70 5 45 Q5 25 12 15 Q25 5 40 5 Z"/>
  <path fill="none" stroke="{colours['primary']}" stroke-width="1.5" d="M15 25 Q8 35 10 50"/>
  <path fill="none" stroke="{colours['primary']}" stroke-width="1.5" d="M65 25 Q72 35 70 50"/>
  <circle fill="{colours['primary']}" cx="40" cy="8" r="3"/>
  <ellipse fill="{colours['primary']}" cx="12" cy="22" rx="3" ry="5" transform="rotate(-30 12 22)"/>
  <ellipse fill="{colours['primary']}" cx="68" cy="22" rx="3" ry="5" transform="rotate(30 68 22)"/>
  <text x="40" y="56" text-anchor="middle" fill="{colours['highlight']}" 
        font-size="{font_size}" font-weight="bold" font-family="Georgia, serif">{tier_text}</text>
</svg>'''
        return svg
    
    def render_locked_shield(
        self,
        size: str = "medium"
    ) -> str:
        """
        Render a locked/unknown shield for future tiers.
        
        Args:
            size: small, medium, or large
        """
        px = self.get_size(size)
        scale = px / 80
        height = int(100 * scale)
        
        svg = f'''<svg viewBox="0 0 80 100" width="{px}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="lockedGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#555555"/>
      <stop offset="100%" style="stop-color:#333333"/>
    </linearGradient>
    <radialGradient id="lockedVig" cx="50%" cy="35%" r="60%">
      <stop offset="0%" style="stop-color:#2a2a2a"/>
      <stop offset="100%" style="stop-color:#1a1a1a"/>
    </radialGradient>
  </defs>
  <path fill="url(#lockedVig)" stroke="url(#lockedGrad)" stroke-width="3"
        d="M40 5 Q55 5 68 15 Q75 25 75 45 Q75 70 58 85 Q45 98 40 98 Q35 98 22 85 Q5 70 5 45 Q5 25 12 15 Q25 5 40 5 Z"/>
  <text x="40" y="60" text-anchor="middle" fill="#666666" 
        font-size="32" font-weight="bold" font-family="Georgia, serif">?</text>
</svg>'''
        return svg
    
    # =========================================================================
    # BADGE - Vice Counties
    # =========================================================================
    
    def render_badge(
        self,
        vc_number: int,
        region: str,
        size: str = "medium"
    ) -> str:
        """
        Render a badge for vice counties.
        
        Args:
            vc_number: VC number
            region: Region name (england, wales, scotland, ireland)
            size: small, medium, or large
        """
        px = self.get_size(size)
        colours = VC_REGIONS.get(region, VC_REGIONS["england"])
        
        scale = px / 80
        height = int(90 * scale)
        
        svg = f'''<svg viewBox="0 0 80 90" width="{px}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="badgeGrad_{vc_number}" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{colours['highlight']}"/>
      <stop offset="100%" style="stop-color:{colours['shadow']}"/>
    </linearGradient>
  </defs>
  <path fill="{colours['vignette_light']}" stroke="url(#badgeGrad_{vc_number})" stroke-width="3"
        d="M10 10 L70 10 L70 50 Q70 70 40 85 Q10 70 10 50 Z"/>
  <text x="40" y="52" text-anchor="middle" fill="{colours['highlight']}" 
        font-size="22" font-weight="bold" font-family="Georgia, serif">{vc_number}</text>
</svg>'''
        return svg
    
    # =========================================================================
    # RIBBON - Family First
    # =========================================================================
    
    def render_ribbon(
        self,
        family: str,
        taxonomic_group: str,
        size: str = "medium"
    ) -> str:
        """
        Render a ribbon for family first badges with family name text.
        
        Args:
            family: Family name
            taxonomic_group: Taxonomic group name
            size: small, medium, or large
        """
        px = self.get_size(size)
        colours = TAXONOMIC_GROUPS.get(taxonomic_group, TAXONOMIC_GROUPS["other"])
        
        scale = px / 60
        height = int(100 * scale)
        
        # Unique ID based on family name hash
        uid = abs(hash(family)) % 10000
        
        # Truncate family name if too long (max ~12 chars)
        display_name = family[:12] + "." if len(family) > 12 else family
        
        # Determine text colour (light on dark background)
        text_colour = colours.get('vignette_light', '#ffffff')
        
        svg = f'''<svg viewBox="0 0 60 100" width="{px}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="ribbonGrad_{uid}" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{colours['highlight']}"/>
      <stop offset="100%" style="stop-color:{colours['shadow']}"/>
    </linearGradient>
  </defs>
  <path fill="{colours['vignette_light']}" stroke="url(#ribbonGrad_{uid})" stroke-width="2.5"
        d="M10 5 L50 5 L50 80 L30 70 L10 80 Z"/>
  <path fill="{colours['primary']}" d="M10 5 L50 5 L50 12 L10 12 Z"/>
  <circle fill="{colours['primary']}" cx="30" cy="40" r="14"/>
  <!-- Family name text - rotated vertically -->
  <text x="30" y="60" text-anchor="middle" 
        font-family="Georgia, serif" font-size="6" font-weight="bold"
        fill="{colours['shadow']}" transform="rotate(-90, 30, 45)">
    {display_name}
  </text>
</svg>'''
        return svg
    
    # =========================================================================
    # MEDAL - Family Depth
    # =========================================================================
    
    def render_medal(
        self,
        trophy_tier: str,
        size: str = "medium"
    ) -> str:
        """
        Render a medal for family depth trophies.
        
        Args:
            trophy_tier: bronze, silver, gold, or platinum
            size: small, medium, or large
        """
        px = self.get_size(size)
        colours = TROPHY_TIERS.get(trophy_tier, TROPHY_TIERS["bronze"])
        
        scale = px / 80
        height = int(100 * scale)
        
        glow = ""
        if trophy_tier == "platinum":
            glow = f'filter="drop-shadow(0 0 6px {colours.get("glow", "rgba(200,200,200,0.4)")})"'
        
        svg = f'''<svg viewBox="0 0 80 100" width="{px}" height="{height}" xmlns="http://www.w3.org/2000/svg" {glow}>
  <defs>
    <linearGradient id="medalGrad_{trophy_tier}" x1="0%" y1="0%" x2="50%" y2="100%">
      <stop offset="0%" style="stop-color:{colours['highlight']}"/>
      <stop offset="50%" style="stop-color:{colours['primary']}"/>
      <stop offset="100%" style="stop-color:{colours['shadow']}"/>
    </linearGradient>
    <radialGradient id="medalVig_{trophy_tier}" cx="50%" cy="35%" r="60%">
      <stop offset="0%" style="stop-color:{colours['vignette_light']}"/>
      <stop offset="100%" style="stop-color:{colours['vignette_dark']}"/>
    </radialGradient>
  </defs>
  <path fill="{colours['primary']}" d="M25 5 L35 5 L40 25 L45 5 L55 5 L45 35 L40 50 L35 35 Z"/>
  <circle fill="url(#medalVig_{trophy_tier})" stroke="url(#medalGrad_{trophy_tier})" stroke-width="4" cx="40" cy="62" r="28"/>
  <circle fill="none" stroke="{colours['primary']}" stroke-width="1.5" cx="40" cy="62" r="20"/>
  <polygon fill="{colours['primary']}" points="40,48 43,56 52,56 45,62 48,70 40,65 32,70 35,62 28,56 37,56"/>
</svg>'''
        return svg
    
    # =========================================================================
    # PIN - Rare Species First
    # =========================================================================
    
    def render_pin(
        self,
        rarity_tier: str,
        size: str = "medium"
    ) -> str:
        """
        Render a pin for rare species badges.
        
        Args:
            rarity_tier: uncommon, rare, very_rare, critical, or protected
            size: small, medium, or large
        """
        px = self.get_size(size)
        colours = RARITY_TIERS.get(rarity_tier, RARITY_TIERS["uncommon"])
        
        scale = px / 60
        height = int(70 * scale)
        
        glow = ""
        if rarity_tier == "protected":
            glow = f'filter="drop-shadow(0 0 5px {colours.get("glow", "rgba(180,100,220,0.5)")})"'
        
        svg = f'''<svg viewBox="0 0 60 70" width="{px}" height="{height}" xmlns="http://www.w3.org/2000/svg" {glow}>
  <defs>
    <linearGradient id="pinGrad_{rarity_tier}" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{colours['highlight']}"/>
      <stop offset="100%" style="stop-color:{colours['shadow']}"/>
    </linearGradient>
  </defs>
  <circle fill="{colours['vignette_light']}" stroke="url(#pinGrad_{rarity_tier})" stroke-width="3" cx="30" cy="30" r="22"/>
  <circle fill="none" stroke="{colours['primary']}" stroke-width="1" cx="30" cy="30" r="15"/>
  <polygon fill="{colours['primary']}" points="30,20 32,26 38,26 33,30 35,36 30,32 25,36 27,30 22,26 28,26"/>
</svg>'''
        return svg
    
    # =========================================================================
    # ROSETTE - Rare Species Milestones
    # =========================================================================
    
    def render_rosette(
        self,
        trophy_tier: str,
        size: str = "medium"
    ) -> str:
        """
        Render a rosette for rare species milestones.
        
        Args:
            trophy_tier: bronze, silver, gold, or platinum
            size: small, medium, or large
        """
        px = self.get_size(size)
        colours = TROPHY_TIERS.get(trophy_tier, TROPHY_TIERS["bronze"])
        
        shadow = colours["shadow"]
        
        scale = px / 80
        height = int(100 * scale)
        
        glow = ""
        if trophy_tier == "platinum":
            glow = f'filter="drop-shadow(0 0 6px {colours.get("glow", "rgba(200,200,200,0.4)")})"'
        
        svg = f'''<svg viewBox="0 0 80 100" width="{px}" height="{height}" xmlns="http://www.w3.org/2000/svg" {glow}>
  <defs>
    <linearGradient id="rosetteGrad_{trophy_tier}" x1="0%" y1="0%" x2="50%" y2="100%">
      <stop offset="0%" style="stop-color:{colours['highlight']}"/>
      <stop offset="50%" style="stop-color:{colours['primary']}"/>
      <stop offset="100%" style="stop-color:{colours['shadow']}"/>
    </linearGradient>
    <radialGradient id="rosetteVig_{trophy_tier}" cx="50%" cy="35%" r="60%">
      <stop offset="0%" style="stop-color:{colours['vignette_light']}"/>
      <stop offset="100%" style="stop-color:{colours['vignette_dark']}"/>
    </radialGradient>
  </defs>
  <path fill="{colours['primary']}" d="M30 60 L25 95 L32 80 L40 95 L40 60 Z"/>
  <path fill="{shadow}" d="M50 60 L55 95 L48 80 L40 95 L40 60 Z"/>
  <circle fill="url(#rosetteVig_{trophy_tier})" stroke="url(#rosetteGrad_{trophy_tier})" stroke-width="4" cx="40" cy="40" r="30"/>
  <circle fill="none" stroke="{colours['primary']}" stroke-width="2" stroke-dasharray="4 3" cx="40" cy="40" r="24"/>
  <circle fill="url(#rosetteGrad_{trophy_tier})" cx="40" cy="40" r="14"/>
</svg>'''
        return svg
    
    # =========================================================================
    # CROWN - Regional Completion
    # =========================================================================
    
    def render_crown(
        self,
        region: Optional[str] = None,
        size: str = "medium"
    ) -> str:
        """
        Render a crown for regional completion.
        
        Args:
            region: Region name, or None for ultimate
            size: small, medium, or large
        """
        px = self.get_size(size)
        
        if region:
            colours = VC_REGIONS.get(region, VC_REGIONS["england"])
            letter = colours["letter"]
            scale = px / 80
            height = int(90 * scale)
            
            svg = f'''<svg viewBox="0 0 80 90" width="{px}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="crownGrad_{region}" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{colours['highlight']}"/>
      <stop offset="100%" style="stop-color:{colours['shadow']}"/>
    </linearGradient>
  </defs>
  <path fill="{colours['vignette_light']}" stroke="url(#crownGrad_{region})" stroke-width="3"
        d="M10 50 L10 75 L70 75 L70 50 L55 60 L40 45 L25 60 Z"/>
  <circle fill="{colours['primary']}" cx="10" cy="50" r="5"/>
  <circle fill="{colours['primary']}" cx="40" cy="40" r="6"/>
  <circle fill="{colours['primary']}" cx="70" cy="50" r="5"/>
  <text x="40" y="68" text-anchor="middle" fill="{colours['highlight']}" 
        font-size="14" font-weight="bold" font-family="Georgia, serif">{letter}</text>
</svg>'''
        else:
            # Ultimate crown with all 4 colours
            scale = px / 90
            height = int(100 * scale)
            
            svg = f'''<svg viewBox="0 0 90 100" width="{px}" height="{height}" xmlns="http://www.w3.org/2000/svg"
     filter="drop-shadow(0 0 6px rgba(200, 180, 100, 0.4))">
  <defs>
    <linearGradient id="ultimateGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#CE1124"/>
      <stop offset="25%" style="stop-color:#00AB39"/>
      <stop offset="50%" style="stop-color:#0065BD"/>
      <stop offset="75%" style="stop-color:#169B62"/>
      <stop offset="100%" style="stop-color:#c9a227"/>
    </linearGradient>
  </defs>
  <path fill="#2a2520" stroke="url(#ultimateGrad)" stroke-width="4"
        d="M10 55 L10 80 L80 80 L80 55 L62 65 L45 48 L28 65 Z"/>
  <circle fill="#CE1124" cx="10" cy="55" r="6"/>
  <circle fill="#c9a227" cx="45" cy="42" r="8"/>
  <circle fill="#0065BD" cx="80" cy="55" r="6"/>
  <text x="23" y="74" text-anchor="middle" fill="#CE1124" font-size="10" font-weight="bold" font-family="Georgia, serif">E</text>
  <text x="37" y="74" text-anchor="middle" fill="#00AB39" font-size="10" font-weight="bold" font-family="Georgia, serif">W</text>
  <text x="53" y="74" text-anchor="middle" fill="#0065BD" font-size="10" font-weight="bold" font-family="Georgia, serif">S</text>
  <text x="67" y="74" text-anchor="middle" fill="#169B62" font-size="10" font-weight="bold" font-family="Georgia, serif">I</text>
</svg>'''
        
        return svg
    
    # =========================================================================
    # SEAL - One-Time Achievements (Daily/Annual Records)
    # =========================================================================
    
    def render_seal(
        self,
        colour: str,
        earned: bool = False,
        period: str = "daily",
        group: str = "general",
        size: str = "medium"
    ) -> str:
        """
        Render a Victorian wax seal for one-time achievements.
        
        Args:
            colour: Hex colour for the seal
            earned: Whether the achievement has been earned
            period: 'daily' or 'annual' (affects fallback icon)
            group: Taxonomic group (for group-specific icons)
            size: small, medium, or large
        """
        px = self.get_size(size)
        scale = px / 80
        height = int(80 * scale)
        
        if earned:
            # Full colour seal
            # Derive lighter/darker shades from base colour
            primary = colour
            highlight = self._lighten_colour(colour, 0.3)
            shadow = self._darken_colour(colour, 0.3)
            vignette_light = self._darken_colour(colour, 0.5)
            vignette_dark = self._darken_colour(colour, 0.7)
            
            # Try to load group-specific icon
            group_icon_content = self._load_group_icon(group, highlight)
            
            if group_icon_content:
                centre_icon = group_icon_content
            elif period == "daily":
                # Fallback: sun icon for daily
                centre_icon = f'''
    <circle fill="{highlight}" cx="40" cy="40" r="8"/>
    <g stroke="{highlight}" stroke-width="2">
      <line x1="40" y1="28" x2="40" y2="24"/>
      <line x1="40" y1="52" x2="40" y2="56"/>
      <line x1="28" y1="40" x2="24" y2="40"/>
      <line x1="52" y1="40" x2="56" y2="40"/>
      <line x1="31" y1="31" x2="28" y2="28"/>
      <line x1="49" y1="31" x2="52" y2="28"/>
      <line x1="31" y1="49" x2="28" y2="52"/>
      <line x1="49" y1="49" x2="52" y2="52"/>
    </g>'''
            else:
                # Fallback: calendar icon for annual
                centre_icon = f'''
    <rect fill="{highlight}" x="30" y="32" width="20" height="16" rx="2"/>
    <rect fill="{shadow}" x="30" y="32" width="20" height="4" rx="1"/>
    <line stroke="{highlight}" stroke-width="1.5" x1="34" y1="29" x2="34" y2="33"/>
    <line stroke="{highlight}" stroke-width="1.5" x1="46" y1="29" x2="46" y2="33"/>'''
        else:
            # Greyed out seal
            primary = "#555555"
            highlight = "#777777"
            shadow = "#333333"
            vignette_light = "#2a2a2a"
            vignette_dark = "#1a1a1a"
            
            # Try to load group icon (greyed)
            group_icon_content = self._load_group_icon(group, "#666666")
            
            if group_icon_content:
                centre_icon = group_icon_content
            else:
                centre_icon = f'''
    <text x="40" y="46" text-anchor="middle" fill="#666666" 
          font-size="20" font-weight="bold" font-family="Georgia, serif">?</text>'''
        
        # Generate unique ID
        uid = abs(hash(f"{colour}_{earned}_{period}_{group}")) % 10000
        
        # Scalloped edge path (12 points)
        svg = f'''<svg viewBox="0 0 80 80" width="{px}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="sealGrad_{uid}" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{highlight}"/>
      <stop offset="100%" style="stop-color:{shadow}"/>
    </linearGradient>
    <radialGradient id="sealVig_{uid}" cx="50%" cy="40%" r="55%">
      <stop offset="0%" style="stop-color:{vignette_light}"/>
      <stop offset="100%" style="stop-color:{vignette_dark}"/>
    </radialGradient>
  </defs>
  <path fill="url(#sealVig_{uid})" stroke="url(#sealGrad_{uid})" stroke-width="2.5"
        d="M40 5 Q48 10 52 8 Q58 12 58 18 Q65 22 62 28 Q68 35 65 40 
           Q68 45 62 52 Q65 58 58 62 Q58 68 52 72 Q48 70 40 75 
           Q32 70 28 72 Q22 68 22 62 Q15 58 18 52 Q12 45 15 40 
           Q12 35 18 28 Q15 22 22 18 Q22 12 28 8 Q32 10 40 5 Z"/>
  <circle fill="none" stroke="{primary}" stroke-width="1" cx="40" cy="40" r="22"/>
  {centre_icon}
</svg>'''
        return svg
    
    def _load_group_icon(self, group: str, fill_colour: str) -> Optional[str]:
        """
        Try to load a group-specific icon from assets.
        
        Args:
            group: Taxonomic group name
            fill_colour: Colour to apply to the icon
            
        Returns:
            SVG content string for the icon, or None if not found
        """
        icon_filename = GROUP_ICONS.get(group)
        if not icon_filename:
            return None
        
        # Build path to icon
        if self.icons_path:
            icon_path = self.icons_path / "groups" / icon_filename
        else:
            # Try relative to this file
            icon_path = Path(__file__).parent / "assets" / "icons" / "groups" / icon_filename
        
        if not icon_path.exists():
            return None
        
        try:
            # Read the SVG file
            svg_content = icon_path.read_text()
            
            # Extract just the path/shape content (basic extraction)
            # Icons should be simple SVGs with paths/shapes
            import re
            
            # Find path elements and apply fill colour
            # This is a simple approach - expects icons to have <path> or <g> elements
            paths = re.findall(r'<path[^>]*d="([^"]*)"[^>]*/>', svg_content)
            
            if paths:
                # Create centred icon group (icons should be designed for ~30x30 space centred at 40,40)
                icon_svg = f'<g transform="translate(25, 25) scale(0.375)" fill="{fill_colour}">'
                for path_d in paths:
                    icon_svg += f'<path d="{path_d}"/>'
                icon_svg += '</g>'
                return icon_svg
            
            # Try finding any path with d attribute
            path_match = re.search(r'd="([^"]+)"', svg_content)
            if path_match:
                path_d = path_match.group(1)
                return f'''<g transform="translate(25, 25) scale(0.375)" fill="{fill_colour}">
      <path d="{path_d}"/>
    </g>'''
            
            return None
            
        except Exception as e:
            print(f"[Gamification] Error loading group icon {icon_filename}: {e}")
            return None
    
    def render_seal_unearned(
        self,
        size: str = "medium"
    ) -> str:
        """Render a greyed out unearned seal."""
        return self.render_seal("#555555", earned=False, size=size)
    
    def _lighten_colour(self, hex_colour: str, factor: float) -> str:
        """Lighten a hex colour by a factor (0-1)."""
        hex_colour = hex_colour.lstrip('#')
        r = int(hex_colour[0:2], 16)
        g = int(hex_colour[2:4], 16)
        b = int(hex_colour[4:6], 16)
        
        r = min(255, int(r + (255 - r) * factor))
        g = min(255, int(g + (255 - g) * factor))
        b = min(255, int(b + (255 - b) * factor))
        
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def _darken_colour(self, hex_colour: str, factor: float) -> str:
        """Darken a hex colour by a factor (0-1)."""
        hex_colour = hex_colour.lstrip('#')
        r = int(hex_colour[0:2], 16)
        g = int(hex_colour[2:4], 16)
        b = int(hex_colour[4:6], 16)
        
        r = max(0, int(r * (1 - factor)))
        g = max(0, int(g * (1 - factor)))
        b = max(0, int(b * (1 - factor)))
        
        return f"#{r:02x}{g:02x}{b:02x}"
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def render_achievement(
        self,
        achievement_type: str,
        size: str = "medium",
        **kwargs
    ) -> str:
        """
        Render any achievement type by name.
        
        Args:
            achievement_type: Type name (tier, vc_badge, etc.)
            size: small, medium, or large
            **kwargs: Type-specific parameters
        """
        if achievement_type == "tier":
            return self.render_shield(
                tier=kwargs.get("tier", 1),
                stage=kwargs.get("stage", "beginner"),
                size=size
            )
        elif achievement_type == "vc_badge":
            return self.render_badge(
                vc_number=kwargs.get("vc_number", 1),
                region=kwargs.get("region", "england"),
                size=size
            )
        elif achievement_type == "vc_completion":
            return self.render_crown(
                region=kwargs.get("region"),
                size=size
            )
        elif achievement_type == "family_first":
            return self.render_ribbon(
                family=kwargs.get("family", "Unknown"),
                taxonomic_group=kwargs.get("taxonomic_group", "other"),
                size=size
            )
        elif achievement_type == "family_depth":
            return self.render_medal(
                trophy_tier=kwargs.get("trophy_tier", "bronze"),
                size=size
            )
        elif achievement_type == "rare_species":
            return self.render_pin(
                rarity_tier=kwargs.get("rarity_tier", "uncommon"),
                size=size
            )
        elif achievement_type == "rare_milestone":
            return self.render_rosette(
                trophy_tier=kwargs.get("trophy_tier", "bronze"),
                size=size
            )
        else:
            return ""
    
    def load_order_icon(self, order: str) -> Optional[str]:
        """
        Load an order icon SVG if it exists.
        
        Args:
            order: Order name (e.g., "Coleoptera")
        
        Returns:
            SVG content string or None if not found
        """
        if not self.icons_path.exists():
            return None
        icon_file = self.icons_path / f"{order.lower()}.svg"
        if icon_file.exists():
            return icon_file.read_text()
        return None
