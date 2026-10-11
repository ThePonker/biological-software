# Observatum V2 - Views Package
# All UI views and tabs

# MainWindow is imported on first use (PEP 562), not when the package loads: importing
# src.views.splash_screen used to pull in the whole main window and every tab (about
# 2 s, pandas included) before the splash screen could appear (startup speed, 11 Oct 2026).

__all__ = [
    'MainWindow',
]


def __getattr__(name):
    if name == 'MainWindow':
        from .main_window import MainWindow
        return MainWindow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
