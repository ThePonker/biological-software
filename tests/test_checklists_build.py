"""scripts/build_checklists.py + checklist_parsers.py: the parsers on a few synthetic lines
per format, the UKSI resolver on known renames, and (when present) the built CSVs.
Fast: no PDF is opened; UKSI / CSV tests skip cleanly when the files are absent."""
import csv
import os
import sqlite3

import pytest

import paths
from scripts import build_checklists as B
from scripts import checklist_parsers as P
from scripts.checklist_parsers import Line
from shared import checklist_order

R, BI, I, BO = "Arial", "Arial,BoldItalic", "Arial,Italic", "Arial,Bold"


def L(words, x0=54.0, size=9.0, page=10, col=0):
    return Line(page, col, x0, size, [tuple(w) for w in words])


def _w(text, font):
    return [(t, font) for t in text.split()]


# ------------------------------------------------------------------ parsers

def test_duff_accepted_species_only():
    lines = [
        L(_w("19. Family SILPHIDAE Latreille, 1807", BO)),
        L(_w("Family author: R.G. Booth", I)),
        L(_w("NICROPHORUS", BO) + _w("Fabricius, 1775", R)),
        L(_w("humator", BI) + _w("(Gleditsch, 1767)", R)),
        L(_w("vespillo", BI) + _w("(Linnaeus, 1758)", R)),
        L(_w("vulgaris", I) + _w("sensu auctt. non Fabricius", R), x0=71),     # synonym
        L(_w("SILPHA", BO) + _w("Linnaeus, 1758", R)),
        L(_w("Subgenus", R) + _w("PHOSPHUGA", R) + _w("Leach, 1817", R)),
        L(_w("atrata", BI) + _w("Linnaeus, 1758", R)),
        L(_w("the subfamily is", BI) + _w("now treated", R)),                  # prose, no author
    ]
    rows = P.parse_duff(lines)
    assert [r["listed"] for r in rows] == ["Nicrophorus humator", "Nicrophorus vespillo",
                                           "Silpha atrata"]
    assert rows[0]["family"] == "Silphidae"
    assert rows[2]["subgenus"] == "Phosphuga"


def test_diptera_skips_notes_and_synonyms():
    F1, F2 = "CIDFont+F1", "CIDFont+F2"
    lines = [
        L(_w("TIPULIDAE (1998 87, no change)", F2), x0=86, size=11.3),
        L(_w("CTENOPHORINAE", F1), x0=86, size=8.5),
        L(_w("CTENOPHORA", F2) + _w("Meigen, 1803", F1), x0=86, size=8.5),
        L(_w("pectinicornis", F2) + _w("(Linnaeus, 1758 – Tipula) +", F1), x0=86, size=8.5),
        L(_w("splendor", F1) + _w("(Harris, 1776 – Tipula)", F1), x0=92, size=8.5),
        L(_w("Nomina dubia", F1), x0=86, size=8.5),
        L(_w("dubia", F2) + _w("Meigen, 1830", F1), x0=86, size=8.5),
    ]
    rows = P.parse_diptera(lines)
    assert [(r["family"], r["listed"]) for r in rows] == [("Tipulidae",
                                                           "Ctenophora pectinicornis")]


def test_lepidoptera_code_and_bullet_marks():
    BB, BBI, BK = "FreightTextProBold-Regular", "FreightTextProBold-Italic", "FreightTextProBook"
    lines = [
        L(_w("GEOMETRIDAE", BB), x0=74, size=13),
        L([("•", "TimesNewRomanPSMT")] + _w("IDAEA", BB) + _w("Treitschke, 1825", BK), x0=33),
        L(_w("70.001", BK) + _w("serpentata", BBI) + _w("(Hufnagel, 1767)", BK), x0=40),
        L(_w("aureolaria", "FreightTextProBook-Italic") + _w("(Denis, 1775)", BK), x0=94),
        L([("○", "TimesNewRomanPSMT")] + _w("70.002", BK) + _w("muricata", BBI), x0=32),
        L(_w("APPENDIX A", BB)),
        L(_w("99.001", BK) + _w("ignored", BBI), x0=40),
    ]
    rows = P.parse_lepidoptera(lines)
    assert [(r["code"], r["listed"]) for r in rows] == [("70.001", "Idaea serpentata"),
                                                        ("70.002", "Idaea muricata")]


def test_spiders_and_aculeates():
    TI, TR = "TimesNRMT-Italic", "TimesNRMT"
    rows = P.parse_spiders([
        L(_w("Family THERIDIIDAE", TR), size=10),
        L(_w("Steatoda bipunctata", TI) + _w("(Linnaeus, 1758)", TR), size=10),
        L(_w("[ Theridion bipunctatum Linnaeus]", TR), size=8),
        L(_w("Orchestina sp.?", TI), size=10),
    ])
    assert [r["listed"] for r in rows] == ["Steatoda bipunctata"]
    TB, TBI, H = "TrebuchetMS-Bold", "Trebuchet-BoldItalic", "TeXGyreHeros-Italic"
    rows = P.parse_aculeates([
        L(_w("Family Andrenidae", TB) + _w("Latreille, 1802", TB)),
        L(_w("Andrena", TBI) + [("(Andrena)", TB)] + _w("fulva", TBI) + _w("(Müller, 1766)", TB)),
        L(_w("Apis fulva", H) + _w("Müller, 1766", "TeXGyreHeros-Regular"), x0=97),
    ])
    assert [(r["listed"], r["subgenus"]) for r in rows] == [("Andrena fulva", "Andrena")]


def test_britishbugs_pages():
    het = "\n".join(["RS", "Current name", "Family", "S", "Cyphostethus tristriatus",
                     "Elasmostethus tristriatus", "(Fabricius 1787)", "Juniper Shieldbug",
                     "Acanthosomatidae", "LC", "W", "Velia caprai", "Tamanini 1947",
                     "Veliidae", "LC"])
    rows = P.parse_heteroptera_text(het)
    assert [(r["listed"], r["family"], r["group"]) for r in rows] == [
        ("Cyphostethus tristriatus", "Acanthosomatidae", "S"), ("Velia caprai", "Veliidae", "W")]
    auc = "\n".join(["Oncopsis avellanae", "Edwards 1920", "Cicadellidae", "Macropsinae",
                     "Oncopsis carpini", "(J.Sahlberg 1871)", "Cicadellidae", "Macropsinae",
                     "Ireland only", "Aphrophora pectoralis", "Aphrophora forneri",
                     "Matsumura 1903", "Aphrophoridae", "Aphrophorinae", "Common"])
    rows = P.parse_auchenorrhyncha_text(auc)
    assert [r["listed"] for r in rows] == ["Oncopsis avellanae", "Oncopsis carpini",
                                           "Aphrophora pectoralis"]


# ------------------------------------------------------------------ resolver

def test_spelling_helpers():
    assert "nigra" in B.gender_variants("niger") or "nigrum" in B.gender_variants("niger")
    assert B._edits("heerii", "heeri") == 1
    assert B._close("pastinaceae", "pastinacae")
    assert not B._close("atrata", "atrata")


@pytest.fixture(scope="module")
def uksi():
    p = str(paths.UKSI_DB)
    if not os.path.exists(p):
        pytest.skip("no uksi.db")
    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    yield conn
    conn.close()


def test_resolver_known_renames(uksi):
    col = B.Resolver(uksi, "Coleoptera")
    tvk, how = col.resolve("Silpha", "atrata", "Phosphuga")
    assert col.name(tvk)[0] == "Phosphuga atrata" and how == "synonym"
    tvk, how = col.resolve("Aphodius", "rufipes", "Acrossus")
    assert col.name(tvk) == ("Acrossus rufipes", "Scarabaeidae")
    tvk, how = col.resolve("Nicrophorus", "humator")
    assert how == "exact" and col.name(tvk)[1] == "Silphidae"
    assert col.resolve("Abax", "notarealepithet")[0] is None
    het = B.Resolver(uksi, "Hemiptera")
    tvk, how = het.resolve("Psallus", "anaemicus")       # UKSI: "Psallus (Psallus) anaemicus"
    assert how == "exact"


def test_resolve_rows_keeps_order_and_drops_duplicates(uksi):
    rows = [P._row("Silphidae", "Nicrophorus", "humator"), P._row("Silphidae", "Silpha", "atrata"),
            P._row("Silphidae", "Phosphuga", "atrata")]
    out, stats = B.resolve_rows(rows, B.Resolver(uksi, "Coleoptera"), "test")
    assert [r["species"] for r in out] == ["Nicrophorus humator", "Phosphuga atrata"]
    assert out[1]["name_as_listed"] == "Silpha atrata" and stats["duplicate"] == 1
    assert set(out[0]) == set(B.FIELDS)


# ------------------------------------------------------------------ the built files

def test_built_csvs_load_and_place_silphids():
    folder = checklist_order.DEFAULT_DIR
    path = os.path.join(folder, "10_coleoptera.csv")
    if not os.path.exists(path):
        pytest.skip("checklists not built on this PC")
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows and set(B.FIELDS) <= set(rows[0])
    fam = {r["species"]: r["family"] for r in rows}
    assert fam.get("Phosphuga atrata") == "Silphidae"
    cl = checklist_order.load(folder)
    names = ("Nicrophorus humator", "Phosphuga atrata", "Necrodes littoralis")
    specs = [{"order_name": "Coleoptera", "family": "Silphidae", "species_name": n,
              "genus": n.split()[0]} for n in names]
    assert [s["species_name"] for s in checklist_order.reorder(specs, cl)] == [
        "Necrodes littoralis", "Phosphuga atrata", "Nicrophorus humator"]   # Duff: Silphinae first
