"""R17 A6: one person counted once (shared/recorder_names.py) and the export page's Recorders."""
from shared import recorder_names as rn
from shared.maps import map_stats


def n(*names):
    return rn.count_people(names)[0]


def test_one_person_in_four_spellings():
    assert len({rn.person_key(x) for x in ("Lyons, G.", "Graeme Lyons", "G. Lyons", "Lyons, G.J.")}) == 1
    assert rn.person_key("Lyons, G.") == ("lyons", "g")
    assert rn.person_key("LYONS, graeme") == ("lyons", "g")
    assert rn.person_key("G.J. Lyons") == ("lyons", "g")


def test_different_people_stay_apart():
    assert n("Heeney, W.J.", "Lyons, G.") == 2
    assert n("Smith, A.", "Smith, B.") == 2
    assert n("A. Smith", "B. Smith") == 2


def test_unparsed_names_count_by_their_text():
    assert not rn.parsed("Anderson") and not rn.parsed("Natural England")
    assert rn.parsed("Lyons, G.")
    assert rn.count_people(["Anderson", "anderson ", "Natural England", "Lyons, G.", "G. Lyons"]) == (3, 2)
    assert rn.count_people(["Lyons,", ""]) == (2, 2)


def test_split_as_before():
    assert rn.split_names("Graeme Lyons;Alice  Parfitt; Shaun Pryor") == [
        "Graeme Lyons", "Alice Parfitt", "Shaun Pryor"]
    assert rn.split_names("A. Smith & B. Jones") == ["A. Smith", "B. Jones"]
    assert rn.split_names("Anderson and Sandy") == ["Anderson", "Sandy"]
    assert rn.split_names(" ; ") == [] and rn.split_names(None) == []
    assert map_stats.recorder_names is rn.split_names


def test_stats_and_line_say_recorders_honestly():
    recs = [{"square": "SP42", "person": "Lyons, G.; Smith, A."},
            {"square": "SP42", "person": "Graeme Lyons & Bristol Museum"},
            {"square": "SP42", "person": "Smith, B."}]
    st = map_stats.compute(recs, None)
    assert st.recorders == 4 and st.recorders_unread == 1     # Lyons, A. Smith, B. Smith, the museum
    line = map_stats.counts_line(st)
    assert "Recorders 4 (incl. 1 name not matched by initial)" in line
    assert "names as given" not in line
    clean = map_stats.compute(recs[:1], None)
    assert map_stats.counts_line(clean).endswith("Recorders 2")
