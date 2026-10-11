"""shared/photo_names.py -- the two file-name conventions and the folder as second witness."""
import datetime

from shared.photo_names import folder_binomial, media_kind, parse_photo_path

TODAY = datetime.date(2026, 10, 11)
LIFE = "Photos/Life/Araneae/Pisauridae/Dolomedes plantarius/"
MICRO = "Photos/Microscope Photos/Coleoptera/Carabidae/"


def p(path):
    return parse_photo_path(path, today=TODAY)


def test_life_convention():
    r = p(LIFE + "Dolomedes plantarius - Fen Raft Spider 3.jpg")
    assert (r.convention, r.parsed, r.name_source) == ("life", True, "file")
    assert r.binomial == "Dolomedes plantarius"
    assert r.common_name == "Fen Raft Spider" and r.number == 3
    assert r.folder_agrees is True and r.warnings == []
    assert r.kind == "image" and r.area == "Life"


def test_life_note_and_upper_case_extension():
    r = p("Photos/Life/Coleoptera/Harmonia axyridis/Harmonia axyridis - Harlequin Ladybird 12 (1a).JPG")
    assert r.binomial == "Harmonia axyridis" and r.number == 12 and r.note == "1a"
    assert r.common_name == "Harlequin Ladybird" and r.ext == ".jpg" and r.kind == "image"


def test_subspecies_drops_ssp_and_its_species_folder_agrees():
    r = p("Photos/Life/Lepidoptera/Zygaena filipendulae/"
          "Zygaena filipendulae ssp. stephensi - Six-spot Burnet 2.jpg")
    assert r.binomial == "Zygaena filipendulae stephensi"      # as UKSI writes it
    assert (r.infra_rank, r.infra) == ("ssp.", "stephensi")
    assert r.written_name == "Zygaena filipendulae ssp. stephensi"
    assert r.common_name == "Six-spot Burnet" and r.number == 2
    assert r.folder_agrees is True


def test_microscope_roman_two_digit_year():
    r = p(MICRO + "Perostichus niger 6.vi.21.jpg")
    assert r.convention == "microscope" and r.binomial == "Perostichus niger"
    assert r.date == "2021-06-06" and r.number is None
    assert (r.folder_order, r.folder_family) == ("Coleoptera", "Carabidae")


def test_microscope_upper_roman_four_digit_year_and_number():
    r = p("Photos/Microscope Photos/Coleoptera/Cerambycidae/Lamia textor 14.VII.2023 2.jpg")
    assert r.binomial == "Lamia textor" and r.date == "2023-07-14" and r.number == 2


def test_microscope_genus_only():
    r = p("Photos/Microscope Photos/Coleoptera/Scarabaeidae/Aphodius sp 1.x.19.jpg")
    assert r.binomial == "Aphodius" and r.epithet == "" and r.date == "2019-10-01"
    assert r.written_name == "Aphodius sp"


def test_camera_name_rejected():
    r = p("IMG_20260614_102231.jpg")
    assert not r.parsed and r.binomial == "" and r.convention is None


def test_camera_name_in_species_folder_takes_the_folder_name():
    r = p(LIFE + "IMG_20260614_102231.jpg")
    assert not r.parsed and r.name_source == "folder" and r.binomial == "Dolomedes plantarius"
    assert any("from folder" in w for w in r.warnings)


def test_folder_disagrees():
    r = p(LIFE + "Pisaura mirabilis - Nursery-web Spider 1.jpg")
    assert r.folder_agrees is False
    assert any("folder says 'Dolomedes plantarius'" in w for w in r.warnings)


def test_date_warnings():
    assert p("Pterostichus niger 1.iiii.21.jpg").date is None
    assert any("bad month" in w for w in p("Pterostichus niger 1.iiii.21.jpg").warnings)
    fut = p("Pterostichus niger 1.vi.29.jpg")
    assert fut.date == "2029-06-01" and any("future" in w for w in fut.warnings)
    assert p("Pterostichus niger 31.ii.21.jpg").date is None
    digits = p("Pterostichus niger 3.6.21.jpg")
    assert digits.date == "2021-06-03" and any("digits" in w for w in digits.warnings)


def test_helpers():
    assert folder_binomial("Lamia textor") == "Lamia textor"
    assert folder_binomial("Cerambycidae") == ""
    assert media_kind(".MOV") == "video" and media_kind(".txt") == "other"
