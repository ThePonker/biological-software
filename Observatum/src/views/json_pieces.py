"""json.loads, a piece at a time, for a big outline file read behind the open window.

Round 6 startup (11 Oct 2026): the vice-county outlines (data/maps/vc_brc_wgs84.geojson,
2-14 MB) are read in a worker thread after the window opens. json.loads parses a whole
document in C without letting go of the GIL, so the window froze for 0.3-0.6 s while it ran.
loads_in_pieces gives exactly the same result but parses a top-level object's list values
one element at a time (a GeoJSON's features, an outline's rings), so the GUI thread gets the
GIL back between pieces. Anything else (or anything it does not expect) is handed to
json.loads whole.

    with pieces_for(vc_map):          # vc_map.json.load(...) parses in pieces meanwhile
        vc_map.load_vc_polygons(path)
"""

import json
import re
from contextlib import contextmanager

_DEC = json.JSONDecoder()
_WS = re.compile(r"[ \t\n\r]*")


class _Unexpected(ValueError):
    pass


def _skip(text: str, idx: int) -> int:
    return _WS.match(text, idx).end()


def _expect(text: str, idx: int, chars: str) -> str:
    c = text[idx:idx + 1]
    if not c or c not in chars:
        raise _Unexpected(idx)
    return c


def loads_in_pieces(text: str):
    """The same as json.loads(text)."""
    try:
        return _object_in_pieces(text)
    except (_Unexpected, ValueError, IndexError):
        return json.loads(text)


def _object_in_pieces(text: str):
    idx = _skip(text, 0)
    if text[idx:idx + 1] != "{":
        return json.loads(text)
    out = {}
    idx = _skip(text, idx + 1)
    if text[idx:idx + 1] == "}":
        idx += 1
    else:
        while True:
            _expect(text, idx, '"')
            key, idx = _DEC.raw_decode(text, idx)
            idx = _skip(text, idx)
            _expect(text, idx, ":")
            idx = _skip(text, idx + 1)
            if text[idx:idx + 1] == "[":
                value, idx = _list_in_pieces(text, idx)
            else:
                value, idx = _DEC.raw_decode(text, idx)
            out[key] = value
            idx = _skip(text, idx)
            c = _expect(text, idx, ",}")
            idx = _skip(text, idx + 1)
            if c == "}":
                break
    if _skip(text, idx) != len(text):           # something after the object: let json say
        raise _Unexpected(idx)
    return out


def _list_in_pieces(text: str, idx: int):
    out = []
    idx = _skip(text, idx + 1)
    if text[idx:idx + 1] == "]":
        return out, idx + 1
    while True:
        value, idx = _DEC.raw_decode(text, idx)     # one element: the GIL is let go after it
        out.append(value)
        idx = _skip(text, idx)
        c = _expect(text, idx, ",]")
        idx = _skip(text, idx + 1)
        if c == "]":
            return out, idx


class _PieceJson:
    """Stands in for the json module inside one module while a big file is read."""

    def load(self, fp, **kw):
        if kw:
            return json.load(fp, **kw)
        return loads_in_pieces(fp.read())

    def loads(self, s, **kw):
        if kw or not isinstance(s, str):
            return json.loads(s, **kw)
        return loads_in_pieces(s)

    def __getattr__(self, name):
        return getattr(json, name)


@contextmanager
def pieces_for(module):
    """Within the block, `module`'s json.load / json.loads parse in pieces (same results)."""
    real = getattr(module, "json", None)
    if real is not json:
        yield
        return
    module.json = _PieceJson()
    try:
        yield
    finally:
        module.json = real
