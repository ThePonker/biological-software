"""scripts/plan_photo_consolidation.py (B1 dry run, 13 Oct 2026) on a purpose-made library
check CSV and UKSI: where each specimen photo would go. Nothing is moved."""
import csv
import sqlite3

from scripts import plan_photo_consolidation as pc

INS = "Photos/Life/Animalia/Arthropoda/Hexapoda/Insecta"
SPI = "Photos/Life/Animalia/Arthropoda/Chelicerata/Arachnida/Araneae"
COLS = ["rel_path", "kind", "size_bytes", "match_status", "uksi_name", "tvk"]


def _uksi(path):
    c = sqlite3.connect(path)
    c.execute('CREATE TABLE taxa (tvk TEXT, scientific_name TEXT, rank TEXT, parent_tvk TEXT, '
              '"order" TEXT, family TEXT)')
    c.executemany("INSERT INTO taxa VALUES (?,?,?,?,?,?)", [
        ("O1", "Coleoptera", "Order", None, "Coleoptera", None),
        ("F1", "Carabidae", "Family", "O1", "Coleoptera", "Carabidae"),
        ("S1", "Carabus nemoralis", "Species", "F1", "Coleoptera", "Carabidae"),
        ("S2", "Abax parallelepipedus", "Species", "F1", "Coleoptera", "Carabidae"),
        ("F2", "Silphidae", "Family", "O1", "Coleoptera", "Silphidae"),
        ("S3", "Silpha atrata", "Species", "F2", "Coleoptera", "Silphidae"),
        ("O2", "Hemiptera", "Order", None, "Hemiptera", None),
        ("SO", "Heteroptera", "Suborder", "O2", "Hemiptera", None),
        ("F3", "Pentatomidae", "Family", "SO", "Hemiptera", "Pentatomidae"),
        ("F4", "Coreidae", "Family", "SO", "Hemiptera", "Coreidae"),
        ("S4", "Coreus marginatus", "Species", "F4", "Hemiptera", "Coreidae"),
        ("F5", "Scutelleridae", "Family", "O2", "Hemiptera", "Scutelleridae"),
        ("S5", "Eurygaster testudinaria", "Species", "F5", "Hemiptera", "Scutelleridae"),
        ("F6", "Linyphiidae", "Family", None, "Araneae", "Linyphiidae"),
        ("S6", "Erigone dentipalpis", "Species", "F6", "Araneae", "Linyphiidae"),
        ("S7", "Xanthostigma xanthostigma", "Species", None, "Raphidioptera", "Raphidiidae"),
    ])
    c.commit()
    c.close()


ROWS = [
    # the existing Life tree
    (f"{INS}/Coleoptera/Carabidae/Carabus nemoralis/Carabus nemoralis 1.jpg", "exact", "Carabus nemoralis", "S1"),
    (f"{INS}/Hemiptera/Heteroptera/Pentatomidae/Palomena prasina/P.jpg", "exact", "Palomena prasina", "X"),
    (f"{SPI}/Linyphiidae/Tiso vagans/Tiso vagans.jpg", "exact", "Tiso vagans", "X"),
    # sources
    ("Photos/Microscope Photos/Coleoptera/Carabidae/Carabus nemoralis 1.v.19.jpg", "exact", "Carabus nemoralis", "S1"),
    ("Photos/Microscope Photos/Coleoptera/Carabidae/Abax parallelepipedus 2.v.19.jpg", "exact", "Abax parallelepipedus", "S2"),
    ("Photos/Microscope Photos/Coleoptera/Labs/Abax parallelepipedus 2.v.19.jpg", "exact", "Abax parallelepipedus", "S2"),
    ("Photos/Microscope Photos/Coleoptera/Silphidae/Silpha atrata 3.v.19.jpg", "exact", "Silpha atrata", "S3"),
    ("Photos/Microscope Photos/Hemiptera/Coreidae/Coreus marginatus 4.v.19.jpg", "exact", "Coreus marginatus", "S4"),
    ("Photos/Microscope Photos/Hemiptera/Scutelleridae/Eurygaster testudinaria 5.v.19.jpg", "exact", "Eurygaster testudinaria", "S5"),
    ("Photos/Microscope Photos/Coleoptera/Carabidae/Carabus nemorlis 6.v.19.jpg", "fuzzy, review", "Carabus nemoralis", "S1"),
    ("Photos/Life/Dead Spiders/Erigone dentipalpis Male 30102026.tif", "", "", ""),
    ("Photos/Microscope Photos/Raphidioptera/Xanthostigma xanthostigma 7.v.19.jpg", "exact", "Xanthostigma xanthostigma", "S7"),
    ("Photos/Microscope Photos/Coleoptera/P1050002.JPG", "", "", ""),
]


def _run(tmp_path):
    uksi, check, out = tmp_path / "u.db", tmp_path / "check.csv", tmp_path / "plan.csv"
    _uksi(uksi)
    with open(check, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        for rel, st, name, tvk in ROWS:
            w.writerow([rel, "image", "100", st, name, tvk])
        w.writerow(["Photos/Microscope Photos/Coleoptera/Thumbs.db", "other", "1", "", "", ""])
    assert pc.main(["--check-csv", str(check), "--uksi", str(uksi), "--csv", str(out),
                    "--root", str(tmp_path / "no-library")]) == 0
    with open(out, encoding="utf-8-sig") as f:
        return {r["source"].rsplit("/", 1)[1]: r for r in csv.DictReader(f)}


def test_places(tmp_path):
    p = _run(tmp_path)
    assert "Thumbs.db" not in p and len(p) == 9        # 10 photos; the two Abax share a name
    r = p["Carabus nemoralis 1.v.19.jpg"]
    assert (r["status"], r["destination"]) == (
        "planned", f"{INS}/Coleoptera/Carabidae/Carabus nemoralis/Specimen/Carabus nemoralis 1.v.19.jpg")
    assert p["Silpha atrata 3.v.19.jpg"]["destination"] == \
        f"{INS}/Coleoptera/Silphidae/Silpha atrata/Specimen/Silpha atrata 3.v.19.jpg"
    # Hemiptera: the suborder level from the UKSI ancestors
    assert p["Coreus marginatus 4.v.19.jpg"]["destination"] == \
        f"{INS}/Hemiptera/Heteroptera/Coreidae/Coreus marginatus/Specimen/Coreus marginatus 4.v.19.jpg"
    r = p["Eurygaster testudinaria 5.v.19.jpg"]
    assert r["status"] == "review" and r["destination"] == ""


def test_review_and_cannot_place(tmp_path):
    p = _run(tmp_path)
    assert p["Carabus nemorlis 6.v.19.jpg"]["status"] == "review"
    r = p["Erigone dentipalpis Male 30102026.tif"]
    assert r["status"] == "review" and r["uksi_name"] == "Erigone dentipalpis"
    assert r["destination"].startswith(f"{SPI}/Linyphiidae/Erigone dentipalpis/Specimen/")
    assert p["Xanthostigma xanthostigma 7.v.19.jpg"]["destination"].startswith(
        "Photos/Life/_New species/Xanthostigma xanthostigma/Specimen/")
    assert p["P1050002.JPG"]["status"] == "cannot place"


def test_copy_held_twice_reviewed_not_planned_twice(tmp_path):
    p = _run(tmp_path)          # keyed by file name: the Labs copy is the later row
    with open(tmp_path / "plan.csv", encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f) if "Abax" in r["source"]]
    assert [r["status"] for r in rows] == ["planned", "review"]
    assert rows[0]["destination"] == \
        f"{INS}/Coleoptera/Carabidae/Abax parallelepipedus/Specimen/Abax parallelepipedus 2.v.19.jpg"
    assert rows[1]["reason"].startswith("probably a copy") and rows[1]["destination"] == ""
    assert p  # read only: the check CSV is the only input


def test_name_clash_gets_a_free_name(tmp_path):
    taken = {"a/specimen/x.jpg", "a/specimen/x (2).jpg"}
    assert pc.free_name("a/Specimen", "x.jpg", taken) == "x (3).jpg"
