"""Disk cache of the species search index (Round 16, C4). No Qt.

SpeciesIndex (shared/species_search.py) takes ~1.3 s to build from uksi.db (3 s cold). Its
state is plain lists, dicts, tuples, strings and ints, so it is saved with marshal (no pickle,
no arbitrary objects) in a local cache folder (outside OneDrive; see default_cache_dir) -- and loaded while
uksi.db is unchanged. The file holds a length-prefixed header (code version and a hash of the search/lookup source, Python version, uksi.db's
size, mtime and inode) then the state; a header that does not match, or any error reading, means
"no cache" and the index is rebuilt and the file rewritten atomically (temp file + os.replace).
Raise CODE_VERSION whenever how names are folded or indexed changes.
"""
from __future__ import annotations

import hashlib
import marshal
import os
import sys
from pathlib import Path
from typing import Optional

CODE_VERSION = 1
MAGIC = "biosoft-species-index"
_CODE_FILES = ("species_search.py", "species_lookup.py")
_code_hash = None


def _source_hash() -> str:
    """sha1 of the source bytes of the modules that decide how the index is built."""
    global _code_hash
    if _code_hash is None:
        h = hashlib.sha1()
        for name in _CODE_FILES:
            try:
                h.update((Path(__file__).parent / name).read_bytes())
            except OSError:
                h.update(b"?")
        _code_hash = h.hexdigest()
    return _code_hash


def _stamp(db_path: str):
    """(size, mtime_ns, inode) of uksi.db, or None when it can't be cached safely: missing, or a
    non-empty -wal beside it (recent commits not yet in the main file). An empty -wal, which a
    shutdown checkpoint touches, is ignored."""
    try:
        st = os.stat(db_path)
    except OSError:
        return None
    try:
        if os.stat(db_path + "-wal").st_size > 0:
            return None
    except OSError:
        pass
    return (st.st_size, st.st_mtime_ns, st.st_ino)


def make_header(db_path: str) -> Optional[dict]:
    """The header for uksi.db as it is now (take it BEFORE building the index), or None."""
    stamp = _stamp(db_path)
    if stamp is None:
        return None
    return {"magic": MAGIC, "code": CODE_VERSION, "src_hash": _source_hash(),
            "py": tuple(sys.version_info[:2]), "src": stamp}


def default_cache_dir() -> Path:
    """Local, outside OneDrive: %LOCALAPPDATA%/BiologicalSoftware/cache (else ~/.cache/...);
    data/cache only on an away machine."""
    try:
        from shared.away_mode import away_active
        if away_active():
            import paths
            return Path(paths.DATA_DIR) / "cache"
    except Exception:
        pass
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) if base else Path.home() / ".cache"
    return root / "BiologicalSoftware" / "cache"


def cache_file_for(db_path: str, requested_path, cache_dir=None) -> Optional[Path]:
    """Where this index is cached: the local cache folder for the suite's own uksi.db (requested_path None),
    else only in an explicit cache_dir. None = do not cache."""
    if cache_dir is None:
        if requested_path is not None:
            return None
        cache_dir = default_cache_dir()
    name = hashlib.sha1(db_path.encode("utf-8", "replace")).hexdigest()[:12]
    return Path(cache_dir) / f"species_index_{name}.bin"


def load(cache_file: Path, db_path: str):
    """The cached SpeciesIndex if the file matches uksi.db and this code; else None."""
    from shared.species_search import SpeciesIndex
    try:
        data = Path(cache_file).read_bytes()      # (marshal.load(file) is 5x slower: tiny reads)
        n = int.from_bytes(data[:8], "little")
        want = make_header(db_path)
        if want is None or marshal.loads(data[8:8 + n]) != want:
            return None
        return SpeciesIndex.from_state(marshal.loads(data[8 + n:]))
    except Exception:                       # missing, truncated, other Python: just rebuild
        return None


def save(idx, cache_file: Path, header: Optional[dict]) -> bool:
    """Write the index atomically. Never raises (a read-only folder just means no cache)."""
    if header is None:                       # no safe stamp (non-empty -wal): no cache
        return False
    tmp = cache_file.with_name(cache_file.name + f".{os.getpid()}.tmp")
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "wb") as f:
            head = marshal.dumps(header)
            f.write(len(head).to_bytes(8, "little") + head)
            f.write(marshal.dumps(idx.to_state()))
        os.replace(tmp, cache_file)
        return True
    except Exception as e:
        print(f"[species_search] index cache not written: {e}")
        return False
