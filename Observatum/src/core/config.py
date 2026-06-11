"""
Observatum V2 - Centralised Configuration

All application settings, paths, and constants in one place.
No more scattered hardcoded values or magic strings.

Usage:
    from src.core.config import AppConfig, Settings, Paths, TabColors
    
    # App info
    print(AppConfig.NAME)  # "Observatum"
    print(AppConfig.VERSION)  # "2.0.0"
    
    # Settings keys (for QSettings)
    settings = QSettings()
    path = settings.value(Settings.DB_MAIN_PATH, Paths.default_main_db())
    
    # Tab colors
    color = TabColors.OBSERVATION
    variants = TabColors.get_variants('observation')  # Returns dict with accent, light, dark
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict
import sys
import paths


# =============================================================================
# APP METADATA
# =============================================================================
print("✓ Config module loaded from src.core.config")

class AppConfig:
    """Application metadata and identity."""
    
    NAME = "Observatum"
    DISPLAY_NAME = "Observatum V2"
    ORGANIZATION = "Observatum"
    VERSION = "2.0.0"
    
    # For QCoreApplication setup
    @classmethod
    def setup_app_info(cls, app):
        """Configure QApplication with app metadata."""
        from PySide6.QtCore import QCoreApplication, QSettings
        
        QCoreApplication.setOrganizationName(cls.ORGANIZATION)
        QCoreApplication.setApplicationName(cls.NAME)
        QCoreApplication.setApplicationVersion(cls.VERSION)
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)


# =============================================================================
# SETTINGS KEYS (for QSettings)
# =============================================================================

class Settings:
    """
    QSettings key constants.
    
    Using these instead of string literals prevents typos and enables IDE autocomplete.
    All keys are organized by category.
    """
    
    # --- Database Paths ---
    DB_MAIN_PATH = "databases/main_path"
    DB_UKSI_PATH = "databases/uksi_path"
    DB_VC_PATH = "databases/vc_path"
    
    # --- General Settings ---
    DEFAULT_RECORDER = "general/default_recorder"
    DEFAULT_DETERMINER = "general/default_determiner"
    USER_INITIALS = "general/user_initials"
    DATE_FORMAT = "general/date_format"
    GRID_REF_FORMAT = "general/grid_ref_format"
    FONT_SIZE = "general/font_size"
    AUTO_CALCULATE_VC = "general/auto_calculate_vc"
    
    # --- Display Settings ---
    THEME = "display/theme"
    COMMON_NAMES_HOME = "display/common_names_home"
    COMMON_NAMES_OBSERVATIONS = "display/common_names_observations"
    COMMON_NAMES_RECORDING_SCHEME = "display/common_names_recording_scheme"
    COMMON_NAMES_INSECT_COLLECTION = "display/common_names_insect_collection"
    
    # --- Recording Scheme ---
    SCHEME_FAMILIES = "scheme/families"  # Comma-separated family names, e.g. "Cerambycidae"

    # --- Species Filtering ---
    EXCLUDE_INCOMPLETE_SPECIES = "display/exclude_incomplete_species"

    # --- Filter Bar Defaults ---
    FILTERS_VISIBLE_OBSERVATIONS = "display/filters_visible_observations"
    FILTERS_VISIBLE_RECORDING_SCHEME = "display/filters_visible_recording_scheme"
    FILTERS_VISIBLE_COLLECTION = "display/filters_visible_collection"
    CSV_BACKUP_ON_CLOSE = "general/csv_backup_on_close"
    CSV_BACKUP_PATH = "general/csv_backup_path"
    ACTIVE_RECORD_BOOKS_PATH = "general/active_record_books_path"

    # --- Export Settings ---
    EXPORT_INCLUDE_COMMON_NAMES = "export/include_common_names"
    EXPORT_INCLUDE_TVK = "export/include_tvk"
    EXPORT_EXCLUDE_NO_GRID = "export/exclude_no_grid"
    EXPORT_DEFAULT_PATH = "export/default_path"
    
    # --- Collection Settings ---
    COLLECTION_NOTIFICATIONS_ENABLED = "collection/notifications_enabled"
    COLLECTION_COLEOPTERA_ENABLED = "collection/coleoptera_enabled"
    COLLECTION_DIPTERA_ENABLED = "collection/diptera_enabled"
    COLLECTION_HYMENOPTERA_ENABLED = "collection/hymenoptera_enabled"
    COLLECTION_HEMIPTERA_ENABLED = "collection/hemiptera_enabled"
    COLLECTION_LEPIDOPTERA_ENABLED = "collection/lepidoptera_enabled"
    
    # --- Sync Settings ---
    SYNC_METHOD = "sync/method"
    SYNC_LAST_SYNC = "sync/last_sync"
    SYNC_AUTO_ACCEPT = "sync/auto_accept"
    SYNC_PROMPT_OVERWRITE = "sync/prompt_overwrite"
    
    # --- Window State ---
    WINDOW_GEOMETRY = "window/geometry"
    WINDOW_STATE = "window/state"
    LAST_TAB = "window/last_tab"


# =============================================================================
# DEFAULT VALUES
# =============================================================================

class Defaults:
    """Default values for settings."""
    
    # General
    RECORDER = ""
    DETERMINER = ""
    USER_INITIALS = ""
    DATE_FORMAT = "DD/MM/YYYY"
    GRID_REF_FORMAT = "DINTY"
    FONT_SIZE = "Medium"
    AUTO_CALCULATE_VC = True
    
    # Display
    THEME = "Light"
    SHOW_COMMON_NAMES = True
    EXCLUDE_INCOMPLETE_SPECIES = True  # Exclude genus-only and aggregates from stats
    FILTERS_VISIBLE_OBSERVATIONS = True
    FILTERS_VISIBLE_RECORDING_SCHEME = True
    FILTERS_VISIBLE_COLLECTION = True
    
    # Export
    INCLUDE_COMMON_NAMES = True
    INCLUDE_TVK = True
    EXCLUDE_NO_GRID = False
    
    # Collection
    NOTIFICATIONS_ENABLED = True
    
    # Sync
    SYNC_METHOD = "Manual (CSV download)"
    AUTO_ACCEPT_CHANGES = True
    PROMPT_OVERWRITE = False


# =============================================================================
# FILE PATHS
# =============================================================================

class Paths:
    """
    File path utilities.
    
    Handles finding the project root and constructing default paths
    regardless of how/where the app is launched.
    """
    
    # Database filenames
    MAIN_DB_FILENAME = "Observatum.db"
    UKSI_DB_FILENAME = "uksi.db"
    VC_DB_FILENAME = "vc_lookup.db"
    
    _project_root: Optional[Path] = None
    
    @classmethod
    def project_root(cls) -> Path:
        """
        Get the project root directory.
        
        Works whether running from source or as frozen executable.
        """
        if cls._project_root is not None:
            return cls._project_root
        
        # Check if running as frozen executable (PyInstaller)
        if getattr(sys, 'frozen', False):
            cls._project_root = Path(sys.executable).parent
        else:
            # Running from source - find project root
            # This file is at src/core/config.py, so go up 3 levels
            cls._project_root = paths.OBSERVATUM_DIR
        
        return cls._project_root
    
    @classmethod
    def data_dir(cls) -> Path:
        """Get the data directory."""
        return cls.project_root() / "data"
    
    @classmethod
    def default_main_db(cls) -> str:
        """Get default path to main database."""
        return str(paths.DATA_DIR / cls.MAIN_DB_FILENAME)
    
    @classmethod
    def default_uksi_db(cls) -> str:
        """Get default path to UKSI database."""
        return str(paths.DATA_DIR / cls.UKSI_DB_FILENAME)
    
    @classmethod
    def default_vc_db(cls) -> str:
        """Get default path to VC lookup database."""
        return str(paths.DATA_DIR / cls.VC_DB_FILENAME)
    
    @classmethod
    def find_database(cls, filename: str) -> Optional[Path]:
        """
        Search for a database file in standard locations.
        
        Returns the path if found, None otherwise.
        """
        candidates = [
            paths.DATA_DIR / filename,
            cls.project_root() / filename,
            Path.cwd() / "data" / filename,
            Path.cwd() / filename,
            paths.DATA_DIR / filename,
            Path.home() / "Documents" / "Observatum_V2" / "data" / filename,
        ]
        
        for path in candidates:
            if path.exists():
                return path
        
        return None


# =============================================================================
# TAB COLORS (Naturalist Palette)
# =============================================================================

class TabColors:
    """
    Tab accent colors for the Naturalist theme.
    
    Each data tab has a distinct color for visual identification.
    Each tab has three variants:
    - accent: Main tab color (headers, active states, navigation buttons)
    - accent_light: Light tint (header backgrounds, hover states)
    - accent_dark: Dark shade (text on light backgrounds)
    
    Usage:
        # Single color
        color = TabColors.OBSERVATION
        
        # All variants
        variants = TabColors.get_variants('observation')
        # Returns: {'accent': '#5f8575', 'accent_light': '#e8f0ec', 'accent_dark': '#4a6b5c'}
    """
    
    # -------------------------------------------------------------------------
    # Home / Settings - Warm Gray
    # -------------------------------------------------------------------------
    HOME = "#8b8178"
    HOME_LIGHT = "#f5f4f3"
    HOME_DARK = "#6b635b"
    
    SETTINGS = "#8b8178"
    SETTINGS_LIGHT = "#f5f4f3"
    SETTINGS_DARK = "#6b635b"
    
    # -------------------------------------------------------------------------
    # Observation Data - Sage Green
    # -------------------------------------------------------------------------
    OBSERVATION = "#5f8575"
    OBSERVATION_LIGHT = "#e8f0ec"
    OBSERVATION_DARK = "#4a6b5c"
    
    # -------------------------------------------------------------------------
    # Recording Scheme - Dusty Purple
    # -------------------------------------------------------------------------
    RECORDING_SCHEME = "#7c6c9f"
    RECORDING_SCHEME_LIGHT = "#eeeaf3"
    RECORDING_SCHEME_DARK = "#5c4f7a"
    
    # -------------------------------------------------------------------------
    # Insect Collection - Warm Gold
    # -------------------------------------------------------------------------
    COLLECTION = "#b8860b"
    COLLECTION_LIGHT = "#faf6eb"
    COLLECTION_DARK = "#8a6508"
    
    # -------------------------------------------------------------------------
    # Stats & Reports - Steel Blue
    # -------------------------------------------------------------------------
    STATS = "#5c6b7a"
    STATS_LIGHT = "#eaecef"
    STATS_DARK = "#454f5c"
    
    # -------------------------------------------------------------------------
    # Mapping - Terracotta
    # -------------------------------------------------------------------------
    MAPPING = "#c2956e"
    MAPPING_LIGHT = "#f7f2ed"
    MAPPING_DARK = "#9a7555"
    # -------------------------------------------------------------------------
    # Personal Stats - Emerald Green
    # -------------------------------------------------------------------------
    PERSONAL = "#10b981"
    PERSONAL_LIGHT = "#d1fae5"
    PERSONAL_DARK = "#065f46"

    # -------------------------------------------------------------------------
    # Commercial Reports - Violet
    # -------------------------------------------------------------------------
    COMMERCIAL = "#8b5cf6"
    COMMERCIAL_LIGHT = "#ede9fe"
    COMMERCIAL_DARK = "#5b21b6"

    # -------------------------------------------------------------------------
    # Species Dashboard - Blue
    # -------------------------------------------------------------------------
    SPECIES = "#3b82f6"
    SPECIES_LIGHT = "#dbeafe"
    SPECIES_DARK = "#1e40af"

    
    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------
    
    @classmethod
    def get_variants(cls, tab_name: str) -> Dict[str, str]:
        """
        Get all color variants for a tab.
        
        Args:
            tab_name: Tab identifier (e.g., 'observation', 'collection', 'mapping')
        
        Returns:
            Dict with 'accent', 'accent_light', 'accent_dark' keys
        
        Example:
            variants = TabColors.get_variants('observation')
            header_bg = variants['accent_light']
            header_text = variants['accent_dark']
            header_border = variants['accent']
        """
        variants_map = {
            'home': (cls.HOME, cls.HOME_LIGHT, cls.HOME_DARK),
            'settings': (cls.SETTINGS, cls.SETTINGS_LIGHT, cls.SETTINGS_DARK),
            'observation': (cls.OBSERVATION, cls.OBSERVATION_LIGHT, cls.OBSERVATION_DARK),
            'observations': (cls.OBSERVATION, cls.OBSERVATION_LIGHT, cls.OBSERVATION_DARK),
            'recording_scheme': (cls.RECORDING_SCHEME, cls.RECORDING_SCHEME_LIGHT, cls.RECORDING_SCHEME_DARK),
            'scheme': (cls.RECORDING_SCHEME, cls.RECORDING_SCHEME_LIGHT, cls.RECORDING_SCHEME_DARK),
            'collection': (cls.COLLECTION, cls.COLLECTION_LIGHT, cls.COLLECTION_DARK),
            'insect_collection': (cls.COLLECTION, cls.COLLECTION_LIGHT, cls.COLLECTION_DARK),
            'stats': (cls.STATS, cls.STATS_LIGHT, cls.STATS_DARK),
            'reports': (cls.STATS, cls.STATS_LIGHT, cls.STATS_DARK),
            'mapping': (cls.MAPPING, cls.MAPPING_LIGHT, cls.MAPPING_DARK),
            'personal': (cls.PERSONAL, cls.PERSONAL_LIGHT, cls.PERSONAL_DARK),
            'commercial': (cls.COMMERCIAL, cls.COMMERCIAL_LIGHT, cls.COMMERCIAL_DARK),
            'species': (cls.SPECIES, cls.SPECIES_LIGHT, cls.SPECIES_DARK),
            'map': (cls.MAPPING, cls.MAPPING_LIGHT, cls.MAPPING_DARK),
        }
        
        accent, light, dark = variants_map.get(
            tab_name.lower(), 
            (cls.HOME, cls.HOME_LIGHT, cls.HOME_DARK)
        )
        
        return {
            'accent': accent,
            'accent_light': light,
            'accent_dark': dark,
        }
    
    @classmethod
    def get_tab_color(cls, tab_name: str) -> str:
        """Get the main accent color for a tab by name."""
        return cls.get_variants(tab_name)['accent']


# =============================================================================
# BUTTON COLORS (Global - Not Tab-Specific)
# =============================================================================

class ButtonColors:
    """
    Standard button colors used throughout the application.
    
    These are consistent across all tabs:
    - PRIMARY: Save, Add, Create actions (Moss Green)
    - SECONDARY: Cancel, Close actions (Warm Gray, outlined)
    - DANGER: Delete actions (Faded Crimson, outlined)
    
    Navigation/View buttons use the tab's accent color instead.
    """
    
    # Primary actions (Save, Add, Create) - Moss Green
    PRIMARY = "#4a7c59"
    PRIMARY_HOVER = "#3d6649"
    PRIMARY_PRESSED = "#2f5a3b"
    PRIMARY_TEXT = "#ffffff"
    
    # Secondary actions (Cancel, Close) - Warm Gray (outlined style)
    SECONDARY = "#8b8178"
    SECONDARY_HOVER = "#6b635b"
    SECONDARY_TEXT = "#8b8178"
    
    # Danger actions (Delete) - Faded Crimson (outlined style)
    DANGER = "#a63d40"
    DANGER_HOVER = "#8b3033"
    DANGER_TEXT = "#a63d40"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_setting(key: str, default=None, value_type=None):
    """
    Get a setting value from QSettings.
    
    Args:
        key: Settings key (use Settings.* constants)
        default: Default value if not set
        value_type: Type to convert to (bool, int, str, etc.)
    
    Example:
        recorder = get_setting(Settings.DEFAULT_RECORDER, "")
        auto_vc = get_setting(Settings.AUTO_CALCULATE_VC, True, bool)
    """
    from PySide6.QtCore import QSettings
    
    settings = QSettings()
    
    if value_type is not None:
        return settings.value(key, default, type=value_type)
    return settings.value(key, default)


def set_setting(key: str, value):
    """
    Set a setting value in QSettings.
    
    Args:
        key: Settings key (use Settings.* constants)
        value: Value to store
    
    Example:
        set_setting(Settings.DEFAULT_RECORDER, "Heeney, W")
    """
    from PySide6.QtCore import QSettings
    
    settings = QSettings()
    settings.setValue(key, value)


def get_db_path(db_type: str = 'main') -> Optional[str]:
    """
    Get a database path, checking QSettings first then falling back to defaults.
    
    Args:
        db_type: 'main', 'uksi', or 'vc'
    
    Returns:
        Path string if database exists, None otherwise.
    """
    from PySide6.QtCore import QSettings
    
    settings = QSettings()
    
    key_map = {
        'main': (Settings.DB_MAIN_PATH, Paths.default_main_db),
        'uksi': (Settings.DB_UKSI_PATH, Paths.default_uksi_db),
        'vc': (Settings.DB_VC_PATH, Paths.default_vc_db),
    }
    
    if db_type not in key_map:
        raise ValueError(f"Unknown db_type: {db_type}. Use 'main', 'uksi', or 'vc'.")
    
    key, default_fn = key_map[db_type]
    
    # Check QSettings first
    path = settings.value(key)
    if path and Path(path).exists():
        return path
    
    # Fall back to default
    default_path = default_fn()
    if Path(default_path).exists():
        return default_path
    
    return None
