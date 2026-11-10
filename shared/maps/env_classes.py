"""Class colours for the Environment layers drawn by class (25 Oct 2026). Data only, no Qt.

A layer listed in PALETTES is drawn with one colour per class (the feature's "t") and has a key
in the Layers window; any other layer keeps its single colour (layers.env_style).

These are published colour schemes, kept as data, not theme colours (the "no hardcoded colours"
rule is for the suite's own interface):
- bedrock: the International Chronostratigraphic Chart's period colours (ICS, 2023), the usual
  colouring of a geological map by age;
- soil parent material: BGS's own colours for soil texture, read from SPM1k_Soil_texture.sld in
  the BGS download (SoilParentMaterial 1 km, V1);
- superficial deposits, ancient woodland, NFI and access land: chosen here (no published scheme
  came with the data), pale enough for the record squares to read on top.

class_colour() matches a class case-insensitively and ignoring extra spaces; a class not listed
gets a steady colour from FALLBACK (the same class always gets the same colour), so a new value
in a later download still draws, and shows in the key.
"""
from __future__ import annotations

import zlib
from typing import Dict, List, Tuple

# bedrock: ICS period colours; build_env_layers.py's period_class() makes these names
BEDROCK = {
    "Neogene": "#FFE619", "Palaeogene": "#FD9A52", "Cretaceous": "#7FC64E",
    "Jurassic": "#34B2C9", "Triassic": "#812B92", "Permian": "#F04028",
    "Carboniferous": "#67A599", "Devonian": "#CB8C37", "Silurian": "#B3E1B6",
    "Ordovician": "#009270", "Cambrian": "#7FA056",
    "Palaeozoic (period not given)": "#99C08D", "Mesozoic (period not given)": "#67C5CA",
    "Cainozoic (period not given)": "#F2F91D", "Precambrian": "#F73563",
    "Undifferentiated": "#C8C8C8",
}
BEDROCK_ORDER = tuple(BEDROCK)          # youngest first, as a geological key is read

SUPERFICIAL = {
    "Till": "#B9C7D9", "Alluvium": "#F5E6A3", "Peat": "#9C7B66",
    "Glacial sand and gravel": "#F2B880", "River terrace deposits (undifferentiated)": "#F6D2A6",
    "Raised marine deposits (undifferentiated)": "#A8D5E2", "Blown sand": "#FFF1AE",
    "Clay-with-flints": "#C49A6C", "Sand and gravel of uncertain age and origin": "#E8C39E",
    "Landslip": "#D99191", "Brickearth": "#E0B98D",
    "Lacustrine deposits (undifferentiated)": "#9FC5A8", "Crag group": "#E6A65C",
}

# BGS SPM1k_Soil_texture.sld (fill colours as published)
SOIL_TEXTURE = {
    "Chalky clay to chalky loam": "#FFAA00", "Chalky, silty loam": "#FFD37F",
    "Chalky, sandy loam": "#FFEBAF", "Clayey": "#CD6666", "Clay to silt": "#CD8966",
    "Clay to clayey loam": "#D7B09E", "Clay to loam": "#D7B09E", "Clay to sandy loam": "#F5CA7A",
    "Clayey loam": "#D7B09E", "Clayey loam to sandy loam": "#F5CA7A",
    "Clayey loam to silty loam": "#D7B09E", "Clayey loam, locally chalky": "#D7B09E",
    "Loam": "#CDCD66", "Loam to clay": "#D7B09E", "Loam to clayey loam": "#D7B09E",
    "Loam to clayey loam, locally chalky": "#D7B09E", "Loam to sandy": "#F5F57A",
    "Loam to sandy loam": "#F5F57A", "Loam to silty": "#B4D79E", "Loam to silty loam": "#CDAA66",
    "Peat": "#AA66CD", "Peat and peaty clay or silt": "#AA66CD", "Peaty clay": "#AA66CD",
    "Peaty clay or silt": "#AA66CD", "Peaty silt": "#C29ED7", "Sand": "#FFFF73",
    "Sand to loam": "#F5F57A", "Sand to sandy loam": "#FFFF73", "Sand to silt": "#E9FFBE",
    "Sandy loam": "#F5F57A", "Sandy loam to clayey loam": "#F5CA7A",
    "Sandy loam to loam": "#F5F57A", "Sandy loam to sand": "#FFFF73",
    "Sandy loam to silty loam": "#E9FFBE", "Silt to sand": "#9ED7C2",
    "Silt to silty loam": "#B4D79E", "Silty loam": "#A5F57A", "Silty loam to sandy loam": "#A5F57A",
    "Silty loam to silt": "#9ED7C2", "Varied, locally peaty": "#D69DBC", "Na": "#BEE8FF",
}

ANCIENT_WOODLAND = {
    "ASNW": "#5E8C4A", "ARW": "#9DBB7A", "PAWS": "#9DBB7A", "RAWS": "#7FA661",
    "AWSUC": "#B5C4A4", "Ancient Wood Pasture": "#C2B46A",
    "Ancient (of semi-natural origin)": "#5E8C4A",
    "Long-Established (of plantation origin)": "#A7C08C",
    "Other (on Roy map)": "#C6CFB8",
}

NFI = {
    "Broadleaved": "#8DBF6B", "Conifer": "#4F7F5A", "Mixed mainly broadleaved": "#A3C487",
    "Mixed mainly conifer": "#6E9A6E", "Young trees": "#C6DDA0", "Coppice": "#B9A76B",
    "Coppice with standards": "#A89A5E", "Shrub": "#C8C08A", "Low density": "#D5DDB8",
    "Assumed woodland": "#B8C9A8", "Felled": "#D8C3A5", "Ground prep": "#E0CDB0",
    "Cloud \\ shadow": "#DDDDDD", "Uncertain": "#D0D0C0", "Windblow": "#C9B79C",
    "Failed": "#D9CBB8",
}

CROW = {
    "Open country": "#C9A66B", "Registered common land": "#A98BC0",
    "Section 16 dedicated land": "#7FB5A8",
    "Open country + Registered common land": "#B898A0",
    "Open country + Section 16 dedicated land": "#A8AE8A",
    "Registered common land + Section 16 dedicated land": "#94A0B4",
    "Open country + Registered common land + Section 16 dedicated land": "#A7A39C",
    "Access land": "#C9A66B",
}

PALETTES: Dict[str, Dict[str, str]] = {
    "geology_bedrock": BEDROCK, "geology_superficial": SUPERFICIAL, "soil_pm": SOIL_TEXTURE,
    "ancient_woodland": ANCIENT_WOODLAND, "nfi": NFI, "crow_access": CROW,
}
SOURCES = {
    "geology_bedrock": "Colours: International Chronostratigraphic Chart (ICS) periods.",
    "soil_pm": "Colours: BGS Soil Parent Material, soil texture style.",
}

# a steady colour for a class not in its layer's palette (crc32 of the class: the same every run)
FALLBACK = ("#C9B79C", "#A8C3B0", "#D6B4A8", "#B4B9D6", "#D6CFA0", "#A9C99A", "#CFA9C6",
            "#9FC1D1", "#DDC08E", "#B7B7A4")


def _norm(text) -> str:
    return " ".join(str(text or "").split()).casefold()


_NORMED = {k: {_norm(c): v for c, v in p.items()} for k, p in PALETTES.items()}


def is_classed(key: str) -> bool:
    """True when the layer is drawn one colour per class."""
    return key in PALETTES


def class_colour(key: str, cls: str) -> str:
    """The hex colour of a class of a classed layer (FALLBACK for one not listed)."""
    hit = _NORMED.get(key, {}).get(_norm(cls))
    if hit:
        return hit
    return FALLBACK[zlib.crc32(_norm(cls).encode("utf-8")) % len(FALLBACK)]


def key_entries(key: str, classes) -> List[Tuple[str, str]]:
    """[(class, hex)] for a layer's key: the classes present in `classes`, in the palette's order
    (bedrock youngest first), then any others alphabetically."""
    present = {c for c in classes if c}
    order = list(PALETTES.get(key, {}))
    rank = {_norm(c): i for i, c in enumerate(order)}
    known = sorted((c for c in present if _norm(c) in rank), key=lambda c: rank[_norm(c)])
    other = sorted((c for c in present if _norm(c) not in rank), key=_norm)
    return [(c, class_colour(key, c)) for c in known + other]
