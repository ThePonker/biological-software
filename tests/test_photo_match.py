"""shared/photo_match.py against the data copy of uksi.db (read-only), and the read-only
library check scripts/check_media_library.py on a temp tree of tiny JPEGs."""
import builtins
import datetime
import io
import sqlite3
from pathlib import Path

import pytest

import paths
from shared.photo_match import PhotoMatcher, SpecimenIndex, folder_warnings
from shared.photo_names import parse_photo_path

pytestmark = pytest.mark.skipif(not Path(paths.UKSI_DB).exists(), reason="no uksi.db copy")
TODAY = datetime.date(2026, 10, 11)


@pytest.fixture(scope="module")
def matcher():
    return PhotoMatcher(paths.UKSI_DB)


def m(matcher, name):
    return matcher.match_photo(parse_photo_path(name, today=TODAY))


def test_exact(matcher):
    r = m(matcher, "Dolomedes plantarius - Fen Raft Spider 3.jpg")
    assert r.status == "exact" and r.tvk == "NBNSYS0000008832"
    r = m(matcher, "Harmonia axyridis - Harlequin Ladybird 12 (1a).jpg")
    assert r.status == "exact" and r.scientific_name == "Harmonia axyridis"
    r = m(matcher, "Lamia textor 14.VII.2023 2.jpg")
    assert r.status == "exact" and r.tvk == "NBNSYS0000011050"


def test_misspelt_genus_is_fuzzy_review(matcher):
    r = m(matcher, "Perostichus niger 6.vi.21.jpg")
    assert r.method == "fuzzy" and r.review and r.status == "fuzzy, review"
    assert r.scientific_name == "Pterostichus niger"


def test_misspelt_epithet_within_genus(matcher):
    r = matcher.match("Rhagium mordx")
    assert r.status == "fuzzy, review" and r.scientific_name == "Rhagium mordax"


def test_genus_only(matcher):
    r = m(matcher, "Aphodius sp 1.x.19.jpg")
    assert r.method == "exact" and r.rank == "Genus" and r.scientific_name == "Aphodius"


def test_subspecies(matcher):
    r = m(matcher, "Zygaena filipendulae ssp. stephensi - Six-spot Burnet 2.jpg")
    assert r.status == "exact" and r.rank == "Subspecies"
    r = matcher.match("Zygaena filipendulae nonexistens", "Six-spot Burnet")
    assert r.review and r.scientific_name == "Zygaena filipendulae" and "matched to the species" in r.note


def test_synonym_goes_to_review(matcher):
    r = matcher.match("Strangalia maculata")
    assert r.status == "synonym, review" and r.scientific_name == "Rutpela maculata"


def test_rejected_and_unknown(matcher):
    assert m(matcher, "IMG_20260614_102231.jpg").method == "none"
    assert matcher.match("Xyzzyx plugh").method == "none"


def test_batch_is_cached(matcher):
    names = [("Lamia textor", ""), ("Perostichus niger", ""), ("Lamia textor", "")]
    out = matcher.match_many(names)
    assert len(out) == 2
    assert matcher.match_many(names)[("Lamia textor", "")] is out[("Lamia textor", "")]


def test_folder_warnings(matcher):
    pn = parse_photo_path("Photos/Microscope Photos/Lepidoptera/Lymantriidae/"
                          "Euproctis similis 2.vii.22.jpg", today=TODAY)
    w = folder_warnings(pn, matcher.match_photo(pn))
    assert any("family folder 'Lymantriidae'" in x for x in w)


def test_specimen_candidates():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE specimens (id INTEGER, specimen_code TEXT, species_tvk TEXT, "
                 "species_name TEXT, date_collected TEXT)")
    conn.executemany("INSERT INTO specimens VALUES (?,?,?,?,?)", [
        (1, "A1", "T1", "Lamia textor", "2023-07-14"),
        (2, "A2", "T1", "Lamia textor", "2023-07-14"),
        (3, "A3", "T2", "Pterostichus niger", "2021-06-06"),
        (4, "A4", "OLD", "Pterostichus niger", "2021-06-06"),
        (5, "A5", "T2", "Pterostichus niger", "")])
    s = SpecimenIndex(conn)
    assert [r["id"] for r in s.candidates("T1", "2023-07-14")] == [1, 2]
    assert [r["id"] for r in s.candidates("T2", "2021-06-06", "Pterostichus niger")] == [3, 4]
    assert s.candidates("T2", None) == [] and s.candidates("T2", "2021-06-07") == []


# ------------------------------------------------------------------ the library check script

NAMES = [
    "Photos/Life/Araneae/Pisauridae/Dolomedes plantarius/Dolomedes plantarius - Fen Raft Spider 3.jpg",
    "Photos/Life/Coleoptera/Harmonia axyridis/Harmonia axyridis - Harlequin Ladybird 12 (1a).JPG",
    "Photos/Life/Coleoptera/Harmonia axyridis/Lamia textor - Weaver Beetle 1.jpg",
    "Photos/Life/Lepidoptera/Zygaena filipendulae/Zygaena filipendulae ssp. stephensi - Six-spot Burnet 2.jpg",
    "Photos/Microscope Photos/Coleoptera/Carabidae/Perostichus niger 6.vi.21.jpg",
    "Photos/Microscope Photos/Coleoptera/Cerambycidae/Lamia textor 14.VII.2023 2.jpg",
    "Photos/Microscope Photos/Coleoptera/Scarabaeidae/Aphodius sp 1.x.19.jpg",
    "Photos/Originals/IMG_20260614_102231.jpg",
]


def _tree(tmp_path):
    from PIL import Image
    root = tmp_path / "Media"
    for n in NAMES:
        f = root / n
        f.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (4, 4), (90, 120, 60)).save(f, "JPEG")
    (root / "Videos").mkdir()
    (root / "Videos" / "clip.mp4").write_bytes(b"\0" * 10)
    return root


def test_scan_never_opens_a_file(tmp_path, monkeypatch):
    import PIL.Image

    from scripts import check_media_library as cml
    root = _tree(tmp_path)
    opened = []

    def refuse(*a, **k):
        opened.append(a[:1])
        raise AssertionError(f"a file was opened during the scan: {a[:1]}")
    PhotoMatcher(paths.UKSI_DB)                       # build the UKSI index before patching
    with monkeypatch.context() as mp:
        mp.setattr(builtins, "open", refuse)
        mp.setattr(io, "open", refuse)
        mp.setattr(PIL.Image, "open", refuse)
        entries, rows = cml.run_scan(root, paths.UKSI_DB, None)
    assert opened == []
    assert len(entries) == len(NAMES) + 1
    by = {r["rel_path"].rsplit("/", 1)[-1]: r for r in rows}
    assert by["Perostichus niger 6.vi.21.jpg"]["match_status"] == "fuzzy, review"
    assert by["Dolomedes plantarius - Fen Raft Spider 3.jpg"]["match_status"] == "exact"
    assert by["Lamia textor - Weaver Beetle 1.jpg"]["folder_agrees"] == 0
    assert by["IMG_20260614_102231.jpg"]["binomial"] == ""
    assert by["clip.mp4"]["kind"] == "video"
    lines = cml.report(entries, rows, has_attrs=False)
    assert any("every file is counted as local" in x for x in lines)
    assert any(x.strip().startswith("fuzzy, review") and x.strip().endswith("1") for x in lines)


def test_cloud_only_counted_from_attributes(tmp_path, monkeypatch):
    from scripts import check_media_library as cml
    root = _tree(tmp_path)
    monkeypatch.setattr(cml, "file_attributes", lambda st: cml.RECALL_ON_DATA_ACCESS
                        if st.st_size > 100 else cml.PINNED)
    entries = cml.scan_tree(root)
    assert sum(f.cloud_only for f in entries) == len(NAMES)      # the JPEGs
    assert sum(f.pinned for f in entries) == 1                    # the 10-byte clip
    lines = cml.report(entries, cml.analyse(entries), matched=False)
    assert any(f"cloud-only: {len(NAMES)}" in x for x in lines)


def test_main_writes_csv_and_says_read_only(tmp_path, capsys):
    from scripts import check_media_library as cml
    root = _tree(tmp_path)
    out = tmp_path / "check.csv"
    assert cml.main(["--root", str(root), "--csv", str(out), "--db", str(tmp_path / "none.db")]) == 0
    text = capsys.readouterr().out
    assert text.rstrip().endswith(cml.FINAL)
    lines = out.read_text(encoding="utf-8-sig").splitlines()
    assert len(lines) == len(NAMES) + 2 and lines[0].startswith("rel_path,")
