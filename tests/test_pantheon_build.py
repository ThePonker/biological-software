"""build_pantheon_db.py (backlog D5, fault F26): species without a TVK keep their own data."""
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "scripts")]
import build_pantheon_db as bp  # noqa: E402

HT = ("SpeciesTraitID,SpeciesName,SpeciesTVK,PreferredName,PreferredTVK,Family,TraitID,TraitName,"
      "TraitType,TraitValue,ParentTraitID,ResourceHeading\n"
      "1,Abax parallelus,NBNSYS0000007303,Abax parallelus,NBNSYS0000007303,Carabidae,38,SQS,rarity score,1,,\n"
      "2,Abax parallelus,NBNSYS0000007303,Abax parallelus,NBNSYS0000007303,Carabidae,250,tall sward & scrub,habitat,,249,\n"
      "3,Ochlerotatus communis,,Aedes communis,NBNSYS0000011578,Culicidae,38,SQS,rarity score,4,,\n"
      "4,Ochlerotatus communis,,Aedes communis,NBNSYS0000011578,Culicidae,38,SQS,rarity score,8,,\n"
      "5,,,Acnemia amoena,NBNSYS0000005500,Mycetophilidae,251,wetland,broad biotope,,,\n"
      "6,Acalypta platychila,,Acalypta platycheila,NHMSYS0020308883,Tingidae,38,SQS,rarity score,16,,\n")
CS = ("SpeciesName,SpeciesTVK,PreferredName,PreferredTVK,ReportingCategory,Designation,DesignationAbbreviation\n"
      "Ochlerotatus communis,,Aedes communis,NBNSYS0000011578,GB Status,Notable,N\n")
AS = ("AssociationID,SpeciesName,SpeciesTVK,PreferredName,PreferredTVK,Family,AssociatedTreeType,"
      "AssociatedTaxaType,AssociatedTaxa\n"
      '9,Abax parallelus,NBNSYS0000007303,Abax parallelus,NBNSYS0000007303,Carabidae,,animal,"Tipula\r\n\r\n"\n')


def _csvs(tmp_path):
    for name, text in ((bp.HT, HT), (bp.CS, CS), (bp.AS, AS)):
        (tmp_path / name).write_bytes(text.encode("utf-8"))
    return str(tmp_path)


def test_species_without_tvk_are_keyed_on_name(tmp_path):
    out = str(tmp_path / "p.db")
    bp.build(out, _csvs(tmp_path), log=lambda *a: None)
    c = sqlite3.connect(out)
    keys = {r[0] for r in c.execute("SELECT tvk FROM species")}
    assert keys == {"NBNSYS0000007303", "NOTVK:Ochlerotatus communis", "NOTVK:Acnemia amoena",
                    "NOTVK:Acalypta platychila"}
    assert "" not in keys
    # a row that gives only the preferred name takes it as its species name
    assert c.execute("SELECT species_name FROM species WHERE tvk='NOTVK:Acnemia amoena'").fetchone()[0] \
        == "Acnemia amoena"
    sqs = dict(c.execute("SELECT tvk, sqs FROM sqs_scores"))
    assert sqs["NOTVK:Ochlerotatus communis"] == 4          # first row wins
    assert sqs["NOTVK:Acalypta platychila"] == 16           # no longer lost to another species
    assert c.execute("SELECT tvk FROM conservation_status").fetchone()[0] == "NOTVK:Ochlerotatus communis"
    assert c.execute("SELECT associated_taxa FROM associations").fetchone()[0] == "Tipula\n\n"


def test_legacy_mode_reproduces_the_old_blank_key(tmp_path):
    out = str(tmp_path / "p.db")
    bp.build(out, _csvs(tmp_path), legacy_blank_key=True, log=lambda *a: None)
    c = sqlite3.connect(out)
    assert {r[0] for r in c.execute("SELECT tvk FROM species")} == {"NBNSYS0000007303", ""}
    assert dict(c.execute("SELECT tvk, sqs FROM sqs_scores"))[""] == 4


def test_build_refuses_to_overwrite(tmp_path):
    out = tmp_path / "p.db"
    out.write_bytes(b"x")
    try:
        bp.build(str(out), _csvs(tmp_path), log=lambda *a: None)
    except FileExistsError:
        return
    raise AssertionError("build overwrote an existing file")
