r"""Make the binary form (shared/maps/layer_bin.py) of every map layer file already built.

    py -3.14 scripts\convert_layers_bin.py            dry run: lists what it would write
    py -3.14 scripts\convert_layers_bin.py --apply    writes <key>_<lod>.*.npy and .meta.json
    --dir PATH                                        another folder (default data\maps\layers)

The JSON files are never touched (they stay the master and the fallback). Each binary file is written
through a .tmp and os.replace. Image and value-grid headers (no features) are skipped. Nothing is
downloaded and nothing is rebuilt: a few seconds for the whole folder.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from shared.maps import layer_bin  # noqa: E402


def _default_dir() -> Path:
    import paths
    return Path(paths.ROOT) / "data" / "maps" / "layers"


def _estimate(jp: Path, doc: dict) -> int:
    arrays, meta = layer_bin.from_features(doc.get("features", []), {})
    return sum(a.nbytes for a in arrays.values()) + len(json.dumps(meta, separators=(",", ":")))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dir", help="the layers folder (default: data\\maps\\layers)")
    ap.add_argument("--apply", action="store_true", help="write the files (else a dry run)")
    args = ap.parse_args(argv)
    folder = Path(args.dir) if args.dir else _default_dir()
    files = sorted(folder.glob("*.json")) if folder.is_dir() else []
    print(f"Layer files in {folder}: {len(files)}")
    done = 0
    for jp in files:
        if jp.name.endswith(".meta.json"):
            continue
        try:
            doc = json.loads(jp.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  {jp.name}: unreadable ({e}); skipped")
            continue
        if not isinstance(doc, dict) or "features" not in doc:
            print(f"  {jp.name}: no features (image or grid header); skipped")
            continue
        if args.apply:
            layer_bin.write(jp, doc["features"], {k: v for k, v in doc.items() if k != "features"})
            size = sum(p.stat().st_size for p in layer_bin.all_paths(jp))
            print(f"  {jp.name}: wrote binary form, {size:,} bytes (JSON {jp.stat().st_size:,})")
        else:
            print(f"  {jp.name}: would write binary form, about {_estimate(jp, doc):,} bytes "
                  f"(JSON {jp.stat().st_size:,})")
        done += 1
    if args.apply:
        print(f"\nWrote the binary form of {done} files. The JSON files are unchanged.")
    else:
        print(f"\nDry run: {done} files would be converted. Nothing has been changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
