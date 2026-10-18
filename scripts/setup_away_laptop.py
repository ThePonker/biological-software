r"""Set up this laptop as an away machine (run once, on the laptop). 18 Oct 2026.

    py -3.14 scripts\setup_away_laptop.py            dry run: says what it would do
    py -3.14 scripts\setup_away_laptop.py --apply    writes the marker, makes the first local copy

The marker %LOCALAPPDATA%\Flauna\away_machine.json is local, never in OneDrive. From then on
paths.DATA_DIR on this machine is %LOCALAPPDATA%\Flauna\away_data, a read-only copy. Start it
with launchers\run_away.bat. Refuses until the desktop has made the away copy (manifest.json
in OneDrive\Observatum away copy).
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shared import away_mode  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Set up this laptop as an away machine.")
    ap.add_argument("--apply", action="store_true", help="write the marker and copy the data")
    a = ap.parse_args(argv)
    away = away_mode.away_dir()
    manifest = away_mode.read_manifest(away)
    if manifest is None:
        print(f"Refusing: no away copy yet ({away}\\manifest.json is missing).")
        print("Run scripts\\make_away_copy.py on the desktop and let OneDrive sync, then try again.")
        return 1
    if manifest.get("source_host") == socket.gethostname():
        print("Refusing: this is the desktop that makes the copies "
              f"(source host {manifest.get('source_host')}). Run this on the laptop.")
        return 1
    marker = away_mode.marker_path()
    print(f"Away copy found, made {away_mode.format_made_at(manifest['made_at'])} "
          f"on {manifest.get('source_host', '?')}.")
    print(f"Marker:     {marker}")
    print(f"Local data: {away_mode.local_data_dir()}")
    if not a.apply:
        print("Dry run: nothing written. Run again with --apply to set this laptop up.")
        return 0
    try:                                        # the first copy first; the marker only if it worked
        made = away_mode.refresh_local_copy()
    except Exception as e:
        print(f"FAILED to make the first local copy: {e}")
        print("The marker was not written.")
        return 1
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({"machine": socket.gethostname(),
                                  "date": datetime.now().date().isoformat()}, indent=2),
                      encoding="utf-8")
    print("Marker written.")
    print(f"Local copy ready (from {away_mode.format_made_at(made)}). Start with launchers\\run_away.bat.")
    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
