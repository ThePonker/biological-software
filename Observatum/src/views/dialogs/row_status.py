"""Status of an import row during validation -- one enum for all three import wizards
(backlog I9, 9 Oct 2026; each validation_worker.py used to define its own copy)."""
from enum import Enum


class RowStatus(Enum):
    PENDING = "pending"
    VALID = "valid"
    WARNING = "warning"
    ERROR = "error"
