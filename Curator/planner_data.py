"""
Collection Planner — Data Layer

Loads specimen data from observatum.db, manages mounting profiles,
and runs the box allocation algorithm with superfamily-aware splitting.
"""

import json
import math
import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import paths
from pathlib import Path
from dataclasses import dataclass, field
from shared.db_open import connect_ro  # D9: reference data, read-only


PROFILES_PATH = Path(__file__).parent / "mounting_profiles.json"
SORT_OVERRIDES_PATH = Path(__file__).parent / "family_sort_overrides.json"
DB_PATH = paths.OBSERVATUM_DB
UKSI_PATH = paths.UKSI_DB


# =========================================================================
# Config problems (CUR-3): a config file that is missing or unreadable is
# recorded here and shown on screen, not silently replaced by defaults.
# =========================================================================

_config_problems = []


def note_config_problem(message: str):
    if message not in _config_problems:
        _config_problems.append(message)


def config_problems() -> list:
    """Every config problem met so far this session, in order."""
    return list(_config_problems)


# =========================================================================
# Data classes
# =========================================================================

@dataclass
class SpecimenSize:
    key: str
    label: str
    width_mm: int
    height_mm: int


@dataclass
class BoxSize:
    key: str
    label: str
    width_mm: int
    height_mm: int


@dataclass
class FamilyData:
    family: str
    specimen_count: int
    species_count: int
    species: list
    sort_key: int
    profile_key: str = "standard"
    superfamily: str = ""
    part: int = 0          # 1, 2, ... for a family split across boxes (CUR-1)

    @property
    def label(self):
        return f"{self.family} ({self.specimen_count} sp)"


@dataclass
class BoxAllocation:
    box_number: int
    families: list = field(default_factory=list)
    rows_used: float = 0
    total_rows: float = 0
    capacity_pct: float = 0

    @property
    def label(self):
        if not self.families:
            return f"Box {self.box_number}: Empty"
        first = self.families[0].family
        last = self.families[-1].family
        if first == last:
            return f"Box {self.box_number}: {first}"
        return f"Box {self.box_number}: {first} \u2014 {last}"


# =========================================================================
# Profile Manager
# =========================================================================

class ProfileManager:
    """Loads and manages mounting profiles and box sizes."""

    def __init__(self):
        self._data = {}
        self._sizes = {}
        self._boxes = {}
        self._family_profiles = {}
        self.load()

    def load(self):
        empty = {"specimen_sizes": {}, "box_sizes": {}, "family_profiles": {}}
        self.problem = ""
        if PROFILES_PATH.exists():
            try:
                with open(PROFILES_PATH, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (OSError, ValueError) as e:
                self.problem = (f"{PROFILES_PATH.name} could not be read ({e}): "
                                "no box or specimen sizes, so Box Layout is empty.")
                self._data = empty
        else:
            self.problem = (f"{PROFILES_PATH.name} is missing from the Curator folder: "
                            "no box or specimen sizes, so Box Layout is empty.")
            self._data = empty
        if self.problem:
            note_config_problem(self.problem)
        self._sizes = {}
        for key, d in self._data.get("specimen_sizes", {}).items():
            self._sizes[key] = SpecimenSize(
                key=key, label=d["label"],
                width_mm=d["width_mm"], height_mm=d["height_mm"],
            )
        self._boxes = {}
        for key, d in self._data.get("box_sizes", {}).items():
            self._boxes[key] = BoxSize(
                key=key, label=d["label"],
                width_mm=d["width_mm"], height_mm=d["height_mm"],
            )
        self._family_profiles = dict(self._data.get("family_profiles", {}))

    def save(self):
        self._data["family_profiles"] = dict(self._family_profiles)
        with open(PROFILES_PATH, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=4, ensure_ascii=False)

    def get_size(self, profile_key: str) -> SpecimenSize:
        return self._sizes.get(profile_key, self._sizes.get("standard"))

    def get_all_sizes(self) -> dict:
        return dict(self._sizes)

    def get_box(self, box_key: str) -> BoxSize:
        return self._boxes.get(box_key)

    def get_all_boxes(self) -> dict:
        return dict(self._boxes)

    def get_family_profile(self, family: str) -> str:
        return self._family_profiles.get(family, "standard")

    def set_family_profile(self, family: str, profile_key: str):
        self._family_profiles[family] = profile_key

    def profile_keys(self) -> list:
        return list(self._sizes.keys())


# =========================================================================
# Superfamily Lookup
# =========================================================================

def load_superfamily_lookup() -> dict:
    """
    Build family -> superfamily mapping from uksi.db via SQL joins.
    Returns dict: {"Syrphidae": "Syrphoidea", ...}
    """
    if not UKSI_PATH.exists():
        return {}
    conn = connect_ro(str(UKSI_PATH))
    c = conn.cursor()
    # Direct parent is Superfamily, or one hop via Infraorder etc.
    c.execute("""
        SELECT f.scientific_name, sf.scientific_name FROM taxa f
        JOIN hierarchy h ON f.tvk = h.tvk
        JOIN taxa sf ON h.parent_tvk = sf.tvk AND sf.rank = 'Superfamily'
        WHERE f.rank = 'Family'
        UNION ALL
        SELECT f.scientific_name, sf.scientific_name FROM taxa f
        JOIN hierarchy h1 ON f.tvk = h1.tvk
        JOIN hierarchy h2 ON h1.parent_tvk = h2.tvk
        JOIN taxa sf ON h2.parent_tvk = sf.tvk AND sf.rank = 'Superfamily'
        WHERE f.rank = 'Family'
    """)
    lookup = {r[0]: r[1] for r in c.fetchall()}
    conn.close()
    return lookup


# =========================================================================
# Family Sort Overrides
# =========================================================================

def load_family_sort_overrides(order_name: str) -> dict:
    """
    Load manual sort overrides for orders where UKSI sort codes are
    alphabetical. Returns {family_name: sort_position} or empty dict.
    Entries starting with '__' are markers (e.g. __suborder__) and skipped.
    """
    if not SORT_OVERRIDES_PATH.exists():
        return {}
    try:
        with open(SORT_OVERRIDES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        note_config_problem(f"{SORT_OVERRIDES_PATH.name} could not be read ({e}): "
                            "families are in UKSI sort order.")
        return {}
    families = data.get(order_name, [])
    if not families:
        return {}
    result = {}
    pos = 0
    for name in families:
        if name.startswith("__"):
            continue
        result[name] = pos
        pos += 1
    return result


# =========================================================================
# Data Loader
# =========================================================================

def load_families(order_name: str) -> list:
    """Load family-level specimen data for an order from observatum.db."""
    if not DB_PATH.exists():
        return []
    conn = connect_ro(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(specimens)")
    has_sort_key = "taxonomic_sort_key" in [c[1] for c in cursor.fetchall()]

    # Always load UKSI sort codes as fallback
    uksi_sort = {}
    if UKSI_PATH.exists():
        uconn = connect_ro(str(UKSI_PATH))
        uc = uconn.cursor()
        uc.execute("""
            SELECT scientific_name, sort_code FROM taxa
            WHERE rank = 'Family' AND sort_code IS NOT NULL
        """)
        uksi_sort = {r[0]: r[1] for r in uc.fetchall()}
        uconn.close()

    if has_sort_key:
        cursor.execute("""
            SELECT family, COUNT(*), COUNT(DISTINCT species_name),
                   MIN(taxonomic_sort_key)
            FROM specimens WHERE order_name = ? AND family IS NOT NULL AND family != ''
            GROUP BY family ORDER BY MIN(taxonomic_sort_key)
        """, (order_name,))
    else:
        cursor.execute("""
            SELECT family, COUNT(*), COUNT(DISTINCT species_name), 0
            FROM specimens WHERE order_name = ? AND family IS NOT NULL AND family != ''
            GROUP BY family
        """, (order_name,))

    sf_lookup = load_superfamily_lookup()
    sort_overrides = load_family_sort_overrides(order_name)
    families = []
    for family_name, spec_count, sp_count, sort_key in cursor.fetchall():
        if has_sort_key:
            cursor.execute("""
                SELECT species_name, COUNT(*) FROM specimens
                WHERE order_name = ? AND family = ?
                GROUP BY species_name ORDER BY MIN(taxonomic_sort_key)
            """, (order_name, family_name))
        else:
            cursor.execute("""
                SELECT species_name, COUNT(*) FROM specimens
                WHERE order_name = ? AND family = ?
                GROUP BY species_name ORDER BY species_name
            """, (order_name, family_name))
        species = [(r[0], r[1]) for r in cursor.fetchall()]
        # Override sort key if manual override exists for this order
        if family_name in sort_overrides:
            fam_sort = sort_overrides[family_name]
        elif has_sort_key and sort_key:
            fam_sort = sort_key
        else:
            fam_sort = uksi_sort.get(family_name, 999999)
        families.append(FamilyData(
            family=family_name, specimen_count=spec_count,
            species_count=sp_count, species=species,
            sort_key=fam_sort,
            superfamily=sf_lookup.get(family_name, ""),
        ))
    conn.close()
    families.sort(key=lambda f: f.sort_key)
    return families


def load_orders() -> list:
    """Get list of orders that have specimens."""
    if not DB_PATH.exists():
        return []
    conn = connect_ro(str(DB_PATH))
    c = conn.cursor()
    c.execute("""SELECT DISTINCT order_name, COUNT(*) FROM specimens
                 WHERE order_name IS NOT NULL AND order_name != ''
                 GROUP BY order_name ORDER BY order_name""")
    orders = [(r[0], r[1]) for r in c.fetchall()]
    conn.close()
    return orders




def load_orders_from_uksi() -> list:
    """Get list of insect orders from UKSI (no specimen data needed)."""
    if not UKSI_PATH.exists():
        return []
    conn = connect_ro(str(UKSI_PATH))
    c = conn.cursor()
    c.execute("""
        SELECT t.scientific_name, COUNT(f.scientific_name) as fam_count
        FROM taxa t
        LEFT JOIN taxa f ON f."order" = t.scientific_name AND f.rank = 'Family'
        WHERE t.rank = 'Order'
        AND t.phylum = 'Arthropoda'
        AND t.class IN ('Insecta', 'Arachnida', 'Malacostraca', 'Chilopoda', 'Diplopoda')
        GROUP BY t.scientific_name
        HAVING fam_count > 0
        ORDER BY t.scientific_name
    """)
    orders = [(r[0], r[1]) for r in c.fetchall()]
    conn.close()
    return orders

# =========================================================================
# Allocation Algorithm
# =========================================================================

def calculate_family_rows(family: FamilyData, profile_mgr: ProfileManager,
                          box, growth_pct: float) -> dict:
    """Calculate how many rows a family needs in a given box."""
    size = profile_mgr.get_size(family.profile_key)
    specimens_per_row = max(1, math.floor(box.width_mm / size.width_mm))
    base_rows = math.ceil(family.specimen_count / specimens_per_row)
    if growth_pct > 0 and base_rows > 0:
        growth_rows = max(1, round(base_rows * growth_pct / 100))
        if base_rows <= 2:
            growth_rows = 1
    else:
        growth_rows = 0
    total_rows = base_rows + growth_rows
    return {
        "family": family, "profile": size,
        "specimens_per_row": specimens_per_row,
        "base_rows": base_rows, "growth_rows": growth_rows,
        "total_rows": total_rows, "row_height_mm": size.height_mm,
        "height_mm": total_rows * size.height_mm,
    }


def allocate_to_boxes(families: list, profile_mgr: ProfileManager,
                      box_key: str, growth_pct: float = 20,
                      separator_mm: float = 8,
                      sf_separator_mm: float = 15) -> list:
    """
    Allocate families to boxes in systematic order.
    Prefers superfamily boundaries as box split points.
    """
    box = profile_mgr.get_box(box_key)
    if not box:
        return []

    available_height = box.height_mm
    boxes = []
    current_box = BoxAllocation(box_number=1, total_rows=available_height)
    current_height_used = 0
    prev_sf = ""

    for family in families:
        info = calculate_family_rows(family, profile_mgr, box, growth_pct)
        needed_height = info["height_mm"]
        is_sf_boundary = (family.superfamily != prev_sf
                          and family.superfamily != "" and prev_sf != "")

        gap = 0
        if current_box.families:
            gap = sf_separator_mm if is_sf_boundary else separator_mm
            needed_height += gap

        if info["height_mm"] > available_height:
            # A family too large for any one box is split wherever it falls:
            # its first part fills the rest of the current box, the remainder
            # whole boxes (CUR-1: it was split only at the start of a box, and
            # otherwise put whole into one box -- Carabidae at 500%).
            current_box = _split_family_across_boxes(
                family, info, boxes, current_box,
                current_height_used, gap, available_height)
            current_height_used = 0
            prev_sf = family.superfamily
            continue

        if current_height_used + needed_height > available_height:
            # Finish current box, start new one
            current_box.rows_used = current_height_used
            current_box.capacity_pct = round(
                (current_height_used / available_height) * 100)
            boxes.append(current_box)
            current_box = BoxAllocation(
                box_number=len(boxes) + 1, total_rows=available_height)
            current_height_used = 0
            needed_height = info["height_mm"]
        elif (is_sf_boundary and current_box.families
              and current_height_used / available_height > 0.85):
            # Prefer splitting at superfamily boundary if box is >85% full
            remaining = available_height - current_height_used
            if remaining < available_height * 0.15:
                current_box.rows_used = current_height_used
                current_box.capacity_pct = round(
                    (current_height_used / available_height) * 100)
                boxes.append(current_box)
                current_box = BoxAllocation(
                    box_number=len(boxes) + 1, total_rows=available_height)
                current_height_used = 0
                needed_height = info["height_mm"]

        current_box.families.append(family)
        current_height_used += needed_height
        prev_sf = family.superfamily

    if current_box.families:
        current_box.rows_used = current_height_used
        current_box.capacity_pct = round(
            (current_height_used / available_height) * 100)
        boxes.append(current_box)
    return boxes


def _split_family_across_boxes(family, info, boxes, current_box,
                               used_height, gap, available_height):
    """Split a family too large for a single box (CUR-1).

    used_height is what the current box already holds; gap the separator the
    family would need after it. The
    first part takes as many whole rows as fit there (the current box is then
    closed); the rest go into new boxes, a box of rows at a time. Specimen
    counts are shared by rows and always sum to the family's. Returns the new,
    empty current box.
    """
    row_height = info["row_height_mm"]
    total_rows = info["total_rows"]
    rows_per_box = max(1, math.floor(available_height / row_height))
    remaining_rows = total_rows
    assigned = 0
    part = 1

    def make_part(rows):
        nonlocal assigned, part
        last = rows >= remaining_rows
        count = (family.specimen_count - assigned if last
                 else round(family.specimen_count * rows / total_rows))
        assigned += count
        partial = FamilyData(
            family=f"{family.family} (part {part})",
            specimen_count=count,
            species_count=family.species_count,
            species=family.species if part == 1 else [],
            sort_key=family.sort_key,
            profile_key=family.profile_key,
            superfamily=family.superfamily,
            part=part,
        )
        part += 1
        return partial

    if current_box.families:
        fit = math.floor(max(0, available_height - used_height - gap) / row_height)
        fit = min(fit, remaining_rows)
        if fit >= 1:
            current_box.families.append(make_part(fit))
            used_height += gap + fit * row_height
            remaining_rows -= fit
        # else nothing fits: the box closes as it is
        current_box.rows_used = used_height
        current_box.capacity_pct = round((current_box.rows_used / available_height) * 100)
        boxes.append(current_box)

    while remaining_rows > 0:
        rows_this_box = min(remaining_rows, rows_per_box)
        height_used = rows_this_box * row_height
        partial = make_part(rows_this_box)
        boxes.append(BoxAllocation(
            box_number=len(boxes) + 1, families=[partial],
            rows_used=height_used, total_rows=available_height,
            capacity_pct=round((height_used / available_height) * 100),
        ))
        remaining_rows -= rows_this_box

    return BoxAllocation(box_number=len(boxes) + 1, total_rows=available_height)
