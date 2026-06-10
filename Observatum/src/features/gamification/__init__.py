"""
Observatum V2 - Gamification Feature

A Victorian naturalist-themed achievement system with dark theme.

Achievement Types:
- Tiers (20 levels based on unique species recorded) - Shield shape
- Vice County Badges (157 VCs) - Badge shape
- Regional Completion (5 crowns) - Crown shape
- Family First (~2,500 ribbons) - Ribbon shape
- Family Depth (~10,000 medals) - Medal shape
- Rare Species First (pins) - Pin shape [future]
- Rare Species Milestones (rosettes) - Rosette shape [future]

Usage:
    from src.features.gamification import GamificationWindow, GamificationCalculator
    
    # Launch the gamification window
    window = GamificationWindow(parent)
    window.show()
    
    # Or just calculate achievements
    calc = GamificationCalculator()
    tier = calc.calculate_current_tier()
    
    # Use the launcher widget in a tab
    from src.features.gamification import GamificationLauncher
    launcher = GamificationLauncher(parent)
"""

__version__ = "2.0.0"

from .calculator import GamificationCalculator
from .window import GamificationWindow
from .setup import ensure_gamification_db, reset_gamification_db
from .launcher import GamificationLauncher, GamificationButton, GamificationSummaryCard
from .renderer import AchievementRenderer
from .notifications import NotificationCard, NotificationStack

from .models import (
    Achievement,
    AchievementType,
    TrophyTier,
    RarityTier,
    Region,
    TaxonomicGroup,
    TierAchievement,
    VCBadge,
    VCCompletion,
    FamilyFirstBadge,
    FamilyDepthMedal,
    RareSpeciesPin,
    RareMilestoneRosette,
    UserProgress,
)

from .theme import (
    TIERS,
    TROPHY_TIERS,
    TAXONOMIC_GROUPS,
    VC_REGIONS,
    RARITY_TIERS,
    PROGRESSION_STAGES,
    ONE_TIME_ACHIEVEMENTS,
    SEAL_COLOURS,
    get_tier_for_species_count,
    get_stage_colours,
    get_family_thresholds,
    get_rarity_tier,
    get_seal_colour,
)

__all__ = [
    # Version
    "__version__",
    
    # Main classes (compatible with existing code)
    'GamificationCalculator',
    'GamificationWindow',
    'ensure_gamification_db',
    'reset_gamification_db',
    'GamificationLauncher',
    'GamificationButton',
    'GamificationSummaryCard',
    
    # New classes
    'AchievementRenderer',
    'NotificationCard',
    'NotificationStack',
    
    # Models
    'Achievement',
    'AchievementType',
    'TrophyTier',
    'RarityTier',
    'Region',
    'TaxonomicGroup',
    'TierAchievement',
    'VCBadge',
    'VCCompletion',
    'FamilyFirstBadge',
    'FamilyDepthMedal',
    'RareSpeciesPin',
    'RareMilestoneRosette',
    'UserProgress',
    
    # Theme data
    'TIERS',
    'TROPHY_TIERS',
    'TAXONOMIC_GROUPS',
    'VC_REGIONS',
    'RARITY_TIERS',
    'PROGRESSION_STAGES',
    'ONE_TIME_ACHIEVEMENTS',
    'SEAL_COLOURS',
    
    # Helper functions
    'get_tier_for_species_count',
    'get_stage_colours',
    'get_family_thresholds',
    'get_rarity_tier',
    'get_seal_colour',
]
