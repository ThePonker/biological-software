"""25 Oct 2026: build_env_layers.py adjusted after a look at the real downloads: BGS's GeoPackage
(its own srs id for the British National Grid, four tables in one file), NRW's and NatureScot's
ancient woodland categories, the wood-pasture file's name, and CRoW's Yes/No flags (common land
taken from the access layer). Small made-up GeoPackages; nothing from Wil's data."""
import json
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("shapely")
from shapely.geometry import box  # noqa: E402

from scripts import build_env_layers as be  # noqa: E402
from scripts.env_sources import ancient_code  # noqa: E402
from tests.test_build_map_layers import make_gpkg  # noqa: E402

A, B = box(10000, 10000, 30000, 30000), box(50000, 50000, 80000, 80000)
BNG_WKT = ('PROJCS["OSGB36 / British National Grid",GEOGCS["OSGB36",DATUM["Ordnance_Survey_of_'
           'Great_Britain_1936",SPHEROID["Airy 1830",6377563.396,299.3249646]]],PROJECTION['
           '"Transverse_Mercator"],PARAMETER["False_Easting",400000],PARAMETER["False_Northing",'
           '-100000],UNIT["metre",1]]')
WGS_WKT = 'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]]]'


def _srs(path, srs_id, wkt):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE gpkg_spatial_ref_sys (srs_id INT, definition TEXT)")
    c.execute("INSERT INTO gpkg_spatial_ref_sys VALUES (?, ?)", (srs_id, wkt))
    c.commit()
    c.close()


def _run(capsys, src, out, *args):
    code = be.main(["--source", str(src), "--out", str(out), *args])
    return code, capsys.readouterr().out


def _feats(out, key):
    return json.loads((out / f"{key}_county.json").read_text(encoding="utf-8"))["features"]


def _bgs(tmp_path, srs_id, wkt):
    root = tmp_path / "Environment data"
    f = root / "BGS 625k bedrock" / "625k_V5_Geology_UK_EPSG27700.gpkg"
    f.parent.mkdir(parents=True)
    cols = "LEX_D TEXT, RCS_D TEXT, "
    make_gpkg(f, {"g625k_V5_DYKES_Geology": (cols, [(A, "Dyke", "Dolerite")]),
                  "g625k_V5_BEDROCK_Geology": (cols, [(B, "Chalk Group", "Chalk")]),
                  "g625k_V5_FAULTS": (cols, [(A, "Fault", "-")])}, srs=srs_id)
    _srs(f, srs_id, wkt)
    return root


def test_bgs_gpkg_with_its_own_bng_srs_id_builds_the_bedrock_table(tmp_path, capsys):
    root, out = _bgs(tmp_path, 100000, BNG_WKT), tmp_path / "out"
    code, text = _run(capsys, root, out, "--only", "geology_bedrock", "--apply")
    assert code == 0, text
    assert "table g625k_V5_BEDROCK_Geology" in text
    assert [(f["n"], f["t"]) for f in _feats(out, "geology_bedrock")] == [("Chalk Group", "Undifferentiated")]   # no MAX_PERIOD in this made-up file


def test_a_custom_srs_id_that_is_not_bng_is_still_refused(tmp_path, capsys):
    root, out = _bgs(tmp_path, 100000, WGS_WKT), tmp_path / "out"
    code, text = _run(capsys, root, out, "--only", "geology_bedrock", "--apply")
    assert code == 1 and "refused" in text and "100000" in text
    assert not list(out.glob("*.json"))


def test_ancient_woodland_wales_and_scotland_categories(tmp_path, capsys):
    root = tmp_path / "Environment data"
    w = root / "Ancient Woodland Wales" / "NRW_ANCIENT_WOODLAND_INVENTORY_2021.gpkg"
    s = root / "Ancient Woodland Scotland" / "AWI_SCOTLAND.gpkg"
    w.parent.mkdir(parents=True)
    s.parent.mkdir(parents=True)
    make_gpkg(w, {"awi": ("category_n TEXT, ", [
        (A, "Ancient Semi Natural Woodland"), (B, "Restored Ancient Woodland Site"),
        (box(0, 0, 9000, 9000), "Plantation on Ancient Woodland Site Deleted")])})
    make_gpkg(s, {"awi": ("SITE_NAME TEXT, ANTIQUITY TEXT, ", [
        (A, "Big Wood", "Long-Established (of plantation origin)")])})
    out = tmp_path / "out"
    code, text = _run(capsys, root, out, "--only", "ancient_woodland", "--apply")
    assert code == 0, text
    got = sorted(f["t"] for f in _feats(out, "ancient_woodland"))
    assert got == ["ASNW", "Long-Established (of plantation origin)", "RAWS"]   # Deleted left out


def test_ancient_code_restored_is_raws():
    assert ancient_code("Restored Ancient Woodland Site") == "RAWS"
    assert ancient_code("Ancient Replanted Woodland") == "ARW"
    assert ancient_code("Plantation on Ancient Woodland Site") == "PAWS"


def test_wood_pasture_file_is_not_taken_as_the_priority_habitat_inventory(tmp_path, capsys):
    root = tmp_path / "Environment data"
    f = root / "Wood-pasture England" / \
        "Wood_Pasture_and_Parkland_BAP_Priority_Habitat_Inventory_for_England.gpkg"
    f.parent.mkdir(parents=True)
    make_gpkg(f, {"wpp": ("mainhabs TEXT, ", [(A, "Wood pasture and parkland")])})
    code, text = _run(capsys, root, tmp_path / "o", "--only", "phi,wood_pasture")
    assert "phi / England: not found" in text
    assert "wood_pasture / England: Wood_Pasture" in text and "class field mainhabs" in text


def test_crow_flags_label_access_land_and_make_common_land(tmp_path, capsys):
    root = tmp_path / "Environment data"
    f = root / "CRoW Access England" / \
        "Countryside_and_Rights_of_Way_Act_2000_Access_Layer_England.gpkg"
    f.parent.mkdir(parents=True)
    make_gpkg(f, {"crow": ("descrip TEXT, oc TEXT, rcl TEXT, s16 TEXT, ", [
        (A, "Access Land - Combined", "Yes", "No", "No"),
        (B, "Access Land - Combined", "Yes", "Yes", "No"),
        (box(0, 0, 9000, 9000), "Access Land - Combined", "No", "No", "No")])})
    out = tmp_path / "out"
    code, text = _run(capsys, root, out, "--only", "crow_access,common_land", "--apply")
    assert code == 0, text
    assert "flags oc, rcl, s16" in text
    assert sorted(f["t"] for f in _feats(out, "crow_access")) == [
        "Access land", "Open country", "Open country + Registered common land"]
    common = _feats(out, "common_land")
    assert [f["t"] for f in common] == ["Registered common land"]      # only the rcl = Yes row


def test_common_land_refused_when_the_flag_field_is_missing(tmp_path, capsys):
    root = tmp_path / "Environment data"
    f = root / "CRoW Access England" / "CRoW_access.gpkg"
    f.parent.mkdir(parents=True)
    make_gpkg(f, {"crow": ("descrip TEXT, ", [(A, "Access land")])})
    code, text = _run(capsys, root, tmp_path / "o", "--only", "common_land", "--apply")
    assert code == 1 and "none of the fields ['RCL']" in text
