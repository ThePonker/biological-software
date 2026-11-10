"""Where scripts/build_env_layers.py finds each Environment dataset and which fields it reads
(25 Oct 2026). Everything that may need correcting after a look at the real files is here.

A source file is found under --source by its path: the folder and file names, split into words
(a token of up to 4 letters must be a whole word: "sssi", "spa", "nrw"; a longer one may be part
of a word). A Part matches when ALL tokens of any one alternative in `any_of` are in the path and
none of `exclude`. So a folder "SSSI England" holding Sites_of_Special_Scientific_Interest.shp
matches ("sssi", "england"). Field names are tried in order, case ignored; a column whose name
contains "name" is the last resort for a name. FIELDS marked (unverified) were not confirmed
against the publisher's own files.
"""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple


@dataclass(frozen=True)
class Part:
    region: str
    any_of: Tuple[Tuple[str, ...], ...]
    name: Tuple[str, ...] = ()          # field(s) for the feature's name "n"
    cls: Tuple[str, ...] = ()           # field(s) for its class "t"
    fixed: str = ""                     # "t" when there is no class field (or none is found)
    prefix: str = ""                    # put before the class ("carbonate ")
    exclude: Tuple[str, ...] = ()
    need_name: bool = False             # refuse to build when no name field is found
    xform: str = ""                     # "ancient": ASNW / PAWS / ARW ...; "period": bedrock period
                                        # (MAX_PERIOD / MAX_ERA); "sentence": class in sentence case
    flags: Tuple[Tuple[str, str], ...] = ()   # (yes/no field, label): the class is the labels
    only_flagged: bool = False          # of the fields set; only_flagged: other rows are left out
    # details "a" for Identify: (field, label, format); format "", "ha", "int", "date", "sentence"
    extra: Tuple[Tuple[str, str, str], ...] = ()
    link: str = ""                      # the feature's own web page; {FIELD} filled from the row
    computed: Tuple[Tuple[str, str], ...] = ()   # (kind, label): "age" (bedrock, from the periods)
    skip: Tuple[str, ...] = ()          # rows whose class starts with one of these are left out


@dataclass(frozen=True)
class LayerSpec:
    key: str
    parts: Tuple[Part, ...]
    gb: Tuple[int, int] = (250, 100000)         # (tolerance m, minimum area m2); None: no GB file
    county: Tuple[int, int] = (25, 2000)
    dissolve: bool = False                      # join neighbours with the same n and t first


def _desig(key, words, name_field, label, **by_region):
    """A designation type: England, Wales and Scotland parts, all named by `name_field` (or NAME,
    SITE_NAME ...) and typed `label`. `by_region` {"England": {"extra": ..., "link": ...}} adds details."""
    names = (name_field, "NAME", "SITE_NAME", "SSSI_NAME")

    def part(region, extra=()):
        return Part(region, tuple((w, region.lower()) for w in words), names, fixed=label,
                    need_name=True, exclude=extra, **by_region.get(region, {}))
    return LayerSpec(key, (part("England", ("impact", "irz", "risk")), part("Wales"),
                           part("Scotland")))


def _eng(code, area, status="", link=""):
    """England's details: Code, Area (ha), Status (when the file has one), and the page link."""
    return {"extra": ((code, "Code", ""), (area, "Area", "ha"))
            + ((status, "Status", ""),) * bool(status), "link": link}


def _scot(*types):
    """Scotland's NatureScot files share these fields (`types`: more (field, label, format))."""
    return {"extra": (("PA_CODE", "Code", "int"), ("SITE_HA", "Area", "ha"), *types,
                      ("STATUS", "Status", "")), "link": "https://sitelink.nature.scot/site/{PA_CODE}"}


_SCOT_TYPE = ("TYPE", "Type", "sentence")
_JNCC = "https://sac.jncc.gov.uk/site/{sac_code}"


_AWI = ("ancientwoodland", "awi")
_CROW = (("crow", "access"), ("crowact2000", "access"), ("countrysiderightsofway", "access"))
_CROW_FLAGS = (("OC", "Open country"), ("RCL", "Registered common land"),
               ("S16", "Section 16 dedicated land"))
LAYER_SPECS = (
    _desig("sssi", ("sssi", "sitesofspecialscientificinterest"), "SSSI_NAME", "SSSI",
           England=_eng("ref_code", "measure", link=("https://designatedsites.naturalengland.org.uk/"
                                                      "SiteDetail.aspx?SiteCode=S{ref_code}")),
           Wales={"extra": (("sssi_code", "Code", ""), ("cartesian_", "Area", "ha"),
                            ("type", "Type", "sentence"), ("first_noti", "Notified", "date"),
                            ("confirmed", "Confirmed", "date"))},
           Scotland=_scot(_SCOT_TYPE)),
    _desig("sac", ("sac", "specialareasofconservation"), "SAC_NAME", "SAC",
           England=_eng("sac_code", "sac_area", "status", _JNCC), Scotland=_scot()),
    _desig("spa", ("spa", "specialprotectionareas"), "SPA_NAME", "SPA",
           England=_eng("spa_code", "spa_area", "status"), Scotland=_scot()),
    _desig("ramsar", ("ramsar",), "RAMSAR_NAME", "Ramsar",
           England=_eng("code", "area", "status"), Scotland=_scot()),
    _desig("nnr", ("nnr", "nationalnaturereserves"), "NNR_NAME", "NNR",
           England=_eng("ref_code", "measure"), Scotland=_scot()),
    _desig("lnr", ("lnr", "localnaturereserves"), "LNR_NAME", "LNR",
           Wales={"extra": (("authority", "Managed by", ""), ("cart_area", "Area", "ha"),
                            ("desig_data", "Designated", "date"))}),
    LayerSpec("ancient_woodland", (
        Part("England", tuple((w, "england") for w in _AWI), ("NAME",), ("THEMNAME", "THEME"),
             xform="ancient"),
        # Wales (NRW AWI 2021, checked 25 Oct 2026): no name field; category_n is the category
        Part("Wales", tuple((w, "wales") for w in _AWI), ("NAME", "WOOD_NAME"),
             ("CATEGORY_N", "CATEGORY", "AWI_CAT", "TYPE", "THEMNAME", "DESC_"), xform="ancient",
             extra=(("area_hecta", "Area", "ha"),)),
        # Scotland (checked 25 Oct 2026): ANTIQUITY holds Scotland's own three categories, kept as
        # they are ("Long-Established (of plantation origin)" is not PAWS)
        Part("Scotland", tuple((w, "scotland") for w in _AWI), ("NAME", "SITE_NAME"),
             ("ANTIQUITY", "CLASS", "CATEGORY", "DESC_", "TYPE"),
             extra=(("PARISH", "Parish", "sentence"), ("HECTARE", "Area", "ha")))),
        gb=(250, 500000), county=(25, 5000)),
    LayerSpec("wood_pasture", (
        Part("England", (("woodpasture",), ("wood", "pasture")), ("NAME",),
             ("MAINHABS", "MAIN_HABIT", "TYPE"),
             extra=(("areaha", "Area", "ha"), ("primsource", "Source", ""))),), gb=(250, 500000), county=(25, 5000)),
    LayerSpec("geology_bedrock", (
        Part("GB", (("625k", "bedrock"), ("625", "bedrock"), ("digmapgb625", "bedrock")),
             ("LEX_D", "LEX_RCS_D"), ("MAX_PERIOD",), need_name=True, xform="period",
             extra=(("RCS_D", "Rock type", "sentence"),), computed=(("age", "Age"),),
             exclude=("dyke", "fault", "linear", "mass", "superficial")),), gb=(200, 100000)),
    LayerSpec("geology_superficial", (
        Part("GB", (("625k", "superficial"), ("625", "superficial"), ("digmapgb625", "superficial")),
             (), ("LEX_D", "LEX_RCS_D"), xform="sentence", skip=("DRIFT GEOLOGY NOT MAPPED",),
             extra=(("ROCK_D", "Material", "sentence"),),
             exclude=("dyke", "fault", "linear", "mass")),), gb=(200, 100000)),
    LayerSpec("soil_pm", (
        Part("GB", (("soilparentmaterial",), ("soil", "parent", "material"), ("pmm", "1km")),
             (), ("SOIL_TEX",), xform="sentence", exclude=("50k",),
             extra=(("CARB_CNTNT", "Carbonate", "sentence"), ("SOIL_GROUP", "Soil group", "sentence"),
                    ("SOIL_DEPTH", "Depth", "sentence"), ("PMM_GRAIN", "Grain size", "sentence"),
                    ("ESB_DESC", "Parent material", "sentence"))),), dissolve=True),
    LayerSpec("soilscapes", (
        Part("England and Wales", (("soilscapes",), ("natmap",)),                  # (unverified)
             ("SOILSCAPE_DESC", "SOILSC_DES", "DESCRIPTION", "DESC_", "NAME"),
             ("SOILSCAPE", "SOILSC", "SOILSCAPE_"), prefix="Soilscape "),),
        gb=(250, 500000), county=(25, 5000)),
    LayerSpec("phi", (
        Part("England", (("priorityhabitat",), ("phi", "england")), (),
             ("MAIN_HABIT", "MAINHABS", "MAIN_HABS"), need_name=False,
             exclude=("woodpasture",)),),   # NE's wood-pasture file is named "...Priority_Habitat_Inventory..."
        gb=None, county=(40, 10000)),
    LayerSpec("nfi", (
        Part("GB", (("nfi",), ("nationalforestinventory",)), (), ("IFT_IOA", "IFT", "CATEGORY"),
             exclude=("openarea",)),), gb=None, county=(40, 20000)),
    LayerSpec("living_england", (
        Part("England", (("livingengland",), ("living", "england")), (),         # (unverified)
             ("PRIM_HAB", "PRIMARY_HAB", "PRIMARY_HABITAT", "HABITAT", "BHAB")),),
        gb=None, county=(40, 20000)),
    # NE's CRoW Access Layer (checked 25 Oct 2026) combines open country, registered common land
    # and Section 16 dedicated land, with a Yes/No field for each; common land comes from it too
    LayerSpec("crow_access", (
        Part("England", _CROW, (), fixed="Access land", flags=_CROW_FLAGS),),
        gb=(250, 500000), county=(25, 5000)),
    LayerSpec("common_land", (
        Part("England", _CROW, (), fixed="Registered common land", flags=(("RCL", ""),),
             only_flagged=True),), gb=(250, 500000), county=(25, 5000)),
)
SPEC_BY_KEY = {s.key: s for s in LAYER_SPECS}


@dataclass(frozen=True)
class GridSpec:
    key: str
    any_of: Tuple[Tuple[str, ...], ...]
    variable: str
    units: str
    label: str
    decimals: int
    scale: float
    offset: float
    exclude: Tuple[str, ...] = ("mon", "seas", "day", "djf", "mam", "jja", "son")


# HadUK-Grid 1991-2020 long-term averages, annual, 1 km (file names and variable names unverified)
GRID_SPECS = (
    GridSpec("haduk_rain", (("rainfall", "1km", "ann", "199101", "202012"),), "rainfall", "mm",
             "Mean annual rainfall", 0, 0.1, 0.0),
    GridSpec("haduk_temp", (("tas", "1km", "ann", "199101", "202012"),), "tas", "°C",
             "Mean annual temperature", 1, 0.01, -30.0),
    GridSpec("haduk_sun", (("sun", "1km", "ann", "199101", "202012"),), "sun", "hours",
             "Sunshine", 0, 0.1, 0.0),
    GridSpec("haduk_frost", (("groundfrost", "1km", "ann", "199101", "202012"),), "groundfrost",
             "days", "Ground frost", 0, 0.01, 0.0),
)
GRID_BY_KEY = {g.key: g for g in GRID_SPECS}


def words_of(rel_path: str):
    low = str(rel_path).lower()
    return set(re.split(r"[^a-z0-9]+", low)), re.sub(r"[^a-z0-9]", "", low)


def path_matches(rel_path, any_of, exclude=()) -> bool:
    words, squashed = words_of(rel_path)

    def has(tok):
        return tok in words if len(tok) <= 4 else tok in squashed
    return any(all(has(t) for t in alt) for alt in any_of) and not any(has(x) for x in exclude)


def find_files(source, any_of, exclude=(), exts=(".gpkg", ".shp")):
    """Files under `source` (a folder) with one of `exts` whose path matches; sorted."""
    src = Path(source)
    if not src.is_dir():
        return []
    return sorted(p for p in src.rglob("*") if p.suffix.lower() in exts
                  and path_matches(p.relative_to(src), any_of, exclude))


def pick_column(columns, candidates, last_resort=""):
    """The first of `candidates` present in `columns` (case ignored), else the first column whose
    name contains `last_resort`, else None."""
    low = {c.lower(): c for c in columns}
    for c in candidates:
        if c.lower() in low:
            return low[c.lower()]
    if last_resort:
        return next((c for c in columns if last_resort in c.lower()), None)
    return None


def is_flag_set(value) -> bool:
    """A Yes/No attribute (CRoW's OC / RCL / S16) is set."""
    return str(value or "").strip().lower() in ("yes", "y", "true", "1", "1.0")


def ancient_code(text: str) -> str:
    """The Ancient Woodland Inventory's category as its short code (ASNW / ARW / PAWS / AWSUC / RAWS);
    anything not recognised is kept as it is."""
    low = str(text or "").lower()
    if low.strip().upper() in ("ASNW", "PAWS", "ARW", "AWSUC", "RAWS"):
        return low.strip().upper()
    if "restored" in low:
        return "RAWS"           # Wales: Restored Ancient Woodland Site
    if "replant" in low:
        return "ARW"
    if "unknown" in low:
        return "AWSUC"
    if "semi" in low:
        return "ASNW"
    if "planted" in low or "plantation" in low:
        return "PAWS"
    return str(text or "").strip()
