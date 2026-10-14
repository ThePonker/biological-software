"""B1 move (13 Oct 2026): the standard photo name, the move list from the plan and Wil's sheet,
and move_photos.py on throwaway folders -- dry run, apply, log, reverse; nothing overwritten
or deleted."""
import csv
import sqlite3

from scripts import build_photo_moves as bm
from scripts import move_photos as mp
from shared.photo_names import format_photo_date, standard_photo_stem

INS = "Photos/Life/Animalia/Arthropoda/Hexapoda/Insecta"


# --- the standard name ----------------------------------------------------------------------
def test_dates_written_the_standard_way():
    assert format_photo_date("2017-09-15") == "15.ix.17"
    cases = {
        "Bembidion dentellum 5.5cm 18.11.16": "Bembidion dentellum 5.5cm 18.xi.16",
        "Bathyphantes gracilis  Male 29092026": "Bathyphantes gracilis male 29.ix.26",
        "Barynotus moerens 12..iii.23": "Barynotus moerens 12.iii.23",
        "Lamia textor 14.VII.2023 2": "Lamia textor 14.vii.23 2",
        "Floronia bucculenta Female 01102026": "Floronia bucculenta female 1.x.26",
        "Pterostichus niger 6.vi.21": "Pterostichus niger 6.vi.21",
    }
    for old, new in cases.items():
        assert standard_photo_stem(old)[0] == new


def test_nothing_guessed():
    for s in ("Telmatophilus typhae 21.iii", "Drymus sylvaticus 10.1",
              "Agapanthia villosoviridescens v.18", "x 31.2.21",
              "Bembidion lampros 3.5 - 4cm", "Tasgius globulifer 28.ix.22 12mm"):
        assert standard_photo_stem(s) == (s, [])


# --- the move list --------------------------------------------------------------------------
def _uksi(path):
    c = sqlite3.connect(path)
    c.execute('CREATE TABLE taxa (tvk TEXT, scientific_name TEXT, rank TEXT, parent_tvk TEXT, '
              '"order" TEXT, family TEXT)')
    c.executemany("INSERT INTO taxa VALUES (?,?,?,?,?,?)", [
        ("O1", "Coleoptera", "Order", None, "Coleoptera", None),
        ("F1", "Carabidae", "Family", "O1", "Coleoptera", "Carabidae"),
        ("S1", "Poecilus cupreus", "Species", "F1", "Coleoptera", "Carabidae"),
        ("F2", "Elateridae", "Family", "O1", "Coleoptera", "Elateridae"),
        ("S2", "Limoniscus violaceus", "Species", "F2", "Coleoptera", "Elateridae"),
        ("F3", "Scarabaeidae", "Family", "O1", "Coleoptera", "Scarabaeidae"),
        ("S3", "Esymus merdarius", "Species", "F3", "Coleoptera", "Scarabaeidae"),
    ])
    c.commit()
    c.close()
    return path


def test_build_from_plan_and_sheet(tmp_path):
    check = [{"rel_path": f"{INS}/Coleoptera/Carabidae/Carabus nemoralis/a.jpg"},
             {"rel_path": f"{INS}/Coleoptera/Elateridae/Agriotes lineatus/b.jpg"},
             {"rel_path": f"{INS}/Coleoptera/Scarabaeidae/Aphodius x/c.jpg"}]
    plan = [{"source": "Photos/Microscope Photos/C/Carabus nemoralis 18.11.16.jpg", "status": "planned",
             "destination": f"{INS}/Coleoptera/Carabidae/Carabus nemoralis/Specimen/"
                            "Carabus nemoralis 18.11.16.jpg", "reason": "species folder exists"}]
    M = "Photos/Microscope Photos/C/"
    review = [
        {"source": M + "Amara cupreus 30.iv.22.jpg", "wil": "Should be Poecilus cupreus"},
        {"source": M + "Esymus meridianus 4.v.20.jpg", "wil": "E. merdarius"},
        {"source": M + "VCB 4.jpg", "wil": "move into Limoniscus violaceus "},
        {"source": M + "P1050002.JPG", "wil": "Folder Carabidae"},
        {"source": M + "Leiopus 3.vi.18.JPG", "wil": ""},
        {"source": M + "Odd 1.i.20.jpg", "wil": "Nonsense name"},
        {"source": M + "Tetrops praeustra 8.vi.16.JPG", "wil": "yes", "action": "move and rename",
         "destination": f"{INS}/Coleoptera/Cerambycidae/Tetrops praeustus/Specimen/Tetrops praeustus 8.vi.16.JPG"},
    ]
    moves = {m["source"].rsplit("/", 1)[1]: m for m in
             bm.build(plan, review, check, bm.pc.Uksi(_uksi(tmp_path / "u.db")))}
    C = f"{INS}/Coleoptera"
    assert moves["Carabus nemoralis 18.11.16.jpg"]["destination"].endswith("/Carabus nemoralis 18.xi.16.jpg")
    assert moves["Amara cupreus 30.iv.22.jpg"]["destination"] == \
        f"{C}/Carabidae/Poecilus cupreus/Specimen/Poecilus cupreus 30.iv.22.jpg"
    assert moves["Esymus meridianus 4.v.20.jpg"]["destination"] == \
        f"{C}/Scarabaeidae/Esymus merdarius/Specimen/Esymus merdarius 4.v.20.jpg"
    assert moves["VCB 4.jpg"]["destination"] == f"{C}/Elateridae/Limoniscus violaceus/VCB 4.jpg"
    assert moves["P1050002.JPG"]["destination"] == f"{C}/Carabidae/P1050002.JPG"
    assert moves["Leiopus 3.vi.18.JPG"]["destination"] == "Photos/_Photo review/Microscope Photos/C/Leiopus 3.vi.18.JPG"
    assert moves["Odd 1.i.20.jpg"]["destination"].startswith("Photos/_Photo review/")
    assert "not understood" in moves["Odd 1.i.20.jpg"]["reason"]
    assert moves["Tetrops praeustra 8.vi.16.JPG"]["renamed"] == "yes"


# --- the mover ------------------------------------------------------------------------------
def _lib(tmp_path):
    root = tmp_path / "Media"
    for rel in ("Photos/Microscope Photos/a.jpg", "Photos/Microscope Photos/b.jpg"):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"photo-" + rel.encode())
    moves = tmp_path / "moves.csv"
    with open(moves, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source", "destination"])
        w.writerow(["Photos/Microscope Photos/a.jpg", "Photos/Life/X/Specimen/a 1.i.20.jpg"])
        w.writerow(["Photos/Microscope Photos/b.jpg", "Photos/Life/Y/Specimen/b.jpg"])
    return root, moves


def _files(root):
    return sorted(str(p.relative_to(root)).replace("\\", "/") for p in root.rglob("*") if p.is_file())


def test_dry_run_moves_nothing(tmp_path):
    root, moves = _lib(tmp_path)
    before = _files(root)
    assert mp.main(["--moves", str(moves), "--root", str(root)]) == 0
    assert _files(root) == before


def test_apply_then_reverse(tmp_path):
    root, moves = _lib(tmp_path)
    before = _files(root)
    log = tmp_path / "log.csv"
    assert mp.main(["--moves", str(moves), "--root", str(root), "--apply", "--log", str(log)]) == 0
    assert _files(root) == ["Photos/Life/X/Specimen/a 1.i.20.jpg", "Photos/Life/Y/Specimen/b.jpg"]
    assert (root / "Photos/Life/Y/Specimen/b.jpg").read_bytes() == b"photo-Photos/Microscope Photos/b.jpg"
    assert len(mp.read(str(log))) == 2
    assert mp.main(["--reverse", str(log), "--root", str(root), "--apply",
                    "--log", str(tmp_path / "rev.csv")]) == 0
    assert _files(root) == before
    assert (root / "Photos/Life/X/Specimen").is_dir()          # emptied folders left


def test_never_overwrites_and_refuses_on_any_problem(tmp_path):
    root, moves = _lib(tmp_path)
    taken = root / "Photos/Life/Y/Specimen/b.jpg"
    taken.parent.mkdir(parents=True)
    taken.write_bytes(b"already here")
    before = _files(root)
    assert mp.main(["--moves", str(moves), "--root", str(root), "--apply",
                    "--log", str(tmp_path / "log.csv")]) == 1
    assert _files(root) == before and taken.read_bytes() == b"already here"
    assert not (tmp_path / "log.csv").exists()


def test_refuses_paths_outside_the_library(tmp_path):
    root, moves = _lib(tmp_path)
    with open(moves, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["Photos/Microscope Photos/a.jpg", "../escaped.jpg"])
    assert mp.main(["--moves", str(moves), "--root", str(root), "--apply",
                    "--log", str(tmp_path / "log.csv")]) == 1
    assert not (tmp_path / "escaped.jpg").exists()


def test_dry_run_catches_what_would_crash_apply(tmp_path):
    root, moves = _lib(tmp_path)
    (root / "Photos/Life").mkdir(parents=True)
    (root / "Photos/Life/X").write_bytes(b"a file where a folder must go")
    with open(moves, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Photos/Microscope Photos/b.jpg", "Photos/Life/Z/b.jpg"])          # twice
        w.writerow(["Photos/Microscope Photos/a.jpg", "Photos/Life/Bad: name/a.jpg"])
    checked = mp.check([(r["source"], r["destination"]) for r in mp.read(str(moves))], root)
    problems = [p for _, _, p in checked]
    assert "a file is in the way" in problems[0]
    assert "listed twice" in problems[2]
    assert "listed twice" in problems[3] or "not allow" in problems[3]
    assert mp.name_problem("Photos/Life/Bad: name/a.jpg").startswith("character")
    assert mp.name_problem("Photos/Life/Trailing. /a.jpg").endswith("drop it)")
    assert mp.main(["--moves", str(moves), "--root", str(root)]) == 1


def test_species_rename_keeps_what_the_name_recorded():
    assert bm.written_species("Amara cupreus 30.iv.22.jpg") == "Amara cupreus"
    for f in ("Leiopus 3.vi.18.JPG", "VCB 4.jpg", "P1050002 male.jpg", "Amara cf cupreus 1.i.20.jpg"):
        assert bm.written_species(f) == ""
    assert bm.rename_species("Leiopus 3.vi.18.JPG", "", "Leiopus linnei") == "Leiopus linnei Leiopus 3.vi.18.JPG"
    assert bm.rename_species("Amara cupreus 30.iv.22.jpg", "Amara cupreus", "Poecilus cupreus") == \
        "Poecilus cupreus 30.iv.22.jpg"
    assert standard_photo_stem("Trechus 2.5.10 mm")[0] == "Trechus 2.5.10 mm"
