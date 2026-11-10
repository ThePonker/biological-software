# PyInstaller spec for the free-standing Lector: a one-folder build of `python -m Lector gui`.
#
#   py -3.14 -m PyInstaller packaging\lector\lector.spec --noconfirm --distpath <dist> --workpath <work>
#
# (build_lector.ps1 does this.) Written without being able to run PyInstaller where it was
# written: the first real build may ask for a hidden import or two (BUILD.md says where to look).
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

HERE = os.path.abspath(SPECPATH)                      # packaging/lector
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))  # the suite (Lector, shared, Observatum...)

# Everything Lector imports from the rest of the suite (found by importing Lector.ui.app,
# Lector.__main__ and the screens): the theme and one widget from Observatum\src, and these
# modules of shared\. Several are imported inside functions, which PyInstaller cannot see,
# so they are listed.
SHARED = ["shared.away_mode", "shared.calendar_style", "shared.crash_log", "shared.db_open",
          "shared.dialog_geometry", "shared.display_format", "shared.fit_to_screen",
          "shared.light_scheme", "shared.opaque_popups", "shared.osgb",
          "shared.settings_store", "shared.tick_mark"]
hidden = (collect_submodules("Lector") + SHARED
          + collect_submodules("src.themes") + ["src.views.components.hscroll_strip",
                                                "docx", "openpyxl"])
# python-docx carries its default document template; openpyxl a few data files
datas = collect_data_files("docx") + collect_data_files("openpyxl")
# Lector's list of UKSI synonym corrections (Lector\synonyms.py finds it under scripts\)
datas += [(os.path.join(ROOT, "scripts", "uksi_synonym_corrections.csv"), "scripts")]

# Qt modules Lector never uses: leaving them out keeps the folder smaller
EXCLUDES = ["PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
            "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.QtQuick", "PySide6.QtQml",
            "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtDataVisualization",
            "PySide6.QtPdf", "PySide6.QtPdfWidgets", "tkinter", "pytest",
            # the suite's paths.py is not bundled: Lector\config.py makes a stand-in that
            # points at Documents\Lector\data when it runs frozen
            "paths"]

a = Analysis(
    [os.path.join(HERE, "lector_entry.py")],
    pathex=[ROOT, os.path.join(ROOT, "Observatum")],
    datas=datas,
    hiddenimports=hidden,
    excludes=EXCLUDES,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Lector", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="Lector")
