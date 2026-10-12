"""json.loads, a piece at a time, for a big outline file read behind the open window.

Round 6 startup (11 Oct 2026): the vice-county outlines (data/maps/vc_brc_wgs84.geojson,
2-14 MB) are read in a worker thread after the window opens. json.loads parses a whole
document in C without letting go of the GIL, so the window froze for 0.3-0.6 s while it ran.
loads_in_pieces gives exactly the same result but parses objects a value at a time and
arrays an element at a time (a GeoJSON's features, an outline's rings), and an outline's
points about 32 KB of text at a time (Round 8: a whole vice-county's outline at once held
the GIL for 20-40 ms, and the window's every call into Python waited for it), so the GUI
thread gets the GIL back between pieces. Anything it does not expect is handed to json.loads
whole.

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
    out, idx = _object(text, idx)
    if _skip(text, idx) != len(text):           # something after the object: let json say
        raise _Unexpected(idx)
    return out


def _value(text: str, idx: int):
    """(the value starting at idx, the index after it): objects and arrays in pieces."""
    c = text[idx:idx + 1]
    if c == "{":
        return _object(text, idx)
    if c == "[":
        return _array(text, idx)
    return _DEC.raw_decode(text, idx)


def _object(text: str, idx: int):
    out = {}
    idx = _skip(text, idx + 1)
    if text[idx:idx + 1] == "}":
        return out, idx + 1
    while True:
        _expect(text, idx, '"')
        key, idx = _DEC.raw_decode(text, idx)
        idx = _skip(text, idx)
        _expect(text, idx, ":")
        idx = _skip(text, idx + 1)
        value, idx = _value(text, idx)
        out[key] = value
        idx = _skip(text, idx)
        c = _expect(text, idx, ",}")
        idx = _skip(text, idx + 1)
        if c == "}":
            return out, idx


def _array(text: str, idx: int):
    """An array: one element at a time; an array of number arrays (an outline's ring of
    points) in chunks of about CHUNK characters (Round 8: a whole vice-county's outline in
    one go held the GIL for 20-40 ms at a time, and the window waited for each)."""
    j = _skip(text, idx + 1)
    first = text[j:j + 1]
    if first == "]":
        return [], j + 1
    if first != "[" and first != "{":
        return _DEC.raw_decode(text, idx)         # numbers, strings...: small
    if first == "[" and text[_skip(text, j + 1):_skip(text, j + 1) + 1] in _NUMBER_START:
        return _points(text, idx, j)
    out = []
    idx = j
    while True:
        value, idx = _value(text, idx)            # one element: the GIL is let go after it
        out.append(value)
        idx = _skip(text, idx)
        c = _expect(text, idx, ",]")
        idx = _skip(text, idx + 1)
        if c == "]":
            return out, idx


CHUNK = 32768                                     # characters of points parsed at once
_NUMBER_START = set("-0123456789")
_RING_END = re.compile(r"\][ \t\n\r]*\]")           # a point's "]" then the array's own
_NESTED = re.compile(r"\[[ \t\n\r]*\[")


def _points(text: str, idx: int, j: int):
    """An array of number arrays ([[lat, lon], ...], j at its first "["), parsed about CHUNK
    characters at a time, each chunk ending at the "]" closing a point. Only for flat number
    arrays (checked: no nested array, object or string between): anything else is _Unexpected,
    and the whole document then goes to json.loads (the same result, in one piece)."""
    m = _RING_END.search(text, j)
    if m is None:
        raise _Unexpected(j)
    last = m.start()                              # the "]" closing the last point
    if (_NESTED.search(text, j + 1, last) or text.find("{", j, last) >= 0
            or text.find('"', j, last) >= 0):
        raise _Unexpected(j)
    out = []
    while True:
        end = text.find("]", j + CHUNK, last) if j + CHUNK < last else -1
        if end < 0:
            end = last
        out.extend(json.loads("[" + text[j:end + 1] + "]"))   # the GIL is let go after it
        if end == last:
            return out, m.end()
        nxt = _skip(text, end + 1)
        _expect(text, nxt, ",")
        j = _skip(text, nxt + 1)


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
