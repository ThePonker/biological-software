"""The Mapping tab's Environment layers: the table of them (25 Oct 2026). Data only, no Qt.

Designated sites, habitat and woodland inventories, geology and soils, climate averages and
access land, from public data Wil downloads himself (docs/drafts/environment_layers_downloads.md)
and builds with scripts/build_env_layers.py into data/maps/layers/. layers.py turns these rows into
its Layer and Toggle entries (all off by default) and the Layers menu shows them under an
"Environment" sub-menu, one heading per `section`.

Each row: key, kind ("polygon", or "grid": a value grid, value_grid.py), the menu label, `short`
(what Identify calls it: "SSSI: Ashen Bank"), the menu section, the credits shown with the map when
the layer is drawn, where it sits in the stack (under the relief, after woodland, or on top) and
its colours (theme token names, see layers.env_style); the alpha is also the default opacity of
the Layers window's slider (geology and soils 75 %: their class colours are strong, 25 Oct 2026).

Soilscapes (Cranfield LandIS) is built, but its toggle stays hidden unless the setting
SOILSCAPES_SETTING is on: it needs a licence (data.gov.uk: "subject to a specific licensing agreement", commercial charges).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Tuple

GROUP = "Environment"
SOILSCAPES_SETTING = "mapping/allow_soilscapes"     # QSettings; layers.setting_on()
YEAR = date.today().year

OS_PART = f"Contains OS data © Crown copyright and database right {YEAR}."
# The OS sentence (OS_PART) is not repeated in these: layers.OS_CREDIT adds it once per page.
C_NE = "Contains Natural England data © Natural England copyright."
C_NRW = "Contains Natural Resources Wales information © Natural Resources Wales and database right."
C_NS = "Contains NatureScot information licensed under the Open Government Licence v3.0."
C_NS_AWI = f"Copyright NatureScot. Contains Ordnance Survey data © Crown copyright and database right {YEAR}."
# Living England Phase 4: the data.gov.uk attribution statement. Only its opening could be fetched
# (25 Oct 2026); the full statement is under "View full summary" at
# https://www.data.gov.uk/dataset/living-england-habitat-map-phase-4 : check it and complete this.
C_LE = ("Living England Habitat Map (Phase 4). Contains data supplied by © Natural England "
        "© Centre for Ecology and Hydrology, Natural England Licence No. 2011/052.")
C_BGS = f"Contains British Geological Survey materials © UKRI {YEAR}."
C_MET = ("Met Office HadUK-Grid (Hollis et al. 2018). Contains public sector information "
         "licensed under the Open Government Licence v3.0.")
C_FC = (f"© Forestry Commission copyright and/or database right {YEAR}. Contains public sector "
        "information licensed under the Open Government Licence v3.0.")
C_LANDIS = f"Soilscapes © Cranfield University (NSRI) and for the Controller of HMSO {YEAR}."

# too big for a GB-wide file: built at county detail only, and not drawn (or identified) in the
# GB view (layers.file_path)
COUNTY_ONLY = ("phi", "nfi", "living_england")
UNDER, MID, TOP = "under", "mid", "top"     # under the relief / after woodland / after national parks


@dataclass(frozen=True)
class EnvLayer:
    key: str
    kind: str                       # "polygon" or "grid"
    label: str                      # the Layers menu
    short: str                      # Identify's name for it
    section: str                    # the sub-menu's heading
    credits: Tuple[str, ...]
    place: str                      # UNDER, MID or TOP
    style: Tuple = ()               # polygon: (theme token, theme token, mix 0-1, alpha); grid: stops
    hidden_unless: str = ""         # a QSettings key that must be on for the toggle to show


DESIG, HAB, GEO, CLIM, ACC = ("Designated sites", "Woodland and habitats", "Geology and soils",
                              "Climate, 1991–2020 averages", "Access land")
_ALL3 = (C_NE, C_NRW, C_NS)
_AWI = (C_NE, C_NRW, C_NS_AWI)      # NatureScot's inventory is under the OS Open Data licence, not the OGL

ENV_LAYERS = (
    EnvLayer("haduk_rain", "grid", "Rainfall, annual total", "Mean annual rainfall", CLIM,
             (C_MET,), UNDER, ("CARD", "SEA", "SLATE")),
    EnvLayer("haduk_temp", "grid", "Temperature, annual mean", "Mean annual temperature", CLIM,
             (C_MET,), UNDER, ("SEA", "GOLD", "CLAY")),
    EnvLayer("haduk_sun", "grid", "Sunshine, annual hours", "Sunshine", CLIM,
             (C_MET,), UNDER, ("CARD", "GOLD")),
    EnvLayer("haduk_frost", "grid", "Ground frost, days a year", "Ground frost", CLIM,
             (C_MET,), UNDER, ("CARD", "SEA", "SLATE")),
    EnvLayer("soilscapes", "polygon", "Soilscapes (LandIS)", "Soilscape", GEO,
             (C_LANDIS,), UNDER, ("CLAY", "GOLD", 0.5, 255), SOILSCAPES_SETTING),
    EnvLayer("soil_pm", "polygon", "Soil parent material (BGS, 1 km)", "Soil parent material", GEO,
             (C_BGS,), UNDER, ("CLAY", "MUTED", 0.5, 190)),
    EnvLayer("geology_bedrock", "polygon", "Bedrock geology (BGS 625k)", "Bedrock", GEO,
             (C_BGS,), UNDER, ("GOLD", "CLAY", 0.4, 190)),
    EnvLayer("geology_superficial", "polygon", "Superficial deposits (BGS 625k)", "Superficial", GEO,
             (C_BGS,), UNDER, ("SLATE", "GOLD", 0.3, 190)),
    EnvLayer("living_england", "polygon", "Living England habitat map", "Habitat (Living England)",
             HAB, (C_LE,), UNDER, ("GOLD", "MOSS", 0.5, 255)),
    EnvLayer("nfi", "polygon", "National Forest Inventory", "Forest type", HAB,
             (C_FC,), MID, ("MOSS", "MUTED", 0.4, 255)),
    EnvLayer("phi", "polygon", "Priority Habitat Inventory", "Priority habitat", HAB,
             (C_NE,), MID, ("MOSS", "SLATE", 0.4, 255)),
    EnvLayer("wood_pasture", "polygon", "Wood-pasture and parkland", "Wood-pasture", HAB,
             (C_NE,), MID, ("GOLD", "MOSS", 0.6, 255)),
    EnvLayer("ancient_woodland", "polygon", "Ancient Woodland Inventory", "Ancient woodland", HAB,
             _AWI, MID, ("MOSS_HOVER", "MUTED", 0.2, 255)),
    EnvLayer("crow_access", "polygon", "CRoW access land", "Access land", ACC,
             (C_NE,), TOP, ("GOLD", "MOSS", 0.2, 120)),
    EnvLayer("common_land", "polygon", "Registered common land", "Common land", ACC,
             (C_NE,), TOP, ("MOSS", "GOLD", 0.5, 120)),
    EnvLayer("lnr", "polygon", "Local Nature Reserves (LNR)", "LNR", DESIG,
             _ALL3, TOP, ("GOLD", "MOSS", 0.5, 110)),
    EnvLayer("nnr", "polygon", "National Nature Reserves (NNR)", "NNR", DESIG,
             _ALL3, TOP, ("MOSS_HOVER", "MOSS", 0.0, 110)),
    EnvLayer("ramsar", "polygon", "Ramsar sites", "Ramsar", DESIG,
             _ALL3, TOP, ("SLATE", "MOSS", 0.5, 110)),
    EnvLayer("spa", "polygon", "Special Protection Areas (SPA)", "SPA", DESIG,
             _ALL3, TOP, ("CLAY", "MUTED", 0.4, 110)),
    EnvLayer("sac", "polygon", "Special Areas of Conservation (SAC)", "SAC", DESIG,
             _ALL3, TOP, ("SLATE", "MUTED", 0.0, 110)),
    EnvLayer("sssi", "polygon", "Sites of Special Scientific Interest (SSSI)", "SSSI", DESIG,
             _ALL3, TOP, ("MOSS", "SLATE", 0.2, 110)),
)
ENV_BY_KEY = {e.key: e for e in ENV_LAYERS}
