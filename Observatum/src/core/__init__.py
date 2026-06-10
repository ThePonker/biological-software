# Observatum V2 - Core Package
# Application-wide configuration and utilities

from .config import (
    AppConfig,
    Settings,
    Defaults,
    Paths,
    TabColors,
    get_setting,
    set_setting,
    get_db_path,
)

__all__ = [
    'AppConfig',
    'Settings',
    'Defaults',
    'Paths',
    'TabColors',
    'get_setting',
    'set_setting',
    'get_db_path',
]
