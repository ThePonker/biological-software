"""What build_env_layers.py carries besides a feature's name and class (25 Oct 2026): the "details"
("a": [[label, text], ...]) and the web link ("u"), their formats, and the geology classes.
The fields read for each layer are listed in env_sources.py; this file only formats them.
"""
import re
from datetime import datetime

from scripts.env_sources import pick_column
from shared.maps.env_classes import BEDROCK

PERIODS = tuple(BEDROCK)[:11]                      # Neogene ... Cambrian
PERIOD_FIELDS = ("MAX_PERIOD", "MIN_PERIOD", "MAX_ERA")
_PRECAMBRIAN = ("NEOPROTEROZOIC", "MESOPROTEROZOIC", "PALAEOPROTEROZOIC")
_ERAS = {"PALAEOZOIC": "Palaeozoic (period not given)", "MESOZOIC": "Mesozoic (period not given)",
         "CAINOZOIC": "Cainozoic (period not given)"}


def text_of(v) -> str:
    """A cell as clean text ("" for None; 1426.0 -> "1426")."""
    if v is None:
        return ""
    if isinstance(v, float) and v == int(v):
        v = int(v)
    return str(v).strip()


def sentence(v) -> str:
    """First letter capital, the rest lower case ("RIVER TERRACE (UNDIFFERENTIATED)" -> "River terrace
    (undifferentiated)")."""
    s = text_of(v)
    return s[:1].upper() + s[1:].lower()


def _date(s: str) -> str:
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            d = datetime.strptime(s[:10] if "-" in s else s, fmt)
        except ValueError:
            continue
        return f"{d.day} {d.strftime('%b %Y')}"
    return ""


def format_value(v, fmt: str) -> str:
    """The text of a cell in one of the formats "", "ha", "int", "date", "sentence" ("" = omit)."""
    s = text_of(v)
    if not s:
        return ""
    if fmt == "ha":
        try:
            return f"{float(s):.1f} ha"
        except ValueError:
            return ""
    if fmt == "int":
        try:
            return str(int(float(s)))
        except ValueError:
            return s
    if fmt == "date":
        return _date(s)
    if fmt == "sentence":
        return sentence(s)
    return s


def period_class(max_period, max_era) -> str:
    """The bedrock class: the period when it is one of the palette's, else a coarser one from the era."""
    p = sentence(max_period)
    if p in PERIODS:
        return p
    era = text_of(max_era).upper()
    if era in _PRECAMBRIAN:
        return "Precambrian"
    return _ERAS.get(era, "Undifferentiated")


def age_text(max_period, min_period) -> str:
    """"Jurassic", or "Triassic to Jurassic" (MAX_PERIOD, then MIN_PERIOD) when they differ."""
    hi, lo = sentence(max_period), sentence(min_period)
    return hi if (not lo or lo == hi) else f"{hi} to {lo}" if hi else lo


def resolve(columns, part) -> dict:
    """The columns of one source file that `part` reads beyond name and class: {"extras": [(column,
    label, fmt)], "link": {FIELD: column}, "period": [max, min, era columns] (xform "period"),
    "cols": every such column, in order}."""
    extras = [(c, label, fmt) for f, label, fmt in part.extra if (c := pick_column(columns, (f,)))]
    link = {}
    for f in re.findall(r"\{(\w+)\}", part.link):
        c = pick_column(columns, (f,))
        if c is None:
            link = {}
            break
        link[f] = c
    period = [pick_column(columns, (f,)) for f in PERIOD_FIELDS] if part.xform == "period" else []
    cols = []
    for c in [e[0] for e in extras] + list(link.values()) + [c for c in period if c]:
        if c not in cols:
            cols.append(c)
    return {"extras": extras, "link": link, "period": period, "cols": cols}


def labels_of(res, part) -> list:
    """The detail labels a file will carry (for the dry run)."""
    out = [label for _c, label, _f in res["extras"]]
    if res["period"] and res["period"][0] and any(k == "age" for k, _l in part.computed):
        out += [label for k, label in part.computed if k == "age"]
    return out


def details(rec: dict, res, part):
    """(a, u): the details list of [label, text] pairs and the link of one row (`rec` {column: value})."""
    a = []
    for c, label, fmt in res["extras"]:
        text = format_value(rec.get(c), fmt)
        if text and text.upper() != "NA":
            a.append([label, text])
    if res["period"] and res["period"][0]:
        hi, lo = (rec.get(c) if c else None for c in res["period"][:2])
        for k, label in part.computed:
            text = age_text(hi, lo) if k == "age" else ""
            if text:
                a.append([label, text])
    u = ""
    if part.link and res["link"]:
        vals = {f: format_value(rec.get(c), "int") for f, c in res["link"].items()}
        if all(vals.values()):
            u = part.link.format(**vals)
    return a, u


def period_of(rec: dict, res) -> str:
    mx, _mn, era = (rec.get(c) if c else None for c in res["period"])
    return period_class(mx, era)
