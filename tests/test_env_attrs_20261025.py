"""Details ("a"), links ("u") and the geology / soil classes of the Environment layers (25 Oct 2026)."""
import json

import pytest

pytest.importorskip("shapely")
from shapely.geometry import box  # noqa: E402

from scripts import build_env_layers as be  # noqa: E402
from scripts import env_attrs  # noqa: E402
from shared.maps import env_classes  # noqa: E402
from tests.test_build_map_layers import make_gpkg  # noqa: E402

A = box(10000, 10000, 30000, 30000)
B = box(50000, 50000, 70000, 70000)
C = box(30000, 10000, 50000, 30000)       # touches A


def _build(tmp_path, capsys, folder, table, cols, rows, key):
    root = tmp_path / "Environment data"
    f = root / folder / "x.gpkg"
    f.parent.mkdir(parents=True)
    make_gpkg(f, {table: (cols, rows)})
    out = tmp_path / "out"
    code = be.main(["--source", str(root), "--out", str(out), "--only", key, "--apply"])
    text = capsys.readouterr().out
    assert code == 0, text
    return json.loads((out / f"{key}_county.json").read_text(encoding="utf-8"))["features"], text


BED = "LEX_D TEXT, RCS_D TEXT, MAX_PERIOD TEXT, MIN_PERIOD TEXT, MAX_ERA TEXT, "


def test_bedrock_period_class_and_age(tmp_path, capsys):
    rows = [(A, "Lias Group", "MUDSTONE", "JURASSIC", "JURASSIC", "MESOZOIC"),
            (B, "Mercia Group", "MUDSTONE", "TRIASSIC", "JURASSIC", "MESOZOIC"),
            (C, "Old thing", "SCHIST", "UNDIFF", None, "NEOPROTEROZOIC")]
    feats, text = _build(tmp_path, capsys, "BGS 625k bedrock", "geo", BED, rows, "geology_bedrock")
    by = {f["n"]: f for f in feats}
    assert by["Lias Group"]["t"] == "Jurassic"
    assert by["Lias Group"]["a"] == [["Rock type", "Mudstone"], ["Age", "Jurassic"]]
    assert by["Mercia Group"]["a"][1] == ["Age", "Triassic to Jurassic"]
    assert by["Old thing"]["t"] == "Precambrian" and by["Old thing"]["a"][1] == ["Age", "Undiff"]
    assert "details rock type, age" in text


def test_period_class_fallbacks():
    assert env_attrs.period_class("silurian", "PALAEOZOIC") == "Silurian"
    assert env_attrs.period_class("UNDIFF", "PALAEOZOIC") == "Palaeozoic (period not given)"
    assert env_attrs.period_class(None, "MESOZOIC") == "Mesozoic (period not given)"
    assert env_attrs.period_class("", "CAINOZOIC") == "Cainozoic (period not given)"
    assert env_attrs.period_class("UNDIFF", "UNDIFF") == "Undifferentiated"
    assert env_attrs.period_class("", "") == "Undifferentiated"
    assert env_attrs.age_text("JURASSIC", "") == "Jurassic"


def test_superficial_class_and_unmapped_rows_left_out(tmp_path, capsys):
    rows = [(A, "TILL", "DIAMICTON"), (B, "DRIFT GEOLOGY NOT MAPPED", "NONE"),
            (C, "RIVER TERRACE DEPOSITS (UNDIFFERENTIATED)", "SAND AND GRAVEL")]
    feats, _ = _build(tmp_path, capsys, "BGS 625k superficial", "sup", "LEX_D TEXT, ROCK_D TEXT, ",
                      rows, "geology_superficial")
    assert sorted(f["t"] for f in feats) == ["River terrace deposits (undifferentiated)", "Till"]
    assert all("n" not in f for f in feats)
    assert {f["t"]: f["a"] for f in feats}["Till"] == [["Material", "Diamicton"]]
    assert {f["t"] for f in feats} <= set(env_classes.SUPERFICIAL)


SOIL = "SOIL_TEX TEXT, CARB_CNTNT TEXT, SOIL_GROUP TEXT, SOIL_DEPTH TEXT, PMM_GRAIN TEXT, ESB_DESC TEXT, "


def test_soil_class_sentence_case_details_and_dissolve(tmp_path, capsys):
    rows = [(A, "CLAYEY LOAM TO SANDY LOAM", "CARBONATE-RICH", "NA", "DEEP", "FINE", "CHALK"),
            (C, "CLAYEY LOAM TO SANDY LOAM", "CARBONATE-RICH", "NA", "DEEP", "FINE", "CHALK"),
            (B, "CLAYEY LOAM TO SANDY LOAM", "NON-CALCAREOUS", "NA", "DEEP", "FINE", "CHALK")]
    feats, _ = _build(tmp_path, capsys, "Soil parent material", "soil", SOIL, rows, "soil_pm")
    assert len(feats) == 2                       # A and C joined; B has different details
    assert {f["t"] for f in feats} == {"Clayey loam to sandy loam"}
    assert {f["t"] for f in feats} <= set(env_classes.SOIL_TEXTURE)
    for f in feats:
        assert "n" not in f
        assert all(lab != "Soil group" for lab, _t in f["a"])      # NA omitted
    assert sorted(dict(f["a"])["Carbonate"] for f in feats) == ["Carbonate-rich", "Non-calcareous"]
    assert ["Parent material", "Chalk"] in feats[0]["a"]


def test_designation_formats_and_link(tmp_path, capsys):
    cols = "SSSI_NAME TEXT, REF_CODE TEXT, MEASURE REAL, "
    rows = [(A, "Ashen Bank", "1006159", 84.44), (B, "No Code", "", 3.0)]
    feats, _ = _build(tmp_path, capsys, "SSSI England", "s", cols, rows, "sssi")
    by = {f["n"]: f for f in feats}
    assert by["Ashen Bank"]["a"] == [["Code", "1006159"], ["Area", "84.4 ha"]]
    assert by["Ashen Bank"]["u"] == \
        "https://designatedsites.naturalengland.org.uk/SiteDetail.aspx?SiteCode=S1006159"
    assert "u" not in by["No Code"] and by["No Code"]["a"] == [["Area", "3.0 ha"]]


def test_date_int_and_sentence_formats():
    f = env_attrs.format_value
    assert f("20170329", "date") == "29 Mar 2017" and f(20170329.0, "date") == "29 Mar 2017"
    assert f("00000000", "date") == "" and f("", "date") == "" and f("junk", "date") == ""
    assert f(1426.0, "int") == "1426" and f("84.44", "ha") == "84.4 ha"
    assert f("SPECIAL AREA (LOW)", "sentence") == "Special area (low)"


def test_wales_dates_and_scotland_link(tmp_path, capsys):
    root = tmp_path / "Environment data"
    w, s = root / "SSSI Wales" / "w.gpkg", root / "SSSI Scotland" / "s.gpkg"
    w.parent.mkdir(parents=True)
    s.parent.mkdir(parents=True)
    make_gpkg(w, {"w": ("SSSI_NAME TEXT, first_noti TEXT, type TEXT, ", [(A, "Cors", "19510101", "BIOLOGICAL")])})
    make_gpkg(s, {"s": ("SITE_NAME TEXT, PA_CODE REAL, ", [(B, "Loch", 1426.0)])})
    out = tmp_path / "out"
    assert be.main(["--source", str(root), "--out", str(out), "--only", "sssi", "--apply"]) == 0
    capsys.readouterr()
    by = {f["n"]: f for f in json.loads((out / "sssi_county.json").read_text())["features"]}
    assert by["Cors"]["a"] == [["Type", "Biological"], ["Notified", "1 Jan 1951"]]
    assert by["Loch"]["a"] == [["Code", "1426"]] and by["Loch"]["u"] == "https://sitelink.nature.scot/site/1426"


def test_missing_extra_fields_are_skipped_not_refused(tmp_path, capsys):
    feats, text = _build(tmp_path, capsys, "SSSI England", "s", "SSSI_NAME TEXT, ", [(A, "X")], "sssi")
    assert feats[0] == {**feats[0], "n": "X", "t": "SSSI"} and "a" not in feats[0] and "u" not in feats[0]
    assert "details" not in text
