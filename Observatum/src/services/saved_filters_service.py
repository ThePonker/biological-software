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
            "filter_name": {
                "created": "2025-01-09T12:00:00",
                "tab": "observations",
                "config": {...filter dict...}
            }
        }
    }
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._filters_file = self._get_filters_path()
        self._filters: Dict[str, Dict] = {}
        self._load_filters()
    
    def _get_filters_path(self) -> Path:
        """Get path to saved filters file."""
        # Try to use the app's data directory
        try:
            from ..core.config import Paths
            data_dir = Path(paths.DATA_DIR)
        except:
            data_dir = Path("data")
        
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "saved_filters.json"
    
    def _load_filters(self):
        """Load filters from file."""
        if self._filters_file.exists():
            try:
                with open(self._filters_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._filters = data.get('filters', {})
                print(f"[SavedFilters] Loaded {len(self._filters)} saved filters")
            except Exception as e:
                print(f"[SavedFilters] Error loading filters: {e}")
                self._filters = {}
        else:
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
        """
        Save a filter configuration.
        
        Args:
            name: Unique name for the filter
            config: Filter configuration dict
            tab: Which tab this filter is for
            
        Returns:
            True if saved successfully
        """
        if not name or not name.strip():
            return False
        
        name = name.strip()
        
        self._filters[name] = {
            'created': datetime.now().isoformat(),
            'tab': tab,
            'config': config
        }
        
        self._save_filters()
        return True
    
    def get_filter(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a saved filter by name.
        
        Returns:
            Filter config dict or None if not found
        """
        filter_data = self._filters.get(name)
        if filter_data:
            return filter_data.get('config', {})
        return None
    
    def get_all_filters(self, tab: Optional[str] = None) -> Dict[str, Dict]:
        """
        Get all saved filters, optionally filtered by tab.
        
        Args:
            tab: If provided, only return filters for this tab
            
        Returns:
            Dict of filter_name -> filter_data
        """
        if tab:
            return {
                name: data for name, data in self._filters.items()
                if data.get('tab') == tab
            }
        return self._filters.copy()
    
    def get_filter_names(self, tab: Optional[str] = None) -> List[str]:
        """
        Get list of saved filter names.
        
        Args:
            tab: If provided, only return names for this tab
        """
        if tab:
            return [
                name for name, data in self._filters.items()
                if data.get('tab') == tab
            ]
        return list(self._filters.keys())
    
    def delete_filter(self, name: str) -> bool:
        """
        Delete a saved filter.
        
        Returns:
            True if deleted, False if not found
        """
        if name in self._filters:
            del self._filters[name]
            self._save_filters()
            return True
        return False
    
    def rename_filter(self, old_name: str, new_name: str) -> bool:
        """
        Rename a saved filter.
        
        Returns:
            True if renamed successfully
        """
        if old_name in self._filters and new_name not in self._filters:
            self._filters[new_name] = self._filters.pop(old_name)
            self._save_filters()
            return True
        return False


# Singleton accessor
def get_saved_filters_service() -> SavedFiltersService:
    """Get the saved filters service singleton."""
    return SavedFiltersService()
