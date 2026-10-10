"""
Saved Filters Service.

Manages persistence of user-saved filter configurations.
Stores filters in a JSON file in the data directory.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import paths


class SavedFiltersService:
    """
    Service for saving and loading filter configurations.
    
    Filters are stored in data/saved_filters.json with structure:
    {
        "filters": {
            "<tab>/<name>": {
                "name": "filter_name",
                "created": "2025-01-09T12:00:00",
                "tab": "observations",
                "config": {...filter dict...}
            }
        }
    }

    10 Oct 2026 (review SRCH11): names are per tab. They used to be one list keyed by
    name, so "Wood" saved on Recording Scheme replaced "Wood" on Observation Data.
    Files written the old way (keyed by name alone) are read as before.
    """
    
    def __init__(self, filters_file=None):
        self._filters_file = Path(filters_file) if filters_file else self._get_filters_path()
        self._filters: Dict[str, Dict] = {}
        self._load_filters()
    
    def _get_filters_path(self) -> Path:
        """Get path to saved filters file."""
        # Try to use the app's data directory
        try:
            data_dir = Path(paths.DATA_DIR)
        except Exception:
            data_dir = Path("data")
        
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "saved_filters.json"

    @staticmethod
    def _key(name: str, tab: Optional[str]) -> str:
        return f"{tab or 'observations'}/{name}"
    
    def _load_filters(self):
        """Load filters from file (old files keyed by name alone are re-keyed by tab)."""
        self._filters = {}
        if not self._filters_file.exists():
            return
        try:
            with open(self._filters_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for key, entry in (data.get('filters', {}) or {}).items():
                if not isinstance(entry, dict):
                    continue
                name = entry.get('name') or key
                entry = dict(entry, name=name, tab=entry.get('tab') or 'observations')
                self._filters[self._key(name, entry['tab'])] = entry
            print(f"[SavedFilters] Loaded {len(self._filters)} saved filters")
        except Exception as e:
            print(f"[SavedFilters] Error loading filters: {e}")
            self._filters = {}
    
    def _save_filters(self):
        """Save filters to file."""
        try:
            data = {'filters': self._filters}
            with open(self._filters_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"[SavedFilters] Saved {len(self._filters)} filters")
        except Exception as e:
            print(f"[SavedFilters] Error saving filters: {e}")
    
    def save_filter(self, name: str, config: Dict[str, Any], tab: str = "observations") -> bool:
        """Save (or replace) the tab's filter of this name."""
        if not name or not name.strip():
            return False
        name = name.strip()
        self._filters[self._key(name, tab)] = {
            'name': name,
            'created': datetime.now().isoformat(),
            'tab': tab,
            'config': config
        }
        self._save_filters()
        return True
    
    def get_filter(self, name: str, tab: str = "observations") -> Optional[Dict[str, Any]]:
        """The tab's saved filter config, or None."""
        filter_data = self._filters.get(self._key(name, tab))
        if filter_data:
            return filter_data.get('config', {})
        return None
    
    def get_all_filters(self, tab: Optional[str] = None) -> Dict[str, Dict]:
        """{name: entry} for one tab, or {"tab/name": entry} for all."""
        if tab:
            return {data['name']: data for data in self._filters.values() if data.get('tab') == tab}
        return self._filters.copy()
    
    def get_filter_names(self, tab: Optional[str] = None) -> List[str]:
        """Names of the saved filters (of one tab, if given)."""
        return [data['name'] for data in self._filters.values()
                if tab is None or data.get('tab') == tab]
    
    def delete_filter(self, name: str, tab: str = "observations") -> bool:
        """Delete the tab's saved filter of this name. True if it existed."""
        key = self._key(name, tab)
        if key in self._filters:
            del self._filters[key]
            self._save_filters()
            return True
        return False
    
    def rename_filter(self, old_name: str, new_name: str, tab: str = "observations") -> bool:
        """Rename one of the tab's saved filters (not over an existing one)."""
        old, new = self._key(old_name, tab), self._key(new_name, tab)
        if old in self._filters and new not in self._filters:
            self._filters[new] = dict(self._filters.pop(old), name=new_name)
            self._save_filters()
            return True
        return False


_service: Optional[SavedFiltersService] = None


# Singleton accessor
def get_saved_filters_service() -> SavedFiltersService:
    """Get the saved filters service singleton."""
    global _service
    if _service is None:
        _service = SavedFiltersService()
    return _service
