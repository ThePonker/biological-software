"""
Collection Planner — Taxonomic Tree Data

Loads hierarchical taxonomic data from uksi.db and observatum.db
for building the tree: Order → Superfamily → Family → Subfamily → Genus → Species
"""

import json
import sqlite3
import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import paths
from pathlib import Path
from dataclasses import dataclass, field

UKSI_PATH = paths.UKSI_DB
DB_PATH = paths.OBSERVATUM_DB


@dataclass
class TaxonNode:
    name: str
    rank: str
    sort_key: int = 0
    common_name: str = ""
    specimen_count: int = 0
    species_count: int = 0
    uksi_species_count: int = 0
    my_species_count: int = 0
    children: list = field(default_factory=list)
    in_collection: bool = False




def _load_uksi_total_counts(order_name):
    """Load total species counts per family and genus from UKSI."""
    fam_totals = {}
    gen_totals = {}
    if not UKSI_PATH.exists():
        return fam_totals, gen_totals
    conn = sqlite3.connect(str(UKSI_PATH))
    c = conn.cursor()
    c.execute("""SELECT family, COUNT(DISTINCT scientific_name) FROM taxa
                 WHERE "order" = ? AND rank = 'Species' AND family IS NOT NULL
                 GROUP BY family""", (order_name,))
    for fam, cnt in c.fetchall():
        fam_totals[fam] = cnt
    c.execute("""SELECT genus, COUNT(DISTINCT scientific_name) FROM taxa
                 WHERE "order" = ? AND rank = 'Species' AND genus IS NOT NULL
                 GROUP BY genus""", (order_name,))
    for gen, cnt in c.fetchall():
        gen_totals[gen] = cnt
    conn.close()
    return fam_totals, gen_totals



def _load_uksi_total_counts(order_name):
    """Load total species counts per family and genus from UKSI."""
    fam_totals = {}
    gen_totals = {}
    if not UKSI_PATH.exists():
        return fam_totals, gen_totals
    conn = sqlite3.connect(str(UKSI_PATH))
    c = conn.cursor()
    c.execute("""SELECT family, COUNT(DISTINCT scientific_name) FROM taxa
                 WHERE "order" = ? AND rank = 'Species' AND family IS NOT NULL
                 GROUP BY family""", (order_name,))
    for fam, cnt in c.fetchall():
        fam_totals[fam] = cnt
    c.execute("""SELECT genus, COUNT(DISTINCT scientific_name) FROM taxa
                 WHERE "order" = ? AND rank = 'Species' AND genus IS NOT NULL
                 GROUP BY genus""", (order_name,))
    for gen, cnt in c.fetchall():
        gen_totals[gen] = cnt
    conn.close()
    return fam_totals, gen_totals



def _load_uksi_total_counts(order_name):
    """Load total species counts per family and genus from UKSI."""
    fam_totals = {}
    gen_totals = {}
    if not UKSI_PATH.exists():
        return fam_totals, gen_totals
    conn = sqlite3.connect(str(UKSI_PATH))
    c = conn.cursor()
    c.execute("""SELECT family, COUNT(DISTINCT scientific_name) FROM taxa
                 WHERE "order" = ? AND rank = 'Species' AND family IS NOT NULL
                 GROUP BY family""", (order_name,))
    for fam, cnt in c.fetchall():
        fam_totals[fam] = cnt
    c.execute("""SELECT genus, COUNT(DISTINCT scientific_name) FROM taxa
                 WHERE "order" = ? AND rank = 'Species' AND genus IS NOT NULL
                 GROUP BY genus""", (order_name,))
    for gen, cnt in c.fetchall():
        gen_totals[gen] = cnt
    conn.close()
    return fam_totals, gen_totals

def load_taxonomic_tree(order_name: str, my_specimens_only: bool = True) -> TaxonNode:
    """Build a taxonomic tree for an order.
    
    Structure: Order → [Suborder →] Superfamily → Family → Subfamily → Genus → Species
    Suborder nodes inserted when suborder data available (UKSI or JSON).
    """
    my_fams, my_gen, my_sp, fam_counts, sp_counts = _load_specimen_data(order_name)

    sf_lookup = _load_superfamily_map()
    uksi_fam_totals, uksi_gen_totals = _load_uksi_total_counts(order_name)
    uksi_fam_totals, uksi_gen_totals = _load_uksi_total_counts(order_name)
    uksi_fam_totals, uksi_gen_totals = _load_uksi_total_counts(order_name)
    families = _load_uksi_families(order_name)
    subfams_by_fam = _load_uksi_subfamilies(order_name)
    gen_by_fam, sp_by_gen, gen_to_subfam = _load_uksi_genera_species(order_name)
    common_names = _load_common_names()
    suborder_map = _load_suborder_map(order_name)

    root = TaxonNode(name=order_name, rank="Order", in_collection=True)

    # Group families by superfamily
    sf_groups = {}
    for fam_name, sort_code in families:
        sf = sf_lookup.get(fam_name, "")
        sf_groups.setdefault(sf, []).append((fam_name, sort_code))

    sorted_sfs = sorted(sf_groups.items(), key=lambda x: x[1][0][1] if x[1] else 999999)

    # Build superfamily/family nodes into a flat list of (suborder, node) pairs
    built_nodes = []  # [(suborder_name, node)]

    for sf_name, sf_families in sorted_sfs:
        sf_node = TaxonNode(
            name=sf_name, rank="Superfamily",
            sort_key=sf_families[0][1] if sf_families else 0,
        ) if sf_name else None

        for fam_name, fam_sort in sf_families:
            if my_specimens_only and fam_name not in my_fams:
                continue

            fam_node = _build_family_node(
                fam_name, fam_sort, common_names, fam_counts, my_fams,
                subfams_by_fam, gen_by_fam, gen_to_subfam, sp_by_gen,
                sp_counts, my_gen, my_sp, my_specimens_only,
                uksi_fam_totals, uksi_gen_totals)

            if sf_node is not None:
                sf_node.children.append(fam_node)
            else:
                suborder = suborder_map.get(fam_name, "")
                built_nodes.append((suborder, fam_node))

        if sf_node is not None and sf_node.children:
            sf_node.in_collection = any(c.in_collection for c in sf_node.children)
            # All families in this superfamily should share a suborder
            first_fam = sf_families[0][0] if sf_families else ""
            suborder = suborder_map.get(first_fam, "")
            built_nodes.append((suborder, sf_node))

    # Group nodes by suborder and build tree
    if suborder_map:
        _assemble_with_suborders(root, built_nodes, suborder_map)
    else:
        for _, node in built_nodes:
            root.children.append(node)

    return root


def _build_family_node(fam_name, fam_sort, common_names, fam_counts, my_fams,
                       subfams_by_fam, gen_by_fam, gen_to_subfam, sp_by_gen,
                       sp_counts, my_gen, my_sp, my_only,
                       uksi_fam_totals=None, uksi_gen_totals=None):
    """Build a single family node with its subfamily/genus/species children."""
    fam_node = TaxonNode(
        name=fam_name, rank="Family", sort_key=fam_sort,
        common_name=common_names.get(fam_name, ""),
        specimen_count=fam_counts.get(fam_name, 0),
        uksi_species_count=(uksi_fam_totals or {}).get(fam_name, 0),
        in_collection=fam_name in my_fams,
    )
    subfams = subfams_by_fam.get(fam_name, [])
    genera = gen_by_fam.get(fam_name, [])

    subfam_genera = {}
    unassigned_genera = []
    for gen_name, gen_sort in genera:
        sf_of_gen = gen_to_subfam.get(gen_name, "")
        if sf_of_gen:
            subfam_genera.setdefault(sf_of_gen, []).append((gen_name, gen_sort))
        else:
            unassigned_genera.append((gen_name, gen_sort))

    for subfam_name, subfam_sort in subfams:
        sf_genera = subfam_genera.get(subfam_name, [])
        if my_only and not any(g[0] in my_gen for g in sf_genera):
            continue
        subfam_node = TaxonNode(
            name=subfam_name, rank="Subfamily", sort_key=subfam_sort,
            in_collection=any(g[0] in my_gen for g in sf_genera),
        )
        _add_genera_to_node(subfam_node, sf_genera, sp_by_gen,
                            common_names, sp_counts, my_gen, my_sp, my_only,
                            uksi_gen_totals)
        if subfam_node.children or not my_only:
            fam_node.children.append(subfam_node)

    _add_genera_to_node(fam_node, unassigned_genera, sp_by_gen,
                        common_names, sp_counts, my_gen, my_sp, my_only,
                        uksi_gen_totals)
    fam_node.species_count = _count_species(fam_node)
    _aggregate_specimen_counts(fam_node)
    return fam_node


def _assemble_with_suborders(root, built_nodes, suborder_map):
    """Group built nodes under Suborder container nodes."""
    # Load suborder common names from JSON
    from .planner_data import SORT_OVERRIDES_PATH
    so_common = {}
    if SORT_OVERRIDES_PATH.exists():
        try:
            import json as _json
            with open(SORT_OVERRIDES_PATH, "r", encoding="utf-8") as f:
                so_common = _json.load(f).get("_suborder_common_names", {})
        except Exception:
            pass

    seen_suborders = []
    suborder_children = {}
    for suborder, node in built_nodes:
        if suborder not in suborder_children:
            seen_suborders.append(suborder)
            suborder_children[suborder] = []
        suborder_children[suborder].append(node)

    for so_name in seen_suborders:
        children = suborder_children[so_name]
        if not so_name:
            for node in children:
                root.children.append(node)
        else:
            so_node = TaxonNode(
                name=so_name, rank="Suborder",
                sort_key=children[0].sort_key if children else 0,
                common_name=so_common.get(so_name, ""),
                in_collection=any(c.in_collection for c in children),
            )
            so_node.children = children
            root.children.append(so_node)


def _add_genera_to_node(parent_node, genera, sp_by_gen, common_names,
                         sp_counts, my_gen, my_sp, my_only,
                         uksi_gen_totals=None):
    """Add genus → species nodes under a parent (family or subfamily)."""
    for gen_name, gen_sort in genera:
        if my_only and gen_name not in my_gen:
            continue
        gen_node = TaxonNode(
            name=gen_name, rank="Genus", sort_key=gen_sort,
            uksi_species_count=(uksi_gen_totals or {}).get(gen_name, 0),
            in_collection=gen_name in my_gen,
        )
        species = sp_by_gen.get(gen_name, [])
        for sp_name, sp_sort in species:
            if my_only and sp_name not in my_sp:
                continue
            gen_node.children.append(TaxonNode(
                name=sp_name, rank="Species", sort_key=sp_sort,
                common_name=common_names.get(sp_name, ""),
                specimen_count=sp_counts.get(sp_name, 0),
                in_collection=sp_name in my_sp,
            ))
        if gen_node.children or not my_only:
            parent_node.children.append(gen_node)



def _aggregate_specimen_counts(node):
    """Sum specimens and count distinct species up through the tree."""
    if node.rank == "Species":
        node.my_species_count = 1 if node.specimen_count > 0 else 0
        return node.specimen_count, node.my_species_count
    total_specimens = 0
    total_my_species = 0
    for child in node.children:
        sp, ms = _aggregate_specimen_counts(child)
        total_specimens += sp
        total_my_species += ms
    node.specimen_count = total_specimens
    node.my_species_count = total_my_species
    return total_specimens, total_my_species


def _count_species(node):
    """Count total species under a node recursively."""
    if node.rank == "Species":
        return 1
    return sum(_count_species(c) for c in node.children)


# =========================================================================
# Data loaders
# =========================================================================

def _load_specimen_data(order_name):
    families, genera, species = set(), set(), set()
    family_counts, species_counts = {}, {}
    if not DB_PATH.exists():
        return families, genera, species, family_counts, species_counts
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("SELECT family, COUNT(*) FROM specimens WHERE order_name = ? AND family IS NOT NULL GROUP BY family", (order_name,))
    for r in c.fetchall():
        families.add(r[0]); family_counts[r[0]] = r[1]
    c.execute("SELECT species_name, COUNT(*) FROM specimens WHERE order_name = ? AND species_name IS NOT NULL GROUP BY species_name", (order_name,))
    for r in c.fetchall():
        species.add(r[0]); species_counts[r[0]] = r[1]
        parts = r[0].split()
        if parts: genera.add(parts[0])
    conn.close()
    return families, genera, species, family_counts, species_counts


def _load_superfamily_map():
    from .planner_data import load_superfamily_lookup
    return load_superfamily_lookup()


def _load_suborder_map(order_name):
    """Build family → suborder mapping from JSON config + UKSI hierarchy.

    Sources (in priority order):
    1. Explicit family lists in _suborders JSON section
    2. __suborder__ markers in sort override lists
    3. UKSI hierarchy (1-hop: family → suborder)
    4. __default__ key from JSON (catches unassigned families)
    """
    from .planner_data import SORT_OVERRIDES_PATH
    result = {}  # {family_name: suborder_name}
    default_suborder = ""

    # Load JSON config
    if SORT_OVERRIDES_PATH.exists():
        try:
            import json as _json
            with open(SORT_OVERRIDES_PATH, "r", encoding="utf-8") as f:
                data = _json.load(f)
        except Exception:
            data = {}

        # Source 1: Explicit suborder assignments
        suborders_cfg = data.get("_suborders", {}).get(order_name, {})
        for so_name, families in suborders_cfg.items():
            if so_name.startswith("_"):
                if so_name == "__default__":
                    default_suborder = families  # families is a string here
                continue
            if isinstance(families, list):
                for fam in families:
                    result[fam] = so_name

        # Source 2: Parse __suborder__ markers from sort list
        sort_list = data.get(order_name, [])
        current_so = ""
        for entry in sort_list:
            if isinstance(entry, str) and entry.startswith("__suborder__"):
                current_so = entry.replace("__suborder__", "")
            elif isinstance(entry, str) and not entry.startswith("__") and current_so:
                if entry not in result:
                    result[entry] = current_so

    # Source 3: UKSI hierarchy (1-hop family → suborder)
    if UKSI_PATH.exists():
        conn = sqlite3.connect(str(UKSI_PATH))
        c = conn.cursor()
        c.execute("""SELECT f.scientific_name, so.scientific_name FROM taxa f
                     JOIN hierarchy h ON f.tvk = h.tvk
                     JOIN taxa so ON h.parent_tvk = so.tvk AND so.rank = 'Suborder'
                     WHERE f.rank = 'Family' AND f."order" = ?""", (order_name,))
        for fam, so in c.fetchall():
            if fam not in result:
                result[fam] = so
        conn.close()

    # Source 4: Apply default for unassigned families
    if default_suborder:
        if UKSI_PATH.exists():
            conn = sqlite3.connect(str(UKSI_PATH))
            c = conn.cursor()
            c.execute("""SELECT scientific_name FROM taxa
                         WHERE "order" = ? AND rank = 'Family'""", (order_name,))
            for (fam,) in c.fetchall():
                if fam not in result:
                    result[fam] = default_suborder
            conn.close()

    return result


def _load_uksi_families(order_name):
    if not UKSI_PATH.exists(): return []
    conn = sqlite3.connect(str(UKSI_PATH))
    c = conn.cursor()
    c.execute("SELECT scientific_name, sort_code FROM taxa WHERE \"order\" = ? AND rank = 'Family' AND sort_code IS NOT NULL ORDER BY sort_code", (order_name,))
    result = [(r[0], r[1]) for r in c.fetchall()]
    conn.close()
    # Apply manual sort overrides for orders with alphabetical UKSI sort codes
    from .planner_data import load_family_sort_overrides
    overrides = load_family_sort_overrides(order_name)
    if overrides:
        result = [(name, overrides.get(name, sort)) for name, sort in result]
        result.sort(key=lambda x: x[1])
    return result


def _load_uksi_subfamilies(order_name):
    """Load subfamilies grouped by family."""
    if not UKSI_PATH.exists(): return {}
    conn = sqlite3.connect(str(UKSI_PATH))
    c = conn.cursor()
    c.execute("""
        SELECT scientific_name, family, sort_code FROM taxa
        WHERE "order" = ? AND rank = 'Subfamily' AND family IS NOT NULL AND sort_code IS NOT NULL
        ORDER BY sort_code
    """, (order_name,))
    result = {}
    for name, family, sort_code in c.fetchall():
        result.setdefault(family, []).append((name, sort_code))
    conn.close()
    return result


def _load_uksi_genera_species(order_name):
    """Load genera, species, and genus→subfamily mapping."""
    if not UKSI_PATH.exists(): return {}, {}, {}
    conn = sqlite3.connect(str(UKSI_PATH))
    c = conn.cursor()

    # Genera by family
    c.execute("SELECT scientific_name, family, sort_code FROM taxa WHERE \"order\" = ? AND rank = 'Genus' AND family IS NOT NULL AND sort_code IS NOT NULL ORDER BY sort_code", (order_name,))
    gen_by_fam = {}
    genus_tvks = {}
    for name, family, sort_code in c.fetchall():
        gen_by_fam.setdefault(family, []).append((name, sort_code))

    # Species by genus
    c.execute("SELECT DISTINCT scientific_name, genus, sort_code FROM taxa WHERE \"order\" = ? AND rank = 'Species' AND genus IS NOT NULL AND sort_code IS NOT NULL ORDER BY sort_code", (order_name,))
    sp_by_gen = {}
    seen_species = set()
    for name, genus, sort_code in c.fetchall():
        if name not in seen_species:
            seen_species.add(name)
            sp_by_gen.setdefault(genus, []).append((name, sort_code))

    # Genus -> subfamily via SQL joins (direct, via Tribe, via Subtribe->Tribe)
    c.execute("""
        SELECT g.scientific_name, sf.scientific_name FROM taxa g
        JOIN hierarchy h ON g.tvk = h.tvk
        JOIN taxa sf ON h.parent_tvk = sf.tvk AND sf.rank = 'Subfamily'
        WHERE g.rank = 'Genus' AND g."order" = ?
        UNION ALL
        SELECT g.scientific_name, sf.scientific_name FROM taxa g
        JOIN hierarchy h1 ON g.tvk = h1.tvk
        JOIN hierarchy h2 ON h1.parent_tvk = h2.tvk
        JOIN taxa sf ON h2.parent_tvk = sf.tvk AND sf.rank = 'Subfamily'
        WHERE g.rank = 'Genus' AND g."order" = ?
        UNION ALL
        SELECT g.scientific_name, sf.scientific_name FROM taxa g
        JOIN hierarchy h1 ON g.tvk = h1.tvk
        JOIN hierarchy h2 ON h1.parent_tvk = h2.tvk
        JOIN hierarchy h3 ON h2.parent_tvk = h3.tvk
        JOIN taxa sf ON h3.parent_tvk = sf.tvk AND sf.rank = 'Subfamily'
        WHERE g.rank = 'Genus' AND g."order" = ?
    """, (order_name, order_name, order_name))
    gen_to_subfam = {r[0]: r[1] for r in c.fetchall()}

    conn.close()
    return gen_by_fam, sp_by_gen, gen_to_subfam


def _load_common_names():
    """Load common names from bundled JSON + UKSI species names."""
    result = {}
    family_names_path = Path(__file__).parent / "family_common_names.json"
    if family_names_path.exists():
        with open(family_names_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if not k.startswith("_"):
                result[k] = v
    if UKSI_PATH.exists():
        conn = sqlite3.connect(str(UKSI_PATH))
        c = conn.cursor()
        c.execute("SELECT t.scientific_name, cn.common_name FROM taxa t JOIN common_names cn ON t.tvk = cn.tvk WHERE t.rank = 'Species' LIMIT 50000")
        for r in c.fetchall():
            result[r[0]] = r[1]
        conn.close()
    return result
