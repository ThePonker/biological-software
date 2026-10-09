"""taxon_groups -- one order/family -> iRecord taxon group rule, and the UKSI taxonomy a
record should carry (review SRCH14 / OBS-11, 9 Oct 2026).

Observations from iRecord arrive with iRecord's own `taxon_group` ("insect - beetle
(Coleoptera)"). Records made here -- Data Entry commits, imports without the column --
have to work it out, and until 9 Oct 2026 Data Entry never did: 1,440 records had none,
so the group curves under-counted (Commercial Beetles 552 against Coleoptera 651).

The map below is the observation import wizard's ORDER_TO_GROUP / CLASS_TO_GROUP
(observation_import_wizard/validation_worker.py, 9 Oct 2026) with one change: Lepidoptera
is split by family into "insect - butterfly" and "insect - moth", as iRecord does. The
wizard sent every lepidopteran to "insect - moth" (42 butterfly records). A few class and
kingdom fallbacks are added, each using a label iRecord itself already gives records in
observatum.db (flowering plant, fungus, mollusc, crustacean).

    group = taxon_group("Lepidoptera", "Pieridae")              # 'insect - butterfly'
    info = taxonomy_for_tvks(["NBNSYS0000008319"])               # {tvk: {...}}

The wizards still hold their own copies of the map; they should import this one.
"""
from __future__ import annotations

from typing import Dict, Iterable, Optional

BUTTERFLY = "insect - butterfly"
MOTH = "insect - moth"

# The British butterfly families (UKSI). Every other lepidopteran family is a moth.
BUTTERFLY_FAMILIES = frozenset({
    "Hesperiidae", "Papilionidae", "Pieridae", "Nymphalidae", "Lycaenidae", "Riodinidae",
})

ORDER_TO_GROUP = {
    'Coleoptera': 'insect - beetle (Coleoptera)',
    'Diptera': 'insect - true fly (Diptera)',
    'Hymenoptera': 'insect - hymenopteran',
    'Hemiptera': 'insect - true bug (Hemiptera)',
    'Lepidoptera': MOTH,                  # butterflies split out by family in taxon_group()
    'Orthoptera': 'insect - orthopteran',
    'Odonata': 'insect - dragonfly (Odonata)',
    'Dermaptera': 'insect - earwig (Dermaptera)',
    'Mecoptera': 'insect - scorpion fly (Mecoptera)',
    'Neuroptera': 'insect - lacewing (Neuroptera)',
    'Trichoptera': 'insect - caddis fly (Trichoptera)',
    'Raphidioptera': 'insect - snakefly (Raphidioptera)',
    'Thysanoptera': 'insect - thrips (Thysanoptera)',
    'Siphonaptera': 'insect - flea (Siphonaptera)',
    'Araneae': 'spider (Araneae)',
    'Opiliones': 'harvestman (Opiliones)',
    'Pseudoscorpiones': 'false scorpion (Pseudoscorpiones)',
    'Passeriformes': 'bird',
    'Anseriformes': 'bird',
    'Charadriiformes': 'bird',
    'Accipitriformes': 'bird',
    'Strigiformes': 'bird',
    'Rodentia': 'terrestrial mammal',
    'Carnivora': 'terrestrial mammal',
    'Chiroptera': 'terrestrial mammal',
    'Anura': 'amphibian',
    'Caudata': 'amphibian',
    'Squamata': 'reptile',
    'Julida': 'millipede',
    'Polydesmida': 'millipede',
    'Lithobiomorpha': 'centipede',
    'Geophilomorpha': 'centipede',
    'Stylommatophora': 'mollusc',
    'Isopoda': 'crustacean',
    'Decapoda': 'crustacean',
    'Agaricales': 'fungus',
    'Polyporales': 'fungus',
}

# Class-level fallbacks, used only when the order is not in ORDER_TO_GROUP.
CLASS_TO_GROUP = {
    'Arachnida': 'spider (Araneae)',
    'Gastropoda': 'mollusc',
    'Malacostraca': 'crustacean',
    'Chilopoda': 'centipede',
    'Diplopoda': 'millipede',
    'Collembola': 'springtail (Collembola)',
    'Amphibia': 'amphibian',
    'Aves': 'bird',
    'Mammalia': 'terrestrial mammal',
    'Reptilia': 'reptile',
    'Insecta': 'insect',
    # added 9 Oct 2026 -- labels iRecord already uses in observatum.db
    'Bivalvia': 'mollusc',
    'Ostracoda': 'crustacean',
    'Magnoliopsida': 'flowering plant',
    'Liliopsida': 'flowering plant',
}

# Kingdom-level fallback, the last resort.
KINGDOM_TO_GROUP = {
    'Fungi': 'fungus',
}


def taxon_group(order: Optional[str], family: Optional[str] = None,
                class_name: Optional[str] = None, kingdom: Optional[str] = None) -> Optional[str]:
    """iRecord-style taxon group from UKSI order and family (class, kingdom as fallbacks).

    None when nothing maps -- a blank is better than a guess."""
    order = (order or "").strip()
    family = (family or "").strip()
    if order == "Lepidoptera":
        return BUTTERFLY if family in BUTTERFLY_FAMILIES else MOTH
    group = ORDER_TO_GROUP.get(order)
    if group:
        return group
    group = CLASS_TO_GROUP.get((class_name or "").strip())
    if group:
        return group
    return KINGDOM_TO_GROUP.get((kingdom or "").strip())


def is_butterfly(order: Optional[str], family: Optional[str]) -> bool:
    return (order or "").strip() == "Lepidoptera" and (family or "").strip() in BUTTERFLY_FAMILIES


def taxonomy_for_tvks(tvks: Iterable[str], uksi_path=None) -> Dict[str, dict]:
    """{tvk: {taxon_group, kingdom, taxon_rank, superfamily, taxonomic_sort_key, order_name,
    family}} from the current UKSI, for every TVK found there (others are left out).

    The sort key and superfamily come from shared.import_core.taxonomy_for_tvks -- the
    formula the import wizards use -- so a record committed here sorts like an imported one.
    Raises on failure; the caller decides what to do without it."""
    from shared.import_core import taxonomy_for_tvks as _sort_and_superfamily
    if uksi_path is None:
        import paths
        uksi_path = paths.UKSI_DB
    tvks = [t for t in dict.fromkeys(tvks) if t]
    out: Dict[str, dict] = {}
    if not tvks:
        return out
    base = _sort_and_superfamily(tvks, uksi_path)
    from shared.db_open import connect_ro
    conn = connect_ro(uksi_path)
    try:
        for i in range(0, len(tvks), 900):
            part = tvks[i:i + 900]
            ph = ",".join("?" * len(part))
            for tvk, kingdom, cls, order, family, rank in conn.execute(
                    f'SELECT tvk, kingdom, class, "order", family, rank FROM taxa '
                    f'WHERE tvk IN ({ph})', part):
                b = base.get(tvk, {})
                out[tvk] = {
                    "taxon_group": taxon_group(order, family, cls, kingdom),
                    "kingdom": kingdom or None,
                    "taxon_rank": rank or None,
                    "superfamily": b.get("superfamily") or None,
                    "taxonomic_sort_key": b.get("sort_key"),
                    "order_name": order or None,
                    "family": family or None,
                }
    finally:
        conn.close()
    return out
