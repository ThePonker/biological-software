"""
Vice County Lookup Service.

Determines vice county from OS Grid Reference.

Supports:
- 4-figure grid refs (10km precision) - may be ambiguous
- 6-figure grid refs (1km precision) - recommended
- 8-figure grid refs (100m precision) - rounded to 1km
- 10-figure grid refs (10m precision) - rounded to 1km

Uses a pre-computed 1km lookup table for fast queries.

Boundaries and the coast (F29, I3b, 9 Oct 2026): vc_lookup.db gives each 1 km square the VC
containing its centre. data/vc_splits.db (built by scripts/build_vc_splits.py from the BRC
boundary shapefile) lists every square a boundary runs through, with each VC's share and the
outline of its part, plus coastal squares whose centre is in the sea. assess() uses it:
  - a point (100 m or finer): the VC its position is actually in -- for a 100 m square the
    centre and four corners are tested, and if they fall in different VCs it is "on a boundary";
  - a 1 km square that a boundary crosses: "on a boundary", with each VC's share;
  - a 2 km tetrad or 10 km square: every 1 km square inside it, not just the south-west one.
The VC returned is the one at the point, or else the one with the largest share; `boundary`
says whether another VC is possible. Without vc_splits.db it falls back to vc_lookup alone.
"""

import json
import re
import sqlite3
import paths
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
from shared.db_open import connect_ro  # D9: reference data, read-only


def _in_rings(x: float, y: float, rings) -> bool:
    """Even-odd ray cast over all of a VC part's rings (holes included)."""
    inside = False
    for ring in rings:
        j = len(ring) - 1
        for i in range(len(ring)):
            xi, yi = ring[i]
            xj, yj = ring[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                inside = not inside
            j = i
    return inside


class VCLookupService:
    """
    Service for Vice County lookups from OS Grid References.
    
    Uses a pre-computed SQLite database mapping 1km grid squares to VCs.
    """
    
    # OS Grid letter codes to 100km easting/northing
    GRID_LETTERS = {
        'SV': (0, 0), 'SW': (1, 0), 'SX': (2, 0), 'SY': (3, 0), 'SZ': (4, 0), 'TV': (5, 0),
        'SQ': (0, 1), 'SR': (1, 1), 'SS': (2, 1), 'ST': (3, 1), 'SU': (4, 1), 'TQ': (5, 1), 'TR': (6, 1),
        'SL': (0, 2), 'SM': (1, 2), 'SN': (2, 2), 'SO': (3, 2), 'SP': (4, 2), 'TL': (5, 2), 'TM': (6, 2),
        'SF': (0, 3), 'SG': (1, 3), 'SH': (2, 3), 'SJ': (3, 3), 'SK': (4, 3), 'TF': (5, 3), 'TG': (6, 3),
        'SA': (0, 4), 'SB': (1, 4), 'SC': (2, 4), 'SD': (3, 4), 'SE': (4, 4), 'TA': (5, 4), 'TB': (6, 4),
        'NV': (0, 5), 'NW': (1, 5), 'NX': (2, 5), 'NY': (3, 5), 'NZ': (4, 5), 'OV': (5, 5),
        'NQ': (0, 6), 'NR': (1, 6), 'NS': (2, 6), 'NT': (3, 6), 'NU': (4, 6),
        'NL': (0, 7), 'NM': (1, 7), 'NN': (2, 7), 'NO': (3, 7), 'NP': (4, 7),
        'NF': (0, 8), 'NG': (1, 8), 'NH': (2, 8), 'NJ': (3, 8), 'NK': (4, 8),
        'NA': (0, 9), 'NB': (1, 9), 'NC': (2, 9), 'ND': (3, 9),
        'HW': (1, 10), 'HX': (2, 10), 'HY': (3, 10), 'HZ': (4, 10),
        'HP': (4, 12), 'HT': (3, 11), 'HU': (4, 11),
    }
    
    # Full VC names (1-112 for GB, 113+ for Channel Islands) - fallback if DB not available
    VC_NAMES = {
        1: "West Cornwall", 2: "East Cornwall", 3: "South Devon", 4: "North Devon",
        5: "South Somerset", 6: "North Somerset", 7: "North Wiltshire", 8: "South Wiltshire",
        9: "Dorset", 10: "Isle of Wight", 11: "South Hampshire", 12: "North Hampshire",
        13: "West Sussex", 14: "East Sussex", 15: "East Kent", 16: "West Kent",
        17: "Surrey", 18: "South Essex", 19: "North Essex", 20: "Hertfordshire",
        21: "Middlesex", 22: "Berkshire", 23: "Oxfordshire", 24: "Buckinghamshire",
        25: "East Suffolk", 26: "West Suffolk", 27: "East Norfolk", 28: "West Norfolk",
        29: "Cambridgeshire", 30: "Bedfordshire", 31: "Huntingdonshire", 32: "Northamptonshire",
        33: "East Gloucestershire", 34: "West Gloucestershire", 35: "Monmouthshire",
        36: "Herefordshire", 37: "Worcestershire", 38: "Warwickshire", 39: "Staffordshire",
        40: "Shropshire", 41: "Glamorgan", 42: "Breconshire", 43: "Radnorshire",
        44: "Carmarthenshire", 45: "Pembrokeshire", 46: "Cardiganshire",
        47: "Montgomeryshire", 48: "Merionethshire", 49: "Caernarvonshire",
        50: "Denbighshire", 51: "Flintshire", 52: "Anglesey", 53: "South Lincolnshire",
        54: "North Lincolnshire", 55: "Leicestershire", 56: "Nottinghamshire",
        57: "Derbyshire", 58: "Cheshire", 59: "South Lancashire", 60: "West Lancashire",
        61: "South-east Yorkshire", 62: "North-east Yorkshire", 63: "South-west Yorkshire",
        64: "Mid-west Yorkshire", 65: "North-west Yorkshire", 66: "Durham",
        67: "South Northumberland", 68: "North Northumberland", 69: "Westmorland",
        70: "Cumberland", 71: "Isle of Man", 72: "Dumfriesshire", 73: "Kirkcudbrightshire",
        74: "Wigtownshire", 75: "Ayrshire", 76: "Renfrewshire", 77: "Lanarkshire",
        78: "Peeblesshire", 79: "Selkirkshire", 80: "Roxburghshire", 81: "Berwickshire",
        82: "East Lothian", 83: "Midlothian", 84: "West Lothian", 85: "Fifeshire",
        86: "Stirlingshire", 87: "West Perthshire", 88: "Mid Perthshire",
        89: "East Perthshire", 90: "Angus", 91: "Kincardineshire", 92: "South Aberdeenshire",
        93: "North Aberdeenshire", 94: "Banffshire", 95: "Moray", 96: "Easterness",
        97: "Westerness", 98: "Main Argyll", 99: "Dunbartonshire", 100: "Clyde Isles",
        101: "Kintyre", 102: "South Ebudes", 103: "Mid Ebudes", 104: "North Ebudes",
        105: "West Ross", 106: "East Ross", 107: "East Sutherland", 108: "West Sutherland",
        109: "Caithness", 110: "Outer Hebrides", 111: "Orkney", 112: "Shetland",
        113: "Channel Islands",
    }
    
    # Short VC names for compact display - fallback if DB not available
    VC_SHORT_NAMES = {
        1: "W Cornwall", 2: "E Cornwall", 3: "S Devon", 4: "N Devon",
        5: "S Somerset", 6: "N Somerset", 7: "N Wilts", 8: "S Wilts",
        9: "Dorset", 10: "IoW", 11: "S Hants", 12: "N Hants",
        13: "W Sussex", 14: "E Sussex", 15: "E Kent", 16: "W Kent",
        17: "Surrey", 18: "S Essex", 19: "N Essex", 20: "Herts",
        21: "Middx", 22: "Berks", 23: "Oxon", 24: "Bucks",
        25: "E Suffolk", 26: "W Suffolk", 27: "E Norfolk", 28: "W Norfolk",
        29: "Cambs", 30: "Beds", 31: "Hunts", 32: "Northants",
        33: "E Gloucs", 34: "W Gloucs", 35: "Monmouth",
        36: "Herefs", 37: "Worcs", 38: "Warks", 39: "Staffs",
        40: "Salop", 41: "Glamorgan", 42: "Brecon", 43: "Radnor",
        44: "Carms", 45: "Pembs", 46: "Cardigan",
        47: "Montg", 48: "Merioneth", 49: "Caerns",
        50: "Denbigh", 51: "Flint", 52: "Anglesey", 53: "S Lincs",
        54: "N Lincs", 55: "Leics", 56: "Notts",
        57: "Derbys", 58: "Cheshire", 59: "S Lancs", 60: "W Lancs",
        61: "SE Yorks", 62: "NE Yorks", 63: "SW Yorks",
        64: "MW Yorks", 65: "NW Yorks", 66: "Durham",
        67: "S Northumb", 68: "N Northumb", 69: "Westmorland",
        70: "Cumberland", 71: "IoM", 72: "Dumfries", 73: "Kirkcud",
        74: "Wigtown", 75: "Ayrshire", 76: "Renfrew", 77: "Lanark",
        78: "Peebles", 79: "Selkirk", 80: "Roxburgh", 81: "Berwick",
        82: "E Lothian", 83: "Midlothian", 84: "W Lothian", 85: "Fife",
        86: "Stirling", 87: "W Perth", 88: "Mid Perth",
        89: "E Perth", 90: "Angus", 91: "Kincardine", 92: "S Aberdeen",
        93: "N Aberdeen", 94: "Banff", 95: "Moray", 96: "E Inverness",
        97: "W Inverness", 98: "Argyll Main", 99: "Dunbarton", 100: "Clyde Isles",
        101: "Kintyre", 102: "S Ebudes", 103: "Mid Ebudes", 104: "N Ebudes",
        105: "W Ross", 106: "E Ross", 107: "E Sutherland", 108: "W Sutherland",
        109: "Caithness", 110: "Outer Heb", 111: "Orkney", 112: "Shetland",
        113: "Channel Is",
    }
    
    # Class-level cache for DB-loaded names
    _db_names_loaded = False
    _db_vc_names: Dict[int, str] = {}
    _db_vc_short_names: Dict[int, str] = {}
    
    def __init__(self, db_path: str = None):
        """
        Initialize the VC lookup service.
        
        Args:
            db_path: Path to the VC lookup SQLite database.
                     If None, looks for 'vc_lookup.db' in the data directory.
        """
        self._db_path = db_path
        self._connection = None
        self._cache: Dict[str, Optional[int]] = {}  # Cache for repeated lookups
        self._splits = None                           # vc_splits.db connection; False = not found
        self._assess_cache: Dict[str, Optional[Dict[str, Any]]] = {}
        
        # Load names from database if available
        self._load_names_from_db()
    
    def _load_names_from_db(self):
        """Load VC names from database vc_names table if available."""
        if VCLookupService._db_names_loaded:
            return
        
        conn = self._get_connection()
        if conn:
            try:
                # Check if vc_names table exists
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='vc_names'"
                )
                if cursor.fetchone():
                    # Load all names
                    cursor = conn.execute("SELECT vc_number, vc_name, short_name FROM vc_names")
                    for row in cursor:
                        vc_num, vc_name, short_name = row
                        VCLookupService._db_vc_names[vc_num] = vc_name
                        VCLookupService._db_vc_short_names[vc_num] = short_name
                    VCLookupService._db_names_loaded = True
            except sqlite3.Error as e:
                print(f"[VCLookupService] Could not load vc_names table: {e}")
    
    def _get_db_path(self) -> Optional[Path]:
        """Find the VC lookup database."""
        if self._db_path:
            p = Path(self._db_path)
            if p.exists():
                return p
        
        import os
        import sys
        
        # Build comprehensive list of candidate paths
        candidates = []
        
        # 1. Check QSettings for user-configured path
        try:
            from PySide6.QtCore import QSettings
            settings = QSettings()
            custom_path = settings.value("database/vc_lookup_path")
            if custom_path:
                candidates.append(Path(custom_path))
        except Exception:
            pass
        
        # 2. From this file's location (most reliable for installed app)
        try:
            this_file = Path(__file__).resolve()
            # src/services/vc_lookup_service.py -> src/services -> src -> project root
            candidates.append(this_file.parent.parent.parent / "data" / "vc_lookup.db")
            candidates.append(this_file.parent.parent / "data" / "vc_lookup.db")
            candidates.append(this_file.parent / "data" / "vc_lookup.db")
        except Exception:
            pass
        
        # 3. From current working directory
        cwd = Path(os.getcwd())
        candidates.append(cwd / "data" / "vc_lookup.db")
        candidates.append(cwd / "src" / "data" / "vc_lookup.db")
        
        # 4. From sys.path (useful when running as module)
        if sys.path:
            candidates.append(Path(sys.path[0]) / "data" / "vc_lookup.db")
        
        # 5. Relative paths
        candidates.append(Path("data") / "vc_lookup.db")
        candidates.append(Path("data/vc_lookup.db"))
        
        # 6. User's home directory (portable fallback)
        try:
            home = Path.home()
            candidates.append(paths.VC_LOOKUP_DB)
            candidates.append(paths.VC_LOOKUP_DB)
        except Exception:
            pass
        
        # 7. For frozen executables (PyInstaller, etc.)
        if getattr(sys, 'frozen', False):
            exe_dir = Path(sys.executable).parent
            candidates.append(exe_dir / "data" / "vc_lookup.db")
            candidates.append(exe_dir / "vc_lookup.db")
        
        for path in candidates:
            try:
                if path.exists():
                    return path
            except Exception:
                pass
        
        return None
    
    def _get_connection(self) -> Optional[sqlite3.Connection]:
        """Get database connection."""
        if self._connection:
            return self._connection
        
        db_path = self._get_db_path()
        if db_path and db_path.exists():
            self._connection = connect_ro(str(db_path))
            return self._connection
        
        return None
    
    @classmethod
    def parse_grid_ref(cls, grid_ref: str) -> Optional[Tuple[int, int, int]]:
        """
        Parse a grid reference into easting, northing, and precision.
        
        Args:
            grid_ref: OS Grid Reference (e.g., "SP580207", "SP58", "SP58020070")
            
        Returns:
            Tuple of (easting, northing, precision_metres) or None if invalid
        """
        if not grid_ref:
            return None
        
        # Clean up the grid ref
        gr = grid_ref.upper().replace(" ", "")
        
        # Match pattern: 2 letters + even number of digits
        match = re.match(r'^([A-Z]{2})(\d+)$', gr)
        if not match:
            return None
        
        letters = match.group(1)
        digits = match.group(2)
        
        # Must have even number of digits
        if len(digits) % 2 != 0:
            return None
        
        # Look up the 100km square
        if letters not in cls.GRID_LETTERS:
            return None
        
        e100, n100 = cls.GRID_LETTERS[letters]
        
        # Split digits into easting and northing parts
        half = len(digits) // 2
        e_digits = digits[:half]
        n_digits = digits[half:]
        
        # Calculate precision
        precision = 10 ** (5 - half)  # 10km, 1km, 100m, 10m, 1m
        
        # Calculate full easting and northing (in metres)
        easting = e100 * 100000 + int(e_digits) * precision
        northing = n100 * 100000 + int(n_digits) * precision
        
        return (easting, northing, precision)
    
    @classmethod
    def get_1km_square(cls, grid_ref: str) -> Optional[str]:
        """
        Convert any grid reference to its 1km square (6-figure equivalent).
        
        Args:
            grid_ref: OS Grid Reference of any precision
            
        Returns:
            6-figure grid reference (e.g., "SP580207") or None if invalid
        """
        parsed = cls.parse_grid_ref(grid_ref)
        if not parsed:
            return None
        
        easting, northing, precision = parsed
        
        # Round to 1km (floor division)
        e_1km = (easting // 1000) * 1000
        n_1km = (northing // 1000) * 1000
        
        # Convert back to grid reference
        e100 = e_1km // 100000
        n100 = n_1km // 100000
        
        # Find the letters
        letters = None
        for code, (e, n) in cls.GRID_LETTERS.items():
            if e == e100 and n == n100:
                letters = code
                break
        
        if not letters:
            return None
        
        # Get the 1km digits
        e_digits = (e_1km % 100000) // 1000
        n_digits = (n_1km % 100000) // 1000
        
        return f"{letters}{e_digits:02d}{n_digits:02d}"
    
    @classmethod
    def get_10km_square(cls, grid_ref: str) -> Optional[str]:
        """
        Convert any grid reference to its 10km square (4-figure equivalent).
        
        Args:
            grid_ref: OS Grid Reference of any precision
            
        Returns:
            4-figure grid reference (e.g., "SP58") or None if invalid
        """
        parsed = cls.parse_grid_ref(grid_ref)
        if not parsed:
            return None
        
        easting, northing, precision = parsed
        
        # Round to 10km (floor division)
        e_10km = (easting // 10000) * 10000
        n_10km = (northing // 10000) * 10000
        
        # Convert back to grid reference
        e100 = e_10km // 100000
        n100 = n_10km // 100000
        
        # Find the letters
        letters = None
        for code, (e, n) in cls.GRID_LETTERS.items():
            if e == e100 and n == n100:
                letters = code
                break
        
        if not letters:
            return None
        
        # Get the 10km digits
        e_digit = (e_10km % 100000) // 10000
        n_digit = (n_10km % 100000) // 10000
        
        return f"{letters}{e_digit}{n_digit}"
    
    # ------------------------------------------------------------ boundaries (F29, I3b)

    def _splits_connection(self) -> Optional[sqlite3.Connection]:
        if self._splits is None:
            self._splits = False
            p = self._get_db_path()
            cand = (p.parent / "vc_splits.db") if p else None
            if cand and cand.exists():
                try:
                    self._splits = sqlite3.connect(cand.resolve().as_uri() + "?mode=ro", uri=True)
                except sqlite3.Error as e:
                    print(f"[VCLookupService] Could not open {cand}: {e}")
        return self._splits or None

    def _parts_for(self, squares: List[str]) -> Dict[str, List[Tuple[int, float, Any]]]:
        """1 km square -> [(vc, share of the square, rings or None)]; [] when nothing is known."""
        out: Dict[str, List[Tuple[int, float, Any]]] = {s: [] for s in squares}
        sp = self._splits_connection()
        rest = list(squares)
        if sp:
            for i in range(0, len(squares), 500):
                chunk = squares[i:i + 500]
                for sq, vc, frac, rings in sp.execute(
                        f"SELECT grid_1km, vc_number, area_fraction, rings_json FROM vc_split_squares "
                        f"WHERE grid_1km IN ({','.join('?' * len(chunk))})", chunk):
                    out[sq].append((vc, frac, json.loads(rings) if rings else None))
            rest = [s for s in squares if not out[s]]
        conn = self._get_connection()
        if conn and rest:
            for i in range(0, len(rest), 500):
                chunk = rest[i:i + 500]
                for sq, vc in conn.execute(
                        f"SELECT grid_1km, vc_number FROM vc_lookup WHERE grid_1km IN ({','.join('?' * len(chunk))})",
                        chunk):
                    out[sq].append((vc, 1.0, None))
        return out

    def assess(self, grid_ref: str) -> Optional[Dict[str, Any]]:
        """The VC of a grid reference, and whether it is on a boundary.

        Returns None for an unreadable reference or one with no VC (open sea), else
            {"vc_number", "vc_name", "boundary": bool,
             "vcs": [(vc_number, percent or None), ...]  largest first,
             "note": "" or e.g. "On the VC34/VC35 boundary: VC34 46%, VC35 54%"}
        """
        from shared import osgb
        key = (grid_ref or "").upper().replace(" ", "")
        if key in self._assess_cache:
            return self._assess_cache[key]
        p = osgb.gridref_to_en(key)
        if not p:
            return None
        e, n, size = p
        if size < 1000:
            e0, n0 = e - e % 1000, n - n % 1000
            squares = [osgb.en_to_gridref(e0, n0, 4)]
        else:
            squares = [osgb.en_to_gridref(x, y, 4) for x in range(e, e + size, 1000)
                       for y in range(n, n + size, 1000)]
        squares = [s for s in squares if s]
        parts = self._parts_for(squares)
        result = None
        if size < 1000:
            pieces = parts.get(squares[0], []) if squares else []
            if len({vc for vc, _, _ in pieces}) > 1 and any(r for _, _, r in pieces):
                pts = [(e + size / 2, n + size / 2)]
                if size >= 100:
                    pts += [(e, n), (e + size, n), (e, n + size), (e + size, n + size)]
                hits = []
                for x, y in pts:
                    hits.append(next((vc for vc, _, r in pieces if r and _in_rings(x - e0, y - n0, r)), None))
                found = [h for h in hits if h is not None]
                if found:
                    vcs = list(dict.fromkeys(([hits[0]] if hits[0] else []) + found))
                    result = {"vc_number": vcs[0], "boundary": len(vcs) > 1,
                              "vcs": [(v, None) for v in vcs]}
                    if len(vcs) > 1:
                        result["note"] = (f"On the {'/'.join(f'VC{v}' for v in vcs)} boundary: "
                                          f"this {size} m square crosses it")
        if result is None:
            share: Dict[int, float] = {}
            for pieces in parts.values():
                for vc, frac, _ in pieces:
                    share[vc] = share.get(vc, 0.0) + frac
            if not share:
                self._assess_cache[key] = None
                return None
            total = sum(share.values())
            ranked = sorted(share.items(), key=lambda kv: -kv[1])
            vcs = [(vc, round(100 * a / total)) for vc, a in ranked]
            result = {"vc_number": ranked[0][0], "boundary": len(ranked) > 1, "vcs": vcs}
            if len(ranked) > 1:
                what = {1000: "1 km square", 2000: "tetrad", 10000: "10 km square"}.get(size, "square")
                result["note"] = (f"On the {'/'.join(f'VC{v}' for v, _ in vcs)} boundary: this {what} is "
                                  + ", ".join(f"VC{v} {pc}%" if pc else f"VC{v} <1%" for v, pc in vcs))
        result.setdefault("note", "")
        result["vc_name"] = self.get_vc_name(result["vc_number"])
        self._assess_cache[key] = result
        return result

    def get_vc_from_grid_ref(self, grid_ref: str) -> Optional[Tuple[int, str]]:
        """
        Get vice county from grid reference.
        
        Args:
            grid_ref: OS Grid Reference (4, 6, 8, or 10 figure)
            
        Returns:
            Tuple of (vc_number, vc_name), or None if not found.
            On a boundary this is the VC at the point, or with the largest share -- see assess().
        """
        if not grid_ref:
            return None
        try:
            a = self.assess(grid_ref)
        except Exception as e:                       # never let the boundary check stop a lookup
            print(f"[VCLookupService] assess({grid_ref!r}) failed: {e}")
            a = False
        if a is not False:
            return (a["vc_number"], a["vc_name"]) if a else None
        
        # Get the 1km square
        square_1km = self.get_1km_square(grid_ref)
        if not square_1km:
            return None
        
        # Check cache
        if square_1km in self._cache:
            vc_num = self._cache[square_1km]
            if vc_num:
                return (vc_num, self.get_vc_name(vc_num))
            return None
        
        # Look up in database
        conn = self._get_connection()
        if conn:
            try:
                cursor = conn.execute(
                    "SELECT vc_number FROM vc_lookup WHERE grid_1km = ?",
                    (square_1km,)
                )
                row = cursor.fetchone()
                if row:
                    vc_num = row[0]
                    self._cache[square_1km] = vc_num
                    return (vc_num, self.get_vc_name(vc_num))
            except sqlite3.Error:
                pass
        
        # Cache the miss
        self._cache[square_1km] = None
        return None
    

    def get_vc_batch(self, grid_refs: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Batch lookup multiple grid references for VC.
        
        Much faster than calling get_vc_from_grid_ref repeatedly.
        """
        if not grid_refs:
            return {}
        
        results = {}
        squares_to_lookup = {}
        
        for grid in grid_refs:
            if not grid:
                results[grid] = {"vc_number": None, "vc_name": "", "warning": "No grid reference provided", "error": ""}
                continue
            
            is_valid, msg = self.validate_grid_ref(grid)
            if not is_valid:
                results[grid] = {"vc_number": None, "vc_name": "", "warning": "", "error": f"Invalid grid reference: {msg}"}
                continue
            
            square_1km = self.get_1km_square(grid)
            if not square_1km:
                results[grid] = {"vc_number": None, "vc_name": "", "warning": "", "error": "Could not parse grid reference"}
                continue
            
            if square_1km not in squares_to_lookup:
                squares_to_lookup[square_1km] = []
            squares_to_lookup[square_1km].append({"original": grid, "warning": msg if "Warning" in msg else ""})
        
        if squares_to_lookup:
            conn = self._get_connection()
            if conn:
                try:
                    placeholders = ",".join(["?" for _ in squares_to_lookup])
                    query = f"SELECT grid_1km, vc_number FROM vc_lookup WHERE grid_1km IN ({placeholders})"
                    cursor = conn.execute(query, tuple(squares_to_lookup.keys()))
                    
                    vc_by_square = {}
                    for row in cursor:
                        vc_by_square[row[0]] = row[1]
                    
                    for square, grid_list in squares_to_lookup.items():
                        vc_num = vc_by_square.get(square)
                        vc_name = self.get_vc_name(vc_num) if vc_num else ""
                        
                        for item in grid_list:
                            if vc_num:
                                results[item["original"]] = {"vc_number": vc_num, "vc_name": vc_name, "warning": item["warning"], "error": ""}
                            else:
                                results[item["original"]] = {"vc_number": None, "vc_name": "", "warning": item["warning"] or "Could not determine Vice County", "error": ""}
                except Exception as e:
                    print(f"[VCLookupService] Batch lookup error: {e}")

        # boundaries, the coast and coarse refs (F29, I3b): the same answer as assess()
        for grid, res in results.items():
            if not grid or res.get("error"):
                continue
            try:
                a = self.assess(grid)
            except Exception as e:
                print(f"[VCLookupService] assess({grid!r}) failed: {e}")
                continue
            res["boundary"] = bool(a and a["boundary"])
            res["vcs"] = a["vcs"] if a else []
            if a:
                res["vc_number"], res["vc_name"] = a["vc_number"], a["vc_name"]
                if a["note"]:
                    res["warning"] = a["note"]
                elif "VC may be ambiguous" in res.get("warning", "") or res.get("warning") == "Could not determine Vice County":
                    res["warning"] = ""
        
        return results

    def get_vc_number(self, grid_ref: str) -> Optional[int]:
        """
        Get vice county number from grid reference.
        
        Args:
            grid_ref: OS Grid Reference
            
        Returns:
            VC number or None if not found
        """
        result = self.get_vc_from_grid_ref(grid_ref)
        return result[0] if result else None
    
    def get_vc_name(self, vc_number: int) -> Optional[str]:
        """Get full VC name from number."""
        # Try DB-loaded names first
        if VCLookupService._db_vc_names:
            return VCLookupService._db_vc_names.get(vc_number, self.VC_NAMES.get(vc_number))
        return self.VC_NAMES.get(vc_number)
    
    def get_vc_short_name(self, vc_number: int) -> Optional[str]:
        """Get short VC name from number."""
        # Try DB-loaded names first
        if VCLookupService._db_vc_short_names:
            return VCLookupService._db_vc_short_names.get(vc_number, self.VC_SHORT_NAMES.get(vc_number))
        return self.VC_SHORT_NAMES.get(vc_number)
    
    @classmethod
    def get_short_name(cls, vc_number: int) -> Optional[str]:
        """Class method to get short VC name from number."""
        # Try DB-loaded names first
        if cls._db_vc_short_names:
            return cls._db_vc_short_names.get(vc_number, cls.VC_SHORT_NAMES.get(vc_number))
        return cls.VC_SHORT_NAMES.get(vc_number)
    
    def get_vice_county(self, grid_ref: str) -> Optional[Dict[str, Any]]:
        """
        Get vice county as a dict from grid reference.
        
        This method is used by dialogs that expect a dict with 'number' and 'name' keys.
        
        Args:
            grid_ref: OS Grid Reference
            
        Returns:
            Dict with 'number', 'name', and 'short_name' keys, or None if not found
        """
        result = self.get_vc_from_grid_ref(grid_ref)
        if result:
            return {
                'number': result[0], 
                'name': result[1],
                'short_name': self.get_vc_short_name(result[0])
            }
        return None
    
    def get_vc_number_from_name(self, vc_name: str) -> Optional[int]:
        """Get VC number from name."""
        vc_name_lower = vc_name.lower().strip()
        
        # Check DB names first
        if VCLookupService._db_vc_names:
            for num, name in VCLookupService._db_vc_names.items():
                if name.lower() == vc_name_lower:
                    return num
        
        # Fallback to class names
        for num, name in self.VC_NAMES.items():
            if name.lower() == vc_name_lower:
                return num
        return None
    
    def format_vc(self, vc_number: int) -> str:
        """Format VC as 'number - name'."""
        name = self.get_vc_name(vc_number)
        if name:
            return f"VC{vc_number} {name}"
        return f"VC{vc_number}"
    
    def format_vc_short(self, vc_number: int) -> str:
        """Format VC with short name as 'number - short_name'."""
        name = self.get_vc_short_name(vc_number)
        if name:
            return f"{vc_number} - {name}"
        return f"VC{vc_number}"
    
    def validate_grid_ref(self, grid_ref: str) -> Tuple[bool, str]:
        """
        Validate a grid reference.
        
        Args:
            grid_ref: OS Grid Reference to validate
            
        Returns:
            Tuple of (is_valid, message)
        """
        if not grid_ref:
            return (False, "Grid reference is empty")
        
        parsed = self.parse_grid_ref(grid_ref)
        if not parsed:
            return (False, "Invalid grid reference format")
        
        easting, northing, precision = parsed
        
        # Check if within GB bounds (roughly)
        if easting < 0 or easting > 700000:
            return (False, "Easting out of range for GB")
        if northing < 0 or northing > 1300000:
            return (False, "Northing out of range for GB")
        
        # Warn about low precision
        if precision >= 10000:
            return (True, "Warning: 4-figure grid ref (10km precision) - VC may be ambiguous")
        
        return (True, "Valid")
    
    def close(self):
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None


# Singleton instance
_vc_service: Optional[VCLookupService] = None


def get_vc_service(db_path: str = None) -> VCLookupService:
    """Get the singleton VC lookup service instance."""
    global _vc_service
    if _vc_service is None:
        _vc_service = VCLookupService(db_path)
    return _vc_service
