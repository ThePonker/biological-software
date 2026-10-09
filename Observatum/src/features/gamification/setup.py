"""
Gamification Database Setup for Observatum V2.

Creates and initializes the gamification.db database.
Called automatically when the gamification window is first opened.
"""

import sqlite3
import paths
from pathlib import Path
from typing import Optional

# Try to import from config
try:
    from src.core.config import Paths  # noqa: F401  (availability check / re-export)
    USE_CONFIG = True
except ImportError:
    USE_CONFIG = False


def _find_data_dir() -> Path:
    """Find the data directory when config is not available."""
    this_file = Path(__file__).resolve()
    project_root = this_file.parent.parent.parent.parent
    return project_root / "data"


def get_gamification_db_path() -> Path:
    """Get the path to the gamification database."""
    if USE_CONFIG:
        return paths.DATA_DIR / "gamification.db"
    else:
        return paths.DATA_DIR / "gamification.db"


# =============================================================================
# VICE COUNTY DATA
# =============================================================================

VICE_COUNTIES = [
    # England (VC 1-40, 53-71)
    (1, "West Cornwall", "England"),
    (2, "East Cornwall", "England"),
    (3, "South Devon", "England"),
    (4, "North Devon", "England"),
    (5, "South Somerset", "England"),
    (6, "North Somerset", "England"),
    (7, "North Wiltshire", "England"),
    (8, "South Wiltshire", "England"),
    (9, "Dorset", "England"),
    (10, "Isle of Wight", "England"),
    (11, "South Hampshire", "England"),
    (12, "North Hampshire", "England"),
    (13, "West Sussex", "England"),
    (14, "East Sussex", "England"),
    (15, "East Kent", "England"),
    (16, "West Kent", "England"),
    (17, "Surrey", "England"),
    (18, "South Essex", "England"),
    (19, "North Essex", "England"),
    (20, "Hertfordshire", "England"),
    (21, "Middlesex", "England"),
    (22, "Berkshire", "England"),
    (23, "Oxfordshire", "England"),
    (24, "Buckinghamshire", "England"),
    (25, "East Suffolk", "England"),
    (26, "West Suffolk", "England"),
    (27, "East Norfolk", "England"),
    (28, "West Norfolk", "England"),
    (29, "Cambridgeshire", "England"),
    (30, "Bedfordshire", "England"),
    (31, "Huntingdonshire", "England"),
    (32, "Northamptonshire", "England"),
    (33, "East Gloucestershire", "England"),
    (34, "West Gloucestershire", "England"),
    (35, "Monmouthshire", "England"),
    (36, "Herefordshire", "England"),
    (37, "Worcestershire", "England"),
    (38, "Warwickshire", "England"),
    (39, "Staffordshire", "England"),
    (40, "Shropshire", "England"),
    (53, "South Lincolnshire", "England"),
    (54, "North Lincolnshire", "England"),
    (55, "Leicestershire", "England"),
    (56, "Nottinghamshire", "England"),
    (57, "Derbyshire", "England"),
    (58, "Cheshire", "England"),
    (59, "South Lancashire", "England"),
    (60, "West Lancashire", "England"),
    (61, "South-east Yorkshire", "England"),
    (62, "North-east Yorkshire", "England"),
    (63, "South-west Yorkshire", "England"),
    (64, "Mid-west Yorkshire", "England"),
    (65, "North-west Yorkshire", "England"),
    (66, "Durham", "England"),
    (67, "South Northumberland", "England"),
    (68, "North Northumberland", "England"),
    (69, "Westmorland", "England"),
    (70, "Cumberland", "England"),
    (71, "Isle of Man", "England"),
    # Wales (VC 41-52)
    (41, "Glamorgan", "Wales"),
    (42, "Breconshire", "Wales"),
    (43, "Radnorshire", "Wales"),
    (44, "Carmarthenshire", "Wales"),
    (45, "Pembrokeshire", "Wales"),
    (46, "Cardiganshire", "Wales"),
    (47, "Montgomeryshire", "Wales"),
    (48, "Merionethshire", "Wales"),
    (49, "Caernarvonshire", "Wales"),
    (50, "Denbighshire", "Wales"),
    (51, "Flintshire", "Wales"),
    (52, "Anglesey", "Wales"),
    # Scotland (VC 72-112)
    (72, "Dumfriesshire", "Scotland"),
    (73, "Kirkcudbrightshire", "Scotland"),
    (74, "Wigtownshire", "Scotland"),
    (75, "Ayrshire", "Scotland"),
    (76, "Renfrewshire", "Scotland"),
    (77, "Lanarkshire", "Scotland"),
    (78, "Peeblesshire", "Scotland"),
    (79, "Selkirkshire", "Scotland"),
    (80, "Roxburghshire", "Scotland"),
    (81, "Berwickshire", "Scotland"),
    (82, "East Lothian", "Scotland"),
    (83, "Midlothian", "Scotland"),
    (84, "West Lothian", "Scotland"),
    (85, "Fifeshire", "Scotland"),
    (86, "Stirlingshire", "Scotland"),
    (87, "West Perthshire", "Scotland"),
    (88, "Mid Perthshire", "Scotland"),
    (89, "East Perthshire", "Scotland"),
    (90, "Angus", "Scotland"),
    (91, "Kincardineshire", "Scotland"),
    (92, "South Aberdeenshire", "Scotland"),
    (93, "North Aberdeenshire", "Scotland"),
    (94, "Banffshire", "Scotland"),
    (95, "Moray", "Scotland"),
    (96, "Easterness", "Scotland"),
    (97, "Westerness", "Scotland"),
    (98, "Main Argyll", "Scotland"),
    (99, "Dunbartonshire", "Scotland"),
    (100, "Clyde Isles", "Scotland"),
    (101, "Kintyre", "Scotland"),
    (102, "South Ebudes", "Scotland"),
    (103, "Mid Ebudes", "Scotland"),
    (104, "North Ebudes", "Scotland"),
    (105, "West Ross", "Scotland"),
    (106, "East Ross", "Scotland"),
    (107, "East Sutherland", "Scotland"),
    (108, "West Sutherland", "Scotland"),
    (109, "Caithness", "Scotland"),
    (110, "Outer Hebrides", "Scotland"),
    (111, "Orkney", "Scotland"),
    (112, "Shetland", "Scotland"),
]


# =============================================================================
# DATABASE SCHEMA
# =============================================================================

SCHEMA_SQL = """
-- ============================================================================
-- Tier Progression
-- ============================================================================
CREATE TABLE IF NOT EXISTS gamification_tiers (
    tier_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tier_number INTEGER NOT NULL CHECK(tier_number BETWEEN 1 AND 20),
    tier_name TEXT NOT NULL,
    species_count INTEGER NOT NULL,
    observation_count INTEGER NOT NULL,
    date_reached DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tier_number)
);

CREATE INDEX IF NOT EXISTS idx_gamification_tiers_number ON gamification_tiers(tier_number);
CREATE INDEX IF NOT EXISTS idx_gamification_tiers_date ON gamification_tiers(date_reached DESC);

-- ============================================================================
-- Vice County Coverage
-- ============================================================================
CREATE TABLE IF NOT EXISTS gamification_vice_county_coverage (
    coverage_id INTEGER PRIMARY KEY AUTOINCREMENT,
    vc_number INTEGER NOT NULL UNIQUE,
    vice_county_name TEXT NOT NULL,
    region TEXT NOT NULL,
    observation_count INTEGER NOT NULL DEFAULT 0,
    species_count INTEGER NOT NULL DEFAULT 0,
    date_first_recorded DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vice_county_region ON gamification_vice_county_coverage(region);

-- ============================================================================
-- Regional Completion (Crowns)
-- ============================================================================
CREATE TABLE IF NOT EXISTS gamification_regional_completion (
    region_id INTEGER PRIMARY KEY AUTOINCREMENT,
    region TEXT NOT NULL UNIQUE,
    total_vice_counties INTEGER NOT NULL,
    counties_recorded INTEGER NOT NULL DEFAULT 0,
    completion_percentage REAL DEFAULT 0.0,
    trophy_earned BOOLEAN DEFAULT 0,
    date_earned DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_regional_completion_earned ON gamification_regional_completion(trophy_earned);

-- ============================================================================
-- Family First (Ribbons)
-- ============================================================================
CREATE TABLE IF NOT EXISTS gamification_family_first (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_name TEXT NOT NULL UNIQUE,
    order_name TEXT,
    taxonomic_group TEXT,
    date_earned DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    first_species_tvk TEXT,
    first_species_name TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_family_first_name ON gamification_family_first(family_name);
CREATE INDEX IF NOT EXISTS idx_family_first_group ON gamification_family_first(taxonomic_group);

-- ============================================================================
-- Family Depth (Medals)
-- ============================================================================
CREATE TABLE IF NOT EXISTS gamification_family_depth (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_name TEXT NOT NULL,
    trophy_tier TEXT NOT NULL CHECK(trophy_tier IN ('bronze', 'silver', 'gold', 'platinum')),
    species_count INTEGER NOT NULL,
    family_total INTEGER NOT NULL,
    date_earned DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(family_name, trophy_tier)
);

CREATE INDEX IF NOT EXISTS idx_family_depth_name ON gamification_family_depth(family_name);
CREATE INDEX IF NOT EXISTS idx_family_depth_tier ON gamification_family_depth(trophy_tier);

-- ============================================================================
-- Rare Species (Pins) - Future use when rarity data available
-- ============================================================================
CREATE TABLE IF NOT EXISTS gamification_rare_species (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    species_tvk TEXT NOT NULL UNIQUE,
    species_name TEXT NOT NULL,
    rarity_tier TEXT NOT NULL,
    designation TEXT,
    date_earned DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rare_species_tier ON gamification_rare_species(rarity_tier);

-- ============================================================================
-- Rare Species Milestones (Rosettes) - Future use
-- ============================================================================
CREATE TABLE IF NOT EXISTS gamification_rare_milestones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    milestone_name TEXT NOT NULL,
    rarity_tier TEXT,  -- NULL for general milestones
    trophy_tier TEXT NOT NULL,
    threshold INTEGER NOT NULL,
    current_count INTEGER NOT NULL DEFAULT 0,
    date_earned DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(milestone_name, rarity_tier)
);

CREATE INDEX IF NOT EXISTS idx_rare_milestones_earned ON gamification_rare_milestones(date_earned);

-- ============================================================================
-- One-Time Achievements (Daily/Annual Records)
-- ============================================================================
CREATE TABLE IF NOT EXISTS gamification_one_time_achievements (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    threshold INTEGER NOT NULL,
    period TEXT NOT NULL CHECK(period IN ('daily', 'annual')),
    taxonomic_group TEXT NOT NULL,
    date_earned DATETIME,
    record_value INTEGER,
    record_date TEXT,
    best_value INTEGER DEFAULT 0,
    best_date TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_one_time_group ON gamification_one_time_achievements(taxonomic_group);
CREATE INDEX IF NOT EXISTS idx_one_time_period ON gamification_one_time_achievements(period);
CREATE INDEX IF NOT EXISTS idx_one_time_earned ON gamification_one_time_achievements(date_earned);

-- ============================================================================
-- Trophies (Legacy - kept for compatibility)
-- ============================================================================
CREATE TABLE IF NOT EXISTS gamification_trophies (
    trophy_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trophy_type TEXT NOT NULL,
    trophy_name TEXT NOT NULL,
    trophy_description TEXT,
    species_count INTEGER NOT NULL,
    observation_count INTEGER NOT NULL,
    context_data TEXT,
    date_earned DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(trophy_type, trophy_name)
);

CREATE INDEX IF NOT EXISTS idx_gamification_trophies_type ON gamification_trophies(trophy_type);
CREATE INDEX IF NOT EXISTS idx_gamification_trophies_date ON gamification_trophies(date_earned DESC);

-- ============================================================================
-- Notifications
-- ============================================================================
CREATE TABLE IF NOT EXISTS gamification_notifications (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    achievement_type TEXT NOT NULL,
    achievement_id TEXT NOT NULL,
    achievement_name TEXT NOT NULL,
    achievement_icon TEXT,
    is_read BOOLEAN DEFAULT 0,
    read_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(achievement_type, achievement_id)
);

CREATE INDEX IF NOT EXISTS idx_notifications_read ON gamification_notifications(is_read);
CREATE INDEX IF NOT EXISTS idx_notifications_created ON gamification_notifications(created_at DESC);

-- ============================================================================
-- Settings
-- ============================================================================
CREATE TABLE IF NOT EXISTS gamification_settings (
    setting_id INTEGER PRIMARY KEY DEFAULT 1,
    gamification_enabled BOOLEAN DEFAULT 1,
    show_notifications BOOLEAN DEFAULT 1,
    notification_sound BOOLEAN DEFAULT 0,
    last_calculation_run DATETIME,
    auto_calculate BOOLEAN DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def ensure_gamification_db() -> bool:
    """
    Ensure the gamification database exists and is initialized.
    
    Returns True if database is ready, False if there was an error.
    """
    db_path = get_gamification_db_path()
    
    # Check if database already exists and has tables
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM gamification_vice_county_coverage")
            count = cursor.fetchone()[0]
            conn.close()
            
            if count > 0:
                # Database exists and is populated
                return True
        except Exception:
            # Database exists but might be corrupted, recreate it
            pass
    
    # Create or recreate database
    return create_gamification_db(db_path)


def create_gamification_db(db_path: Optional[Path] = None) -> bool:
    """
    Create the gamification database with all required tables.
    
    Args:
        db_path: Path to create the database. If None, uses default location.
        
    Returns:
        True if successful, False otherwise.
    """
    if db_path is None:
        db_path = get_gamification_db_path()
    
    # Ensure data directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Create tables
        cursor.executescript(SCHEMA_SQL)
        
        # Initialize settings
        cursor.execute("""
            INSERT OR IGNORE INTO gamification_settings
            (setting_id, gamification_enabled, show_notifications, notification_sound, auto_calculate)
            VALUES (1, 1, 1, 0, 1)
        """)
        
        # Initialize vice county coverage
        for vc_number, vc_name, region in VICE_COUNTIES:
            cursor.execute("""
                INSERT OR IGNORE INTO gamification_vice_county_coverage
                (vc_number, vice_county_name, region)
                VALUES (?, ?, ?)
            """, (vc_number, vc_name, region))
        
        # Initialize regional completion
        england_count = sum(1 for vc in VICE_COUNTIES if vc[2] == "England")
        scotland_count = sum(1 for vc in VICE_COUNTIES if vc[2] == "Scotland")
        wales_count = sum(1 for vc in VICE_COUNTIES if vc[2] == "Wales")
        total_count = len(VICE_COUNTIES)
        
        regions = [
            ("England", england_count),
            ("Scotland", scotland_count),
            ("Wales", wales_count),
            ("UK", total_count),
        ]
        
        for region_name, total_vcs in regions:
            cursor.execute("""
                INSERT OR IGNORE INTO gamification_regional_completion
                (region, total_vice_counties)
                VALUES (?, ?)
            """, (region_name, total_vcs))
        
        # Initialize one-time achievements
        from .theme import ONE_TIME_ACHIEVEMENTS
        for achievement in ONE_TIME_ACHIEVEMENTS:
            cursor.execute("""
                INSERT OR IGNORE INTO gamification_one_time_achievements
                (id, name, threshold, period, taxonomic_group)
                VALUES (?, ?, ?, ?, ?)
            """, (
                achievement["id"],
                achievement["name"],
                achievement["threshold"],
                achievement["period"],
                achievement["group"]
            ))
        
        conn.commit()
        conn.close()
        
        print(f"[Gamification] Database created: {db_path}")
        print(f"[Gamification] Vice counties initialized: {len(VICE_COUNTIES)}")
        print(f"[Gamification] One-time achievements initialized: {len(ONE_TIME_ACHIEVEMENTS)}")
        return True
        
    except Exception as e:
        print(f"[Gamification] Error creating database: {e}")
        import traceback
        traceback.print_exc()
        return False


def reset_gamification_db() -> bool:
    """
    Delete and recreate the gamification database.
    Use this when schema changes require a fresh start.
    
    Returns True if successful.
    """
    db_path = get_gamification_db_path()
    
    try:
        if db_path.exists():
            db_path.unlink()
            print(f"[Gamification] Deleted existing database: {db_path}")
        
        return create_gamification_db(db_path)
    except Exception as e:
        print(f"[Gamification] Error resetting database: {e}")
        return False
