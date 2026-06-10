"""
Field Entry App - Undo/Redo Manager.

Tracks changes to table data for undo/redo functionality.
"""

from dataclasses import dataclass
from typing import List, Optional, Any
from enum import Enum


class ActionType(Enum):
    """Types of undoable actions."""
    CELL_EDIT = "cell_edit"
    ROW_INSERT = "row_insert"
    ROW_DELETE = "row_delete"
    ROW_DUPLICATE = "row_duplicate"
    MULTI_CELL_EDIT = "multi_cell_edit"
    PASTE = "paste"
    FILL_DOWN = "fill_down"
    CLEAR = "clear"


@dataclass
class CellChange:
    """Represents a single cell change."""
    row: int
    col: int
    old_value: str
    new_value: str


@dataclass
class RowData:
    """Represents a complete row of data."""
    row: int
    values: List[str]


@dataclass
class UndoAction:
    """Represents an undoable action."""
    action_type: ActionType
    description: str
    
    # For cell edits
    cell_changes: Optional[List[CellChange]] = None
    
    # For row operations
    row_data: Optional[List[RowData]] = None
    
    # For row insert - where the row was inserted
    insert_row: Optional[int] = None


class UndoManager:
    """
    Manages undo/redo stacks for table operations.
    
    Usage:
        manager = UndoManager()
        
        # Before making changes
        manager.begin_action(ActionType.CELL_EDIT, "Edit cell")
        manager.record_cell_change(row, col, old_val, new_val)
        manager.end_action()
        
        # To undo
        action = manager.undo()
        if action:
            # Apply inverse of action
            
        # To redo
        action = manager.redo()
        if action:
            # Reapply action
    """
    
    MAX_UNDO_STACK = 100
    
    def __init__(self):
        self._undo_stack: List[UndoAction] = []
        self._redo_stack: List[UndoAction] = []
        self._current_action: Optional[UndoAction] = None
        self._batch_mode = False
    
    def begin_action(self, action_type: ActionType, description: str):
        """
        Begin recording a new action.
        
        Args:
            action_type: Type of action
            description: Human-readable description
        """
        self._current_action = UndoAction(
            action_type=action_type,
            description=description,
            cell_changes=[],
            row_data=[],
        )
    
    def record_cell_change(self, row: int, col: int, old_value: str, new_value: str):
        """Record a cell value change."""
        if self._current_action and self._current_action.cell_changes is not None:
            self._current_action.cell_changes.append(
                CellChange(row, col, old_value, new_value)
            )
    
    def record_row_data(self, row: int, values: List[str]):
        """Record a complete row of data (for delete/insert operations)."""
        if self._current_action and self._current_action.row_data is not None:
            self._current_action.row_data.append(RowData(row, values))
    
    def set_insert_row(self, row: int):
        """Set the row index for an insert operation."""
        if self._current_action:
            self._current_action.insert_row = row
    
    def end_action(self):
        """
        Finish recording the current action and add to undo stack.
        """
        if self._current_action:
            # Only add if there were actual changes
            has_changes = (
                (self._current_action.cell_changes and len(self._current_action.cell_changes) > 0) or
                (self._current_action.row_data and len(self._current_action.row_data) > 0) or
                self._current_action.insert_row is not None
            )
            
            if has_changes:
                self._undo_stack.append(self._current_action)
                
                # Trim stack if too large
                if len(self._undo_stack) > self.MAX_UNDO_STACK:
                    self._undo_stack.pop(0)
                
                # Clear redo stack when new action is recorded
                self._redo_stack.clear()
            
            self._current_action = None
    
    def cancel_action(self):
        """Cancel the current action without adding to stack."""
        self._current_action = None
    
    def undo(self) -> Optional[UndoAction]:
        """
        Pop and return the last action from undo stack.
        
        Returns:
            The action to undo, or None if stack is empty
        """
        if not self._undo_stack:
            return None
        
        action = self._undo_stack.pop()
        self._redo_stack.append(action)
        return action
    
    def redo(self) -> Optional[UndoAction]:
        """
        Pop and return the last action from redo stack.
        
        Returns:
            The action to redo, or None if stack is empty
        """
        if not self._redo_stack:
            return None
        
        action = self._redo_stack.pop()
        self._undo_stack.append(action)
        return action
    
    def can_undo(self) -> bool:
        """Check if undo is available."""
        return len(self._undo_stack) > 0
    
    def can_redo(self) -> bool:
        """Check if redo is available."""
        return len(self._redo_stack) > 0
    
    def get_undo_description(self) -> Optional[str]:
        """Get description of the action that would be undone."""
        if self._undo_stack:
            return self._undo_stack[-1].description
        return None
    
    def get_redo_description(self) -> Optional[str]:
        """Get description of the action that would be redone."""
        if self._redo_stack:
            return self._redo_stack[-1].description
        return None
    
    def clear(self):
        """Clear all undo/redo history."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._current_action = None
