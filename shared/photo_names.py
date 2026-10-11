"""Read the species name (and date) out of a photo's file name and folders. Pure: no Qt, no
database, never opens the file (A8 groundwork, 11 Oct 2026).

    parse_photo_path(path, root=None, today=None) -> PhotoName

Wil's two naming conventions:
  * field photos   Photos/Life/<taxonomic folders>/<Genus species>/
                   'Genus species - Common name N.jpg'
                   'Zygaena filipendulae ssp. stephensi - Six-spot Burnet 2.jpg'
  * microscope     Photos/Microscope Photos/<Order>/.../<Family>/...
                   'Pterostichus niger 6.vi.21.jpg', 'Lamia textor 14.VII.2023 2.jpg',
                   'Aphodius sp 1.x.19.jpg'
Notes in brackets ('(1a)') may sit anywhere; they are kept in `note`. Months are roman
(i-xii, any case); a 2-digit year is 20YY. A date after `today`, a bad month or day, and a
year before 1900 are warnings (the date is then left empty, except a future date, which is
kept with the warning so it can be looked at).

The folder is a second witness: in Life the species folder should carry the same name as the
file (a disagreement is a warning; a file that does not parse but sits in a species folder
takes the folder's name, name_source='folder'). In Microscope Photos the Order / Family
folders are recorded for photo_match to compare with the matched taxon (a soft check only:
the folder taxonomy is out of date in places, e.g. Lymantriidae).
"""
from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from pathlib import PurePath
from typing import List, Optional, Union

LIFE = "life"
MICROSCOPE = "microscope"

AREA_LIFE = "Life"
AREA_MICROSCOPE = "Microscope Photos"
KNOWN_AREAS = (AREA_LIFE, AREA_MICROSCOPE, "All Other Photos", "Originals")

IMAGE_EXTS = frozenset(".jpg .jpeg .jpe .png .tif .tiff .heic .heif .webp .gif .bmp .dng .cr2 "
                       ".cr3 .nef .arw .orf .rw2 .raf".split())
VIDEO_EXTS = frozenset(".mp4 .mov .avi .mkv .m4v .3gp .wmv .mts .m2ts .mpg .mpeg .webm".split())

ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8,
         "ix": 9, "x": 10, "xi": 11, "xii": 12}
INFRA_RANKS = {"ssp": "ssp.", "subsp": "ssp.", "var": "var.", "f": "f.", "ab": "ab."}

_NOTE = re.compile(r"\(([^()]*)\)")
_NAME = r"(?P<genus>[A-Za-z][a-z]+)\s+(?P<epithet>[a-z][a-z-]+|sp\.?|spp\.?)" \
        r"(?:\s+(?P<irank>ssp|subsp|var|f|ab)\.?\s*(?P<infra>[a-z][a-z-]+))?"
_LIFE = re.compile(r"^" + _NAME + r"\s*-\s*(?P<common>.*?)(?:\s+(?P<n>\d+))?\s*$")
_DATE = r"(?P<d>\d{1,2})[.\-](?P<m>[ivxIVX]{1,5}|\d{1,2})[.\-](?P<y>\d{4}|\d{2})"
_MICRO = re.compile(r"^" + _NAME + r"\s+" + _DATE + r"(?:\s+(?P<n>\d+))?\s*$")
_PLAIN = re.compile(r"^" + _NAME + r"(?:\s+(?P<n>\d+))?\s*$")
_FOLDER = re.compile(r"^" + _NAME + r"\s*$")


@dataclass
class PhotoName:
    """What a photo's path says. `binomial` is the name to look up: 'Genus species',
    'Genus species infra' (UKSI writes subspecies without 'ssp.'), or 'Genus' for 'sp'."""
    path: str
    stem: str = ""
    ext: str = ""
    kind: str = "other"                  # image / video / other
    area: str = ""                       # Life / Microscope Photos / All Other Photos / ...
    convention: Optional[str] = None     # life / microscope / None (file name not understood)
    parsed: bool = False                 # the FILE NAME gave a species name
    name_source: Optional[str] = None    # file / folder / None
    genus: str = ""
    epithet: str = ""                    # '' for 'sp'
    infra_rank: str = ""                 # 'ssp.' / 'var.' / ...
    infra: str = ""
    binomial: str = ""
    written_name: str = ""               # as written in the file name
    common_name: str = ""
    number: Optional[int] = None
    note: str = ""                       # '(1a)' etc., without brackets, '; '-joined
    date: Optional[str] = None           # ISO yyyy-mm-dd
    date_raw: str = ""
    folder_name: str = ""                # Life: the species folder's name, when it is one
    folder_binomial: str = ""
    folder_agrees: Optional[bool] = None
    folder_order: str = ""               # Microscope: '...ptera' folder above the file
    folder_family: str = ""              # Microscope: '...idae' folder above the file
    warnings: List[str] = field(default_factory=list)


def media_kind(ext: str) -> str:
    e = ext.lower()
    return "image" if e in IMAGE_EXTS else "video" if e in VIDEO_EXTS else "other"


def parse_date(d: str, m: str, y: str, today: datetime.date):
    """(iso or None, [warnings]) for day, month (roman or digits), year (2 or 4 digits)."""
    warns: List[str] = []
    raw = f"{d}.{m}.{y}"
    if m.isdigit():
        month = int(m)
        warns.append(f"month written in digits in '{raw}'")
    else:
        month = ROMAN.get(m.lower())
        if month is None:
            return None, [f"bad month '{m}' in '{raw}'"]
    if not 1 <= month <= 12:
        return None, [f"bad month '{m}' in '{raw}'"]
    year = int(y) + 2000 if len(y) == 2 else int(y)
    if year < 1900:
        return None, [f"year {year} before 1900 in '{raw}'"]
    try:
        dt = datetime.date(year, month, int(d))
    except ValueError:
        return None, [f"no such date '{raw}'"]
    if dt > today:
        warns.append(f"date {dt.isoformat()} is in the future ('{raw}')")
    return dt.isoformat(), warns


def _name_bits(m) -> dict:
    genus = m.group("genus")
    epithet = m.group("epithet")
    bits = {"warnings": []}
    if genus[0].islower():
        bits["warnings"].append(f"genus '{genus}' written in lower case")
        genus = genus[0].upper() + genus[1:]
    if epithet.rstrip(".") in ("sp", "spp"):
        epithet = ""
    infra = m.group("infra") or ""
    irank = INFRA_RANKS.get(m.group("irank") or "", "") if infra else ""
    bits.update(genus=genus, epithet=epithet, infra=infra, infra_rank=irank,
                binomial=" ".join(x for x in (genus, epithet, infra) if x),
                written_name=" ".join(m.group(0).split()[:2 + (2 if infra else 0)]))
    return bits


def folder_binomial(name: str) -> str:
    """The name to look up from a species folder name ('' if it is not one)."""
    m = _FOLDER.match(" ".join(_NOTE.sub(" ", name).split()))
    if not m or m.group("genus")[0].islower():
        return ""
    return _name_bits(m)["binomial"]


def _area(parts) -> tuple:
    """(area, index of the area folder in parts) -- the first known area folder."""
    for i, p in enumerate(parts):
        for a in KNOWN_AREAS:
            if p.lower() == a.lower():
                return a, i
    return "", -1


def parse_photo_path(path: Union[str, PurePath], root: Union[str, PurePath, None] = None,
                     today: Optional[datetime.date] = None) -> PhotoName:
    """Parse one photo path. Only the path string is used (the file is never opened)."""
    today = today or datetime.date.today()
    p = PurePath(path)
    if root is not None:
        try:
            p = p.relative_to(PurePath(root))
        except ValueError:
            pass
    folders = list(p.parts[:-1])
    out = PhotoName(path=str(path), stem=p.stem, ext=p.suffix.lower(), kind=media_kind(p.suffix))
    out.area, at = _area(folders)
    notes = [n.strip() for n in _NOTE.findall(p.stem) if n.strip()]
    out.note = "; ".join(notes)
    stem = " ".join(_NOTE.sub(" ", p.stem).split())

    m = _LIFE.match(stem)
    conv = LIFE if m else None
    if m is None:
        m = _MICRO.match(stem)
        conv = MICROSCOPE if m else None
    if m is None and out.area in (AREA_LIFE, AREA_MICROSCOPE):
        m = _PLAIN.match(stem)            # 'Genus species 3' with no common name or date
        conv = (LIFE if out.area == AREA_LIFE else MICROSCOPE) if m else None
        if m:
            out.warnings.append("no common name or date in the file name")
    if m is not None:
        bits = _name_bits(m)
        out.warnings.extend(bits.pop("warnings"))
        for k, v in bits.items():
            setattr(out, k, v)
        out.convention, out.parsed, out.name_source = conv, True, "file"
        if m.group("n"):
            out.number = int(m.group("n"))
        if conv == LIFE and "common" in m.groupdict():
            out.common_name = (m.group("common") or "").strip()
        if "d" in m.groupdict() and m.group("d"):
            out.date_raw = f"{m.group('d')}.{m.group('m')}.{m.group('y')}"
            out.date, warns = parse_date(m.group("d"), m.group("m"), m.group("y"), today)
            out.warnings.extend(warns)

    # second witness: the folders
    if out.area == AREA_LIFE and folders:
        fb = folder_binomial(folders[-1])
        if fb:
            out.folder_name, out.folder_binomial = folders[-1], fb
            if out.parsed:
                same = fb.lower() == out.binomial.lower()
                # a subspecies photo in its species' folder is fine
                if not same and out.infra:
                    same = fb.lower() == f"{out.genus} {out.epithet}".lower()
                out.folder_agrees = same
                if not same:
                    out.warnings.append(f"folder says '{fb}', file says '{out.binomial}'")
            else:
                out.binomial, out.genus, out.name_source = fb, fb.split()[0], "folder"
                out.epithet = fb.split()[1] if len(fb.split()) > 1 else ""
                out.convention = LIFE
                out.warnings.append(f"file name not understood; name taken from folder '{fb}'")
    if out.area == AREA_MICROSCOPE:
        for f in folders[at + 1:]:
            low = f.lower()
            if low.endswith("ptera") or low in ("araneae", "opiliones", "isopoda", "acari",
                                                 "pseudoscorpiones", "odonata", "mecoptera"):
                out.folder_order = f
            elif low.endswith("idae"):
                out.folder_family = f
    if not out.parsed and out.name_source is None and out.kind == "image" \
            and out.area in (AREA_LIFE, AREA_MICROSCOPE):
        out.warnings.append("file name not understood")
    return out


__all__ = ["PhotoName", "parse_photo_path", "parse_date", "folder_binomial", "media_kind",
           "LIFE", "MICROSCOPE", "AREA_LIFE", "AREA_MICROSCOPE", "IMAGE_EXTS", "VIDEO_EXTS"]
