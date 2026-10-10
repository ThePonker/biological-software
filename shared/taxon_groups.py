"""taxon_groups -- the one taxon grouping of the suite (review SRCH14 / MAP10 / OBS-11 / IMP-10,
9-10 Oct 2026). Everything that groups records by "taxon group" uses this module:

  * the stored column `taxon_group` on observations, recording_scheme and specimens, in
    iRecord's own labels ("insect - beetle (Coleoptera)"), filled on import, on Data Entry
    commit and on Quick Entry save, and for old records by scripts/backfill_taxon_groups.py;
  * the short display labels and merges of the Stats group curves ("Beetles (Coleoptera)",
    "Plants (Plantae)") -- one copy here instead of three in the dashboards;
  * the Filter Wizard's Group option and (later) Mapping, through group_sql() /
    group_filter_sql(), which use the stored label and fall back to order/family for a blank.

Rules
-----
- A record that came with a label (iRecord, an NBN/iRecord-format scheme file) keeps it. We only
  fill blanks; scripts never overwrite a label from iRecord.
- Our own label for a taxon comes from UKSI: family overrides (butterflies, seals, whales),
  then order, then class, then phylum, then kingdom. None when nothing maps -- a blank is
  better than a guess (an arachnid of unknown order is not called a spider).
- Labels are iRecord's. Every label below except those in UNCONFIRMED_LABELS occurs on
  iRecord records in observatum.db (checked 10 Oct 2026).

Not this grouping: Examen uses Pantheon's groups (assemblage types, from pantheon.db) -- a
different concept, kept. The gamification colour groups (features/gamification/theme.py)
are colours, not a grouping of records.

    group = taxon_group("Lepidoptera", "Pieridae")              # 'insect - butterfly'
    info = taxonomy_for_tvks(["NBNSYS0000008319"])               # {tvk: {...}}
    sql, params = group_filter_sql(["Beetles (Coleoptera)"])     # for a WHERE clause
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

BUTTERFLY = "insect - butterfly"
MOTH = "insect - moth"
MARINE_MAMMAL = "marine mammal"

# The British butterfly families (UKSI). Every other lepidopteran family is a moth.
BUTTERFLY_FAMILIES = frozenset({
    "Hesperiidae", "Papilionidae", "Pieridae", "Nymphalidae", "Lycaenidae", "Riodinidae",
})

# Family-level labels that cut across an order (checked before the order).
FAMILY_TO_GROUP = {
    **{f: BUTTERFLY for f in BUTTERFLY_FAMILIES},
    # seals (Carnivora) and whales/dolphins (Cetartiodactyla) -- iRecord: 'marine mammal'
    'Phocidae': MARINE_MAMMAL, 'Otariidae': MARINE_MAMMAL, 'Odobenidae': MARINE_MAMMAL,
    'Balaenidae': MARINE_MAMMAL, 'Balaenopteridae': MARINE_MAMMAL, 'Delphinidae': MARINE_MAMMAL,
    'Eschrichtiidae': MARINE_MAMMAL, 'Kogiidae': MARINE_MAMMAL, 'Monodontidae': MARINE_MAMMAL,
    'Phocoenidae': MARINE_MAMMAL, 'Physeteridae': MARINE_MAMMAL, 'Ziphiidae': MARINE_MAMMAL,
}

ORDER_TO_GROUP = {
    # insects
    'Coleoptera': 'insect - beetle (Coleoptera)',
    'Diptera': 'insect - true fly (Diptera)',
    'Hymenoptera': 'insect - hymenopteran',
    'Hemiptera': 'insect - true bug (Hemiptera)',
    'Lepidoptera': MOTH,                  # butterflies by family, FAMILY_TO_GROUP
    'Orthoptera': 'insect - orthopteran',
    'Odonata': 'insect - dragonfly (Odonata)',
    'Dermaptera': 'insect - earwig (Dermaptera)',
    'Mecoptera': 'insect - scorpion fly (Mecoptera)',
    'Neuroptera': 'insect - lacewing (Neuroptera)',
    'Trichoptera': 'insect - caddis fly (Trichoptera)',
    'Raphidioptera': 'insect - snakefly (Raphidioptera)',
    'Thysanoptera': 'insect - thrips (Thysanoptera)',
    'Siphonaptera': 'insect - flea (Siphonaptera)',
    'Zygentoma': 'insect - silverfish (Thysanura)',
    'Ephemeroptera': 'insect - mayfly (Ephemeroptera)',
    'Plecoptera': 'insect - stonefly (Plecoptera)',
    'Megaloptera': 'insect - alderfly (Megaloptera)',
    'Archaeognatha': 'insect - bristletail (Archaeognatha)',
    'Blattodea': 'insect - cockroach (Dictyoptera)',
    'Phasmatodea': 'insect - stick insect (Phasmida)',
    'Psocodea': 'insect - booklouse (Psocoptera)',
    # arachnids
    'Araneae': 'spider (Araneae)',
    'Opiliones': 'harvestman (Opiliones)',
    'Pseudoscorpiones': 'false scorpion (Pseudoscorpiones)',
    'Scorpiones': 'scorpion',
    'Trombidiformes': 'acarine (Acari)',
    'Sarcoptiformes': 'acarine (Acari)',
    'Mesostigmata': 'acarine (Acari)',
    'Ixodida': 'acarine (Acari)',
    'Astigmata': 'acarine (Acari)',
    # other invertebrates
    'Julida': 'millipede',
    'Polydesmida': 'millipede',
    'Lithobiomorpha': 'centipede',
    'Geophilomorpha': 'centipede',
    'Stylommatophora': 'mollusc',
    'Isopoda': 'crustacean',
    'Decapoda': 'crustacean',
    'Tricladida': 'flatworm (Turbellaria)',
    # vertebrates
    'Passeriformes': 'bird',
    'Anseriformes': 'bird',
    'Charadriiformes': 'bird',
    'Accipitriformes': 'bird',
    'Strigiformes': 'bird',
    'Rodentia': 'terrestrial mammal',
    'Carnivora': 'terrestrial mammal',     # seals by family, FAMILY_TO_GROUP
    'Chiroptera': 'terrestrial mammal',
    'Anura': 'amphibian',
    'Caudata': 'amphibian',
    'Squamata': 'reptile',
    # plants and fungi
    'Equisetales': 'horsetail',            # before the class: Polypodiopsida is 'fern'
    'Agaricales': 'fungus',
    'Polyporales': 'fungus',
}

# Class-level fallbacks, used only when neither family nor order maps.
CLASS_TO_GROUP = {
    'Gastropoda': 'mollusc',
    'Bivalvia': 'mollusc',
    'Malacostraca': 'crustacean',
    'Ostracoda': 'crustacean',
    'Chilopoda': 'centipede',
    'Diplopoda': 'millipede',
    'Collembola': 'springtail (Collembola)',
    'Clitellata': 'annelid',
    'Polychaeta': 'annelid',
    'Amphibia': 'amphibian',
    'Aves': 'bird',
    'Mammalia': 'terrestrial mammal',
    'Reptilia': 'reptile',
    'Actinopterygii': 'bony fish (Actinopterygii)',
    'Insecta': 'insect',                   # an insect order not listed above
    'Magnoliopsida': 'flowering plant',
    'Liliopsida': 'flowering plant',
    'Polypodiopsida': 'fern',
    'Pinopsida': 'conifer',
    'Bryopsida': 'moss',
    'Sphagnopsida': 'moss',
    'Polytrichopsida': 'moss',
    'Andreaeopsida': 'moss',
    'Tetraphidopsida': 'moss',
    'Jungermanniopsida': 'liverwort',
    'Marchantiopsida': 'liverwort',
    'Lycopodiopsida': 'clubmoss',
    'Lecanoromycetes': 'lichen',
    'Myxogastrea': 'slime mould',
    'Phaeophyceae': 'chromist',
    'Ulvophyceae': 'alga',
}

PHYLUM_TO_GROUP = {
    'Cnidaria': 'coelenterate (=cnidarian)',
    'Mollusca': 'mollusc',
    'Annelida': 'annelid',
}

# The last resort.
KINGDOM_TO_GROUP = {
    'Fungi': 'fungus',
}

# Labels in the maps above that no iRecord record in observatum.db carried on 10 Oct 2026, so
# their spelling is ours until one arrives. None of them is on any record yet.
UNCONFIRMED_LABELS = frozenset({
    'insect', 'insect - mayfly (Ephemeroptera)', 'insect - stonefly (Plecoptera)',
    'insect - alderfly (Megaloptera)', 'insect - bristletail (Archaeognatha)',
    'insect - cockroach (Dictyoptera)', 'insect - stick insect (Phasmida)',
    'insect - booklouse (Psocoptera)', 'liverwort', 'clubmoss',
})


def taxon_group(order: Optional[str], family: Optional[str] = None,
                class_name: Optional[str] = None, kingdom: Optional[str] = None,
                phylum: Optional[str] = None) -> Optional[str]:
    """iRecord-style taxon group from UKSI family, order, class, phylum, kingdom.

    None when nothing maps -- a blank is better than a guess."""
    family = (family or "").strip()
    group = FAMILY_TO_GROUP.get(family)
    if group:
        return group
    for value, table in ((order, ORDER_TO_GROUP), (class_name, CLASS_TO_GROUP),
                         (phylum, PHYLUM_TO_GROUP), (kingdom, KINGDOM_TO_GROUP)):
        group = table.get((value or "").strip())
        if group:
            return group
    return None


def is_butterfly(order: Optional[str], family: Optional[str]) -> bool:
    return (order or "").strip() == "Lepidoptera" and (family or "").strip() in BUTTERFLY_FAMILIES


def group_for_record(stored: Optional[str], order: Optional[str] = None,
                     family: Optional[str] = None, kingdom: Optional[str] = None) -> Optional[str]:
    """The group of a record: its stored label, else ours from its order and family (the
    Python twin of group_sql())."""
    stored = (stored or "").strip()
    return stored or taxon_group(order, family, kingdom=kingdom)


# ------------------------------------------------------------------ display labels (Stats)
# iRecord label -> short display label, in display order. Formerly LABEL_MAP, copied into
# personal_dashboard, all_stats_dashboard and commercial_dashboard (identical copies).
CURVE_LABELS = {
    'insect - beetle (Coleoptera)': 'Beetles (Coleoptera)',
    'insect - true fly (Diptera)': 'True Flies (Diptera)',
    'insect - hymenopteran': 'Bees, Wasps & Ants (Hymenoptera)',
    'insect - true bug (Hemiptera)': 'True Bugs (Hemiptera)',
    'insect - moth': 'Moths (Lepidoptera)',
    'insect - butterfly': 'Butterflies (Lepidoptera)',
    'insect - dragonfly (Odonata)': 'Dragonflies (Odonata)',
    'insect - orthopteran': 'Grasshoppers & Crickets (Orthoptera)',
    'insect - earwig (Dermaptera)': 'Earwigs (Dermaptera)',
    'insect - scorpion fly (Mecoptera)': 'Scorpion Flies (Mecoptera)',
    'insect - caddis fly (Trichoptera)': 'Caddisflies (Trichoptera)',
    'insect - snakefly (Raphidioptera)': 'Snakeflies (Raphidioptera)',
    'insect - lacewing (Neuroptera)': 'Lacewings (Neuroptera)',
    'insect - thrips (Thysanoptera)': 'Thrips (Thysanoptera)',
    'insect - flea (Siphonaptera)': 'Fleas (Siphonaptera)',
    'insect - silverfish (Thysanura)': 'Silverfish (Zygentoma)',
    'insect - mayfly (Ephemeroptera)': 'Mayflies (Ephemeroptera)',
    'insect - stonefly (Plecoptera)': 'Stoneflies (Plecoptera)',
    'insect - alderfly (Megaloptera)': 'Alderflies (Megaloptera)',
    'insect - bristletail (Archaeognatha)': 'Bristletails (Archaeognatha)',
    'insect - cockroach (Dictyoptera)': 'Cockroaches (Blattodea)',
    'insect - stick insect (Phasmida)': 'Stick Insects (Phasmida)',
    'insect - booklouse (Psocoptera)': 'Booklice (Psocodea)',
    'insect': 'Other Insects',
    'spider (Araneae)': 'Spiders (Araneae)',
    'harvestman (Opiliones)': 'Harvestmen (Opiliones)',
    'false scorpion (Pseudoscorpiones)': 'False Scorpions (Pseudoscorpiones)',
    'acarine (Acari)': 'Mites (Acari)',
    'scorpion': 'Scorpions (Scorpiones)',
    'millipede': 'Millipedes (Diplopoda)',
    'centipede': 'Centipedes (Chilopoda)',
    'springtail (Collembola)': 'Springtails (Collembola)',
    'crustacean': 'Crustaceans (Crustacea)',
    'mollusc': 'Molluscs (Mollusca)',
    'annelid': 'Annelids (Annelida)',
    'flatworm (Turbellaria)': 'Flatworms (Turbellaria)',
    'coelenterate (=cnidarian)': 'Cnidarians (Cnidaria)',
    'bird': 'Birds (Aves)',
    'terrestrial mammal': 'Land Mammals (Mammalia)',
    'marine mammal': 'Marine Mammals (Mammalia)',
    'amphibian': 'Amphibians (Amphibia)',
    'reptile': 'Reptiles (Reptilia)',
    'bony fish (Actinopterygii)': 'Fish (Actinopterygii)',
    'flowering plant': 'Flowering Plants (Angiospermae)',
    'fern': 'Ferns (Polypodiopsida)',
    'conifer': 'Conifers (Pinopsida)',
    'horsetail': 'Horsetails (Equisetopsida)',
    'moss': 'Mosses (Bryophyta)',
    'liverwort': 'Liverworts (Marchantiophyta)',
    'clubmoss': 'Clubmosses (Lycopodiopsida)',
    'fungus': 'Fungi',
    'slime mould': 'Slime Moulds (Mycetozoa)',
    'lichen': 'Lichens',
    'alga': 'Algae',
    'chromist': 'Chromists (Chromista)',
}

# Display labels that stand for several iRecord labels (the curves draw one line for them).
CURVE_MERGES = {
    'Plants (Plantae)': ['flowering plant', 'fern', 'conifer', 'horsetail'],
    'Fungi': ['fungus', 'slime mould'],
    'Mammals (Mammalia)': ['terrestrial mammal', 'marine mammal'],
}
_MERGED_INTO = {m: label for label, members in CURVE_MERGES.items() for m in members}


def group_label(group: Optional[str]) -> str:
    """Short display label for an iRecord taxon_group value (merges applied); unknown labels
    are title-cased, as the dashboards always did."""
    group = (group or "").strip()
    if not group:
        return ""
    return _MERGED_INTO.get(group) or CURVE_LABELS.get(group) or group.title()


def _display_rank() -> Dict[str, int]:
    rank: Dict[str, int] = {}
    for tg in CURVE_LABELS:
        rank.setdefault(group_label(tg), len(rank))
    return rank


def display_labels(groups: Iterable[Optional[str]] = None) -> List[str]:
    """Display labels in display order. With `groups` (iRecord values, e.g. the distinct
    taxon_group values in a table), only the labels those values fall under; labels this
    module does not know come last, alphabetically."""
    rank = _display_rank()
    if groups is None:
        return sorted(rank, key=rank.get)
    labels = {group_label(g) for g in groups if (g or "").strip()}
    return sorted(labels, key=lambda lab: (rank.get(lab, len(rank)), lab))


def group_values(label: str, known: Iterable[str] = ()) -> List[str]:
    """The iRecord taxon_group values a display label stands for (the inverse of
    group_label). `known` adds values seen in the data that only title-casing maps
    to the label. A raw iRecord value passed as `label` stands for itself as well."""
    out = list(CURVE_MERGES.get(label, []))
    out += [tg for tg, lab in CURVE_LABELS.items() if lab == label and tg not in _MERGED_INTO]
    out += [k for k in known if k and group_label(k) == label]
    if label in CURVE_LABELS or label in _MERGED_INTO:
        out.append(label)
    return list(dict.fromkeys(out))


def merge_curve_groups(raw: Dict[str, dict]) -> Tuple[Dict[str, dict], Dict[str, List[str]]]:
    """Fold the stats service's per-taxon_group curve data ({taxon_group: {'species_count': N,
    'yearly_new': {year: n}}}) into display labels. Returns (label_data, label_groups) --
    label_groups maps each label to the taxon_group values in it, for the species dialog."""
    label_data: Dict[str, dict] = {}
    label_groups: Dict[str, List[str]] = {}
    for tg, info in raw.items():
        label = group_label(tg)
        if label not in label_data:
            label_data[label] = {'species_count': 0, 'yearly_new': {}}
            label_groups[label] = []
        label_groups[label].append(tg)
        label_data[label]['species_count'] += info['species_count']
        for yr, cnt in info['yearly_new'].items():
            label_data[label]['yearly_new'][yr] = label_data[label]['yearly_new'].get(yr, 0) + cnt
    return label_data, label_groups


# ------------------------------------------------------------------ SQL
def _lit(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def _in(values) -> str:
    return "(" + ",".join(_lit(v) for v in sorted(values)) + ")"


def group_sql(group_col: str = "taxon_group", order_col: str = "order_name",
              family_col: str = "family", kingdom_col: Optional[str] = None) -> str:
    """SQL expression for a record's group: the stored label, else ours from order and family
    (and kingdom, for tables that have it). Class and phylum fallbacks need UKSI and are not
    in it -- the backfill and the import/commit paths store those. Constant text only, no
    parameters: safe to use in SELECT, WHERE and GROUP BY.

    For a table alias pass e.g. group_col='o.taxon_group'."""
    by_group: Dict[str, set] = {}
    for order, group in ORDER_TO_GROUP.items():
        by_group.setdefault(group, set()).add(order)
    by_family: Dict[str, set] = {}
    for family, group in FAMILY_TO_GROUP.items():
        by_family.setdefault(group, set()).add(family)
    whens = [f"WHEN {family_col} IN {_in(fams)} THEN {_lit(g)}" for g, fams in sorted(by_family.items())]
    whens += [f"WHEN {order_col} IN {_in(orders)} THEN {_lit(g)}" for g, orders in sorted(by_group.items())]
    if kingdom_col:
        whens += [f"WHEN {kingdom_col} = {_lit(k)} THEN {_lit(g)}" for k, g in KINGDOM_TO_GROUP.items()]
    case = "CASE " + " ".join(whens) + " END"
    return f"COALESCE(NULLIF(TRIM({group_col}), ''), {case})"


def group_filter_sql(labels: Sequence[str], known: Iterable[str] = (), **cols) -> Tuple[str, list]:
    """(sql, params) for "the record is in any of these groups". `labels` are display labels
    (or raw iRecord values); `known` = distinct stored values, so title-cased labels resolve;
    `cols` as for group_sql(). Empty labels -> ("1=0", [])."""
    known = list(known)
    values: List[str] = []
    for lab in labels:
        values += group_values(lab, known)
    values = list(dict.fromkeys(values))
    if not values:
        return "1=0", []
    return f"{group_sql(**cols)} IN ({','.join('?' * len(values))})", values


# ------------------------------------------------------------------ UKSI
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
        cols = {r[1] for r in conn.execute("PRAGMA table_info(taxa)")}
        phylum = "phylum" if "phylum" in cols else "NULL"
        for i in range(0, len(tvks), 900):
            part = tvks[i:i + 900]
            ph = ",".join("?" * len(part))
            for tvk, kingdom, phy, cls, order, family, rank in conn.execute(
                    f'SELECT tvk, kingdom, {phylum}, class, "order", family, rank FROM taxa '
                    f'WHERE tvk IN ({ph})', part):
                b = base.get(tvk, {})
                out[tvk] = {
                    "taxon_group": taxon_group(order, family, cls, kingdom, phy),
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


def fill_blank_groups(rows, taxonomy: Optional[Dict[str, dict]] = None, uksi_path=None) -> int:
    """Import rows (any wizard's row objects with species_tvk / taxon_group, and kingdom
    where they have it): fill a blank taxon_group -- and a blank kingdom -- from UKSI by
    the row's FINAL TVK, else from its order and family. A label already on the row (from
    the file, e.g. iRecord's) is kept. Returns how many groups were filled.

    taxonomy: a taxonomy_for_tvks() result; looked up when not given (a failure leaves the
    order/family fallback only)."""
    rows = list(rows)
    if taxonomy is None:
        try:
            taxonomy = taxonomy_for_tvks((getattr(r, "species_tvk", "") for r in rows), uksi_path)
        except Exception as e:                       # fall back to order and family
            print(f"[taxon_groups] UKSI lookup failed: {e}")
            taxonomy = {}
    filled = 0
    for r in rows:
        t = taxonomy.get(getattr(r, "species_tvk", "") or "") or {}
        if hasattr(r, "kingdom") and not (r.kingdom or "").strip() and t.get("kingdom"):
            r.kingdom = t["kingdom"]
        if (getattr(r, "taxon_group", "") or "").strip():
            continue
        group = t.get("taxon_group") or taxon_group(getattr(r, "order_name", None),
                                                    getattr(r, "family", None),
                                                    kingdom=getattr(r, "kingdom", None))
        if group:
            r.taxon_group = group
            filled += 1
    return filled
