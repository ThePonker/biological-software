"""
Observatum V2 Gamification Models
=================================
Data classes and enums for the achievement system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List


class AchievementType(Enum):
    """Types of achievements."""
    TIER = "tier"
    VC_BADGE = "vc_badge"
    VC_COMPLETION = "vc_completion"
    FAMILY_FIRST = "family_first"
    FAMILY_DEPTH = "family_depth"
    RARE_SPECIES = "rare_species"
    RARE_MILESTONE = "rare_milestone"


class TrophyTier(Enum):
    """Trophy tier levels."""
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"


class RarityTier(Enum):
    """Rarity classification tiers."""
    UNCOMMON = "uncommon"
    RARE = "rare"
    VERY_RARE = "very_rare"
    CRITICAL = "critical"
    PROTECTED = "protected"


class Region(Enum):
    """Vice county regions."""
    ENGLAND = "england"
    WALES = "wales"
    SCOTLAND = "scotland"
    IRELAND = "ireland"


class TaxonomicGroup(Enum):
    """Taxonomic groups for families."""
    INSECTS = "insects"
    OTHER_INVERTEBRATES = "other_invertebrates"
    VERTEBRATES = "vertebrates"
    PLANTS = "plants"
    FUNGI = "fungi"
    OTHER = "other"


@dataclass
class Achievement:
    """Base achievement class."""
    id: str
    achievement_type: AchievementType
    name: str
    description: str
    earned: bool = False
    earned_date: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.achievement_type.value,
            "name": self.name,
            "description": self.description,
            "earned": self.earned,
            "earned_date": self.earned_date.isoformat() if self.earned_date else None,
        }


@dataclass
class TierAchievement(Achievement):
    """Progression tier achievement."""
    tier_number: int = 1
    stage: str = "beginner"
    min_species: int = 0
    max_species: Optional[int] = 500
    
    def __post_init__(self):
        self.achievement_type = AchievementType.TIER


@dataclass
class VCBadge(Achievement):
    """Vice county badge."""
    vc_number: int = 0
    vc_name: str = ""
    region: str = "england"
    
    def __post_init__(self):
        self.achievement_type = AchievementType.VC_BADGE


@dataclass
class VCCompletion(Achievement):
    """Regional VC completion badge (Crown)."""
    region: Optional[str] = None  # None = Ultimate (all regions)
    vc_count: int = 0
    
    def __post_init__(self):
        self.achievement_type = AchievementType.VC_COMPLETION


@dataclass
class FamilyFirstBadge(Achievement):
    """First observation from a family (Ribbon)."""
    family_name: str = ""
    order_name: str = ""
    taxonomic_group: str = "other"
    
    def __post_init__(self):
        self.achievement_type = AchievementType.FAMILY_FIRST


@dataclass
class FamilyDepthMedal(Achievement):
    """Trophy for species count within a family (Medal)."""
    family_name: str = ""
    order_name: str = ""
    taxonomic_group: str = "other"
    trophy_tier: str = "bronze"
    species_count: int = 0
    family_total: int = 0
    
    def __post_init__(self):
        self.achievement_type = AchievementType.FAMILY_DEPTH


@dataclass
class RareSpeciesPin(Achievement):
    """Badge for observing a rare species (Pin)."""
    species_name: str = ""
    tvk: str = ""
    rarity_tier: str = "uncommon"
    designation: str = ""
    
    def __post_init__(self):
        self.achievement_type = AchievementType.RARE_SPECIES


@dataclass
class RareMilestoneRosette(Achievement):
    """Milestone trophy for rare species counts (Rosette)."""
    milestone_name: str = ""
    threshold: int = 0
    trophy_tier: str = "bronze"
    rarity_tier: Optional[str] = None  # None = general milestone
    current_count: int = 0
    
    def __post_init__(self):
        self.achievement_type = AchievementType.RARE_MILESTONE


@dataclass
class UserProgress:
    """Current progress summary for a user."""
    total_species: int = 0
    total_observations: int = 0
    current_tier: int = 1
    tier_name: str = "Junior Naturalist"
    tier_stage: str = "beginner"
    species_to_next_tier: int = 500
    progress_percent: float = 0.0
    next_tier_name: Optional[str] = "Apprentice Naturalist"
    
    vcs_visited: int = 0
    vc_total: int = 112
    regions_complete: List[str] = field(default_factory=list)
    
    families_observed: int = 0
    family_medals: dict = field(default_factory=dict)
    
    rare_species_count: int = 0
    rare_by_tier: dict = field(default_factory=dict)
    
    recent_achievements: List[Achievement] = field(default_factory=list)


@dataclass
class NewAchievementNotification:
    """Notification for a newly earned achievement."""
    achievement: Achievement
    timestamp: datetime = field(default_factory=datetime.now)
    seen: bool = False
    
    @property
    def title(self) -> str:
        return self.achievement.name
    
    @property
    def description(self) -> str:
        return self.achievement.description
    
    @property
    def achievement_type(self) -> AchievementType:
        return self.achievement.achievement_type
