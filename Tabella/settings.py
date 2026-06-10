"""
Field Entry App - User Settings.

Persistent settings stored in JSON file.
"""

import json
from pathlib import Path
from typing import Optional, Any, Dict, List


class Settings:
    """
    Manages persistent user settings.
    
    Settings are stored in a JSON file in the user's data directory.
    """
    
    # Default values
    DEFAULTS = {
        'default_recorder': '',
        'default_determiner': '',
        'default_certainty': 'Certain',
        'default_data_type': 'Personal',
        'default_qty': '1',
        'startup_rows': 1000,
        'jump_after_species_match': True,
        'column_order': [],  # Empty = default order
        'hidden_columns': [],  # Column indices to hide
        'auto_save_enabled': True,
        'auto_save_interval': 60,  # seconds
    }
    
    def __init__(self, settings_path: Optional[Path] = None):
        """
        Initialize settings.
        
        Args:
            settings_path: Path to settings file, or None for default location
        """
        if settings_path is None:
            settings_path = self._find_settings_path()
        
        self._path = settings_path
        self._settings: Dict[str, Any] = dict(self.DEFAULTS)
        self._load()
    
    def _find_settings_path(self) -> Path:
        """Find or create settings directory."""
        candidates = [
            Path('data/field_entry_settings.json'),
            Path('../data/field_entry_settings.json'),
            Path.cwd() / 'data' / 'field_entry_settings.json',
        ]
        
        for path in candidates:
            if path.parent.exists():
                return path
        
        return Path('field_entry_settings.json')
    
    def _load(self):
        """Load settings from file."""
        if self._path.exists():
            try:
                with open(self._path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self._settings.update(loaded)
            except Exception as e:
                print(f"[Settings] Error loading settings: {e}")
    
    def _save(self):
        """Save settings to file."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=2)
        except Exception as e:
            print(f"[Settings] Error saving settings: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self._settings.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set a setting value and save."""
        self._settings[key] = value
        self._save()
    
    # Convenience properties
    @property
    def default_recorder(self) -> str:
        return self.get('default_recorder', '')
    
    @default_recorder.setter
    def default_recorder(self, value: str):
        self.set('default_recorder', value)
    
    @property
    def default_determiner(self) -> str:
        return self.get('default_determiner', '')
    
    @default_determiner.setter
    def default_determiner(self, value: str):
        self.set('default_determiner', value)
    
    @property
    def default_certainty(self) -> str:
        return self.get('default_certainty', 'Certain')
    
    @default_certainty.setter
    def default_certainty(self, value: str):
        self.set('default_certainty', value)
    
    @property
    def default_data_type(self) -> str:
        return self.get('default_data_type', 'Personal')
    
    @default_data_type.setter
    def default_data_type(self, value: str):
        self.set('default_data_type', value)
    
    @property
    def startup_rows(self) -> int:
        return self.get('startup_rows', 1000)
    
    @startup_rows.setter
    def startup_rows(self, value: int):
        self.set('startup_rows', value)
    
    @property
    def jump_after_species_match(self) -> bool:
        return self.get('jump_after_species_match', True)
    
    @jump_after_species_match.setter
    def jump_after_species_match(self, value: bool):
        self.set('jump_after_species_match', value)
    
    @property
    def column_order(self) -> List[int]:
        return self.get('column_order', [])
    
    @column_order.setter
    def column_order(self, value: List[int]):
        self.set('column_order', value)
    
    @property
    def hidden_columns(self) -> List[int]:
        return self.get('hidden_columns', [])
    
    @hidden_columns.setter
    def hidden_columns(self, value: List[int]):
        self.set('hidden_columns', value)
    
    @property
    def auto_save_enabled(self) -> bool:
        return self.get('auto_save_enabled', True)
    
    @auto_save_enabled.setter
    def auto_save_enabled(self, value: bool):
        self.set('auto_save_enabled', value)
    
    @property
    def auto_save_interval(self) -> int:
        return self.get('auto_save_interval', 60)
    
    @auto_save_interval.setter
    def auto_save_interval(self, value: int):
        self.set('auto_save_interval', value)
