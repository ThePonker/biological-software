"""Tabella -- Patch existing .xlsm workbooks with updated VBA.

Surgical fix for the LoadRecordsCSV CSV-parsing bug (May 2026).
Replaces the DataEntry VBA module in each .xlsm with the current
vba_source.py MODULE_CODE. Worksheet data (entries, Records sheet,
any other content) is preserved -- only the VBA module is replaced.

Usage:
    python -m Tabella.patch_existing_vba <path_or_glob>

Examples:
    # Patch all active workbooks
    python -m Tabella.patch_existing_vba "C:\\Users\\Wil J. Heeney\\OneDrive\\Active Record Books\\*.xlsm"

    # Patch a single workbook
    python -m Tabella.patch_existing_vba "C:\\path\\to\\workbook.xlsm"

After patching, open each workbook and run Alt+F8 -> RefreshRecords to
repopulate the Records sheet with correctly-parsed values.
"""

import sys
import shutil
from glob import glob
from pathlib import Path
from datetime import datetime

# Make Tabella importable when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import win32com.client
except ImportError:
    print("pywin32 required: pip install pywin32")
    sys.exit(1)

from Tabella.vba_source import MODULE_CODE, THISWORKBOOK_CODE


def patch_workbook(xlsm_path: Path) -> bool:
    """Replace the DataEntry module in an .xlsm with current MODULE_CODE.

    Takes a timestamped backup before modifying. Returns True on success.
    """
    print(f"\n  Patching: {xlsm_path.name}")

    # Backup alongside the original
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = xlsm_path.with_name(f"{xlsm_path.stem}.bak-{stamp}.xlsm")
    shutil.copy2(str(xlsm_path), str(backup))
    print(f"    Backup: {backup.name}")

    xl = win32com.client.Dispatch("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    wb = None

    try:
        wb = xl.Workbooks.Open(str(xlsm_path.resolve()))
        vb_proj = wb.VBProject

        # Remove the existing DataEntry module if present
        try:
            old_mod = vb_proj.VBComponents("DataEntry")
            vb_proj.VBComponents.Remove(old_mod)
            print("    Removed old DataEntry module")
        except Exception:
            print("    No existing DataEntry module (will add fresh)")

        # Inject the current module code
        mod = vb_proj.VBComponents.Add(1)  # 1 = vbext_ct_StdModule
        mod.Name = "DataEntry"
        mod.CodeModule.AddFromString(MODULE_CODE)
        print("    Injected updated DataEntry module")

        # Refresh ThisWorkbook handlers (adds Workbook_Open protection)
        tw = vb_proj.VBComponents("ThisWorkbook")
        cm = tw.CodeModule
        if cm.CountOfLines > 0:
            cm.DeleteLines(1, cm.CountOfLines)
        cm.AddFromString(THISWORKBOOK_CODE)
        print("    Refreshed ThisWorkbook handlers (Workbook_Open protection)")

        wb.Save()
        wb.Close(SaveChanges=False)
        xl.Quit()
        print(f"    OK: {xlsm_path.name}")
        return True

    except Exception as e:
        print(f"    FAILED: {e}")
        if "Programmatic access" in str(e):
            print("\n    Fix: Excel > File > Options > Trust Centre > Trust")
            print("         Centre Settings > Macro Settings > tick")
            print("         'Trust access to the VBA project object model'")
        try:
            if wb is not None:
                wb.Close(SaveChanges=False)
        except Exception:
            pass
        try:
            xl.Quit()
        except Exception:
            pass
        return False


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    pattern = sys.argv[1]
    if any(c in pattern for c in "*?["):
        paths = [Path(p) for p in glob(pattern)]
    else:
        paths = [Path(pattern)]

    paths = [p for p in paths if p.suffix.lower() == ".xlsm" and p.exists()]
    # Skip already-made backups
    paths = [p for p in paths if ".bak-" not in p.stem]

    if not paths:
        print(f"No .xlsm files found matching: {pattern}")
        sys.exit(1)

    print(f"Patching {len(paths)} workbook(s)...")
    for p in paths:
        print(f"  - {p.name}")

    success = 0
    for p in paths:
        if patch_workbook(p):
            success += 1

    print()
    print(f"Done: {success}/{len(paths)} workbooks patched.")
    print()
    print("Next step:")
    print("  Reopen each patched workbook (macros enabled) -- sheet")
    print("  protection applies automatically at open. Or run Alt+F8 ->")
    print("  ApplyProtection manually.")
    print("  Open each patched workbook and run Alt+F8 -> RefreshRecords.")
    print("  The Records sheet will be repopulated with correctly-parsed")
    print("  values. Verify by selecting a species you know has multiple")
    print("  commercial projects (e.g. Tetrops praeustus) and checking the")
    print("  info panel shows the correct Specimens count.")


if __name__ == "__main__":
    main()
