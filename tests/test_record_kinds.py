"""shared.record_kinds: the one rule for incomplete names (10 Oct 2026)."""
import pytest

from shared.record_kinds import classify, is_excluded, species_name_for_ss

CASES = [
    ("Leiopus", None, {"genus"}), ("Leiopus sp.", None, {"genus"}), ("Leiopus spp.", None, {"genus"}),
    ("Melanotus", "Genus", {"genus"}), ("Troglodytidae", "Family", {"family_plus"}),
    ("Troglodytidae", None, {"family_plus"}), ("Coleoptera", None, {"family_plus"}),
    ("Forficula auricularia/dentata agg.", "Species", {"agg"}),
    ("Leiopus linnei/nebulosus", "Species aggregate", {"agg"}),
    ("Oligia strigilis agg.", "Species aggregate", {"agg"}),
    ("Xanthogramma pedissequum", "Species sensu lato", {"sl"}),
    ("Bombus terrestris s.s.", None, {"ss"}),
    ("Motacilla alba yarrellii", "Subspecies", {"subsp"}), ("Corvus corone corone", None, {"subsp"}),
    ("Hypholoma fasciculare var. fasciculare", "Variety", {"subsp"}),
    ("Rhopalus (Rhopalus) subrufus", None, set()), ("Grypocoris (Lophyromiris) stysi", None, set()),
    ("Cantharis flavilabris (=nigra auctt.)", None, set()),
    ("Salix x multinervis", None, {"hybrid"}), ("Salix × multinervis", "Species hybrid", {"hybrid"}),
    ("Rutpela maculata", "Species", set()), ("Hepialus humuli", "Subspecies", {"subsp"}),
    ("", None, set()), (None, None, set()),
]


@pytest.mark.parametrize("name,rank,expected", CASES)
def test_classify(name, rank, expected):
    assert set(classify(name, rank)) == expected


def test_is_excluded_and_ss():
    assert is_excluded({"agg"}, {"genus", "agg"})
    assert not is_excluded(set(), {"genus", "agg"})
    assert species_name_for_ss("Bombus terrestris s.s.") == "Bombus terrestris"
