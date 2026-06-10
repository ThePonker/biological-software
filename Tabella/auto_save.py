"""
Field Entry App - Auto-Save and Recovery.

Periodically saves data to a recovery file and can restore on startup.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Callable

from PySide6.QtCore import QTimer, QObject, Signal


class AutoSave(QObject):
    """
    Auto-save manager that periodically saves table data to a recovery file.
    
    Features:
    - Configurable save interval
    - Recovery file detection on startup
    - Automatic cleanup after successful export
    """
    
    save_triggered = Signal()
    recovery_available = Signal(str)  # path to recovery file
    
    def __init__(self, data_dir: Path, interval_seconds: int = 60, parent=None):
        super().__init__(parent)
        
        self._data_dir = data_dir
        self._interval = interval_seconds * 1000  # Convert to ms
        self._recovery_path = data_dir / 'field_entry_recovery.json'
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer)
        self._get_data_callback: Optional[Callable] = None
        self._dirty = False
    
    def set_data_callback(self, callback: Callable[[], List[List[str]]]):
        """
        Set callback to get current table data.
        
        Args:
            callback: Function that returns list of row data
        """
        self._get_data_callback = callback
    
    def start(self):
        """Start auto-save timer."""
        if self._interval > 0:
            self._timer.start(self._interval)
    
    def stop(self):
        """Stop auto-save timer."""
        self._timer.stop()
    
    def set_interval(self, seconds: int):
        """Set auto-save interval in seconds."""
        self._interval = seconds * 1000
        if self._timer.isActive():
            self._timer.stop()
            self._timer.start(self._interval)
    
    def mark_dirty(self):
        """Mark data as changed (needs saving)."""
        self._dirty = True
    
    def mark_clean(self):
        """Mark data as saved (no changes)."""
        self._dirty = False
    
    def check_for_recovery(self) -> Optional[str]:
        """
        Check if a recovery file exists.
        
        Returns:
            Path to recovery file if exists, None otherwise
        """
        if self._recovery_path.exists():
            try:
                with open(self._recovery_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    timestamp = data.get('timestamp', 'Unknown time')
                    row_count = len(data.get('rows', []))
                    return f"Recovery file found from {timestamp} ({row_count} rows)"
            except Exception:
                pass
        return None
    
    def load_recovery(self) -> Optional[List[List[str]]]:
        """
        Load data from recovery file.
        
        Returns:
            List of row data, or None if no recovery file
        """
        if not self._recovery_path.exists():
            return None
        
        try:
            with open(self._recovery_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('rows', [])
        except Exception as e:
            print(f"[AutoSave] Error loading recovery: {e}")
            return None
    
    def clear_recovery(self):
        """Delete the recovery file."""
        try:
            if self._recovery_path.exists():
                self._recovery_path.unlink()
        except Exception as e:
            print(f"[AutoSave] Error clearing recovery: {e}")
    
    def save_now(self) -> bool:
        """
        Immediately save current data to recovery file.
        
        Returns:
            True if saved successfully
        """
        if not self._get_data_callback:
            return False
        
        try:
            rows = self._get_data_callback()
            
            # Only save if there's actual data
            data_rows = [r for r in rows if r and r[0].strip()]
            if not data_rows:
                return False
            
            data = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'rows': rows
            }
            
            self._data_dir.mkdir(parents=True, exist_ok=True)
            
            with open(self._recovery_path, 'w', encoding='utf-8') as f:
                json.dump(data, f)
            
            self._dirty = False
            self.save_triggered.emit()
            return True
            
        except Exception as e:
            print(f"[AutoSave] Error saving: {e}")
            return False
    
    def _on_timer(self):
        """Handle timer tick - save if dirty."""
        if self._dirty:
            self.save_now()
