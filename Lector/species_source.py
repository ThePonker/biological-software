"""Read the species list and resolve names/TVKs/synonyms against uksi.db.

Input: a .csv with a 'tvk' and/or name column ('species', 'scientific_name',
'name', 'taxon'), or a plain text file with one name or TVK per line
('#' lines ignored). uksi.db is opened read-only.
"""
import csv
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from . import config

TVK_RE = re.compile(r"^[A-Z]{6}\d{10}$")          # e.g. NHMSYS0000123456
NAME_COLUMNS = ("species", "scientific_name", "species_name", "name", "taxon")


@dataclass
class SpeciesEntry:
    name: str                      # accepted / supplied name
    tvk: str = None
    synonyms: list = field(default_factory=list)
    held_back: list = field(default_factory=list)   # (name, reason) not searched (LEC3)
    added: list = field(default_factory=list)       # names from the user's synonym list

    def query_names(self):
        """(name, role) pairs to send to BHL, accepted name first."""
        return [(self.name, "accepted")] + [(s, "synonym") for s in self.synonyms]


def read_input(path):
    """Return a list of raw strings (names or TVKs) from a CSV or text file."""
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"✗ Input file not found: {path}")
    values = []
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            cols = {c.lower().strip(): c for c in (reader.fieldnames or [])}
            tvk_col = cols.get("tvk")
            name_col = next((cols[c] for c in NAME_COLUMNS if c in cols), None)
            if not (tvk_col or name_col):
                raise SystemExit("✗ CSV needs a 'tvk' or species-name column "
                                 f"({', '.join(NAME_COLUMNS)}).")
            for row in reader:
                val = (row.get(tvk_col) or "").strip() if tvk_col else ""
                val = val or ((row.get(name_col) or "").strip() if name_col else "")
                if val:
                    values.append(val)
    else:
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                values.append(line)
    return list(dict.fromkeys(values))           # de-duplicate, keep order


class UksiLookup:
    """Read-only name/TVK/synonym resolution. Degrades gracefully if the
    expected tables or columns are not present."""

    def __init__(self, db_path=config.UKSI_DB):
        self.conn = None
        self.warnings = []
        if not Path(db_path).exists():
            self.warnings.append(f"uksi.db not found at {db_path} - names used as supplied")
            return
        self.conn = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row
        self.taxa_ok = self._has("taxa", ("tvk", "scientific_name"))
        self.syn_ok = self._has("synonyms", ("synonym", "tvk"))
        self.family_ok = self._has("taxa", ("family", "genus", "rank"))
        self.map_ok = self._has("name_map", ("name", "recommended_tvk", "name_status"))
        if not self.taxa_ok:
            self.warnings.append("uksi.taxa (tvk, scientific_name) not found - no TVK resolution")
        if not self.syn_ok:
            self.warnings.append("uksi.synonyms (synonym, tvk) not found - no synonym search")

    def _has(self, table, columns):
        cols = {r[1] for r in self.conn.execute(f"PRAGMA table_info({table})")}
        return set(columns) <= cols

    # --- lookups used by the synonym checks and the service (read-only) ---
    def taxon(self, tvk):
        """taxa row as a dict (tvk, scientific_name, rank, family, genus) or None."""
        if not (self.conn and self.taxa_ok and tvk):
            return None
        row = self.conn.execute("SELECT * FROM taxa WHERE tvk=?", (tvk,)).fetchone()
        return dict(row) if row else None

    def taxa_named(self, name):
        """Current taxa with this exact scientific name (any case)."""
        if not (self.conn and self.taxa_ok):
            return []
        rows = self.conn.execute(
            "SELECT * FROM taxa WHERE scientific_name=? COLLATE NOCASE ORDER BY tvk",
            (name.strip(),)).fetchall()
        return [dict(r) for r in rows]

    def recommended_for(self, name):
        """TVKs UKSI recommends for an old or variant name (synonyms + name map)."""
        tvks = []
        if self.conn and self.syn_ok:
            tvks += [r[0] for r in self.conn.execute(
                "SELECT tvk FROM synonyms WHERE LOWER(synonym)=LOWER(?)", (name.strip(),))]
        if self.conn and self.map_ok:
            tvks += [r[0] for r in self.conn.execute(
                "SELECT recommended_tvk FROM name_map WHERE name=? COLLATE NOCASE",
                (name.strip(),))]
        return list(dict.fromkeys(tvks))

    def synonym_names(self, tvk):
        """(name, source) pairs UKSI gives as other names of a taxon: the
        synonyms table, then Latin S/U rows of the name map."""
        out = []
        if self.conn and self.syn_ok:
            out += [(r[0], "synonyms") for r in self.conn.execute(
                "SELECT DISTINCT synonym FROM synonyms WHERE tvk=? ORDER BY synonym", (tvk,))]
        if self.conn and self.map_ok:
            out += [(r[0], "name_map") for r in self.conn.execute(
                "SELECT DISTINCT name FROM name_map WHERE recommended_tvk=?"
                " AND name_status IN ('S','U') ORDER BY name", (tvk,))]
        return out

    def species_with_epithet(self, epithet, family, exclude_tvk=None):
        """Current species/subspecies in a family whose name ends in this epithet."""
        if not (self.conn and self.family_ok and epithet and family):
            return []
        rows = self.conn.execute(
            "SELECT tvk, scientific_name, genus FROM taxa WHERE family=? AND"
            " rank IN ('Species','Subspecies') AND scientific_name LIKE ? AND tvk != ?",
            (family, f"% {epithet}", exclude_tvk or "")).fetchall()
        return [dict(r) for r in rows]

    def family_species(self, family):
        """(tvk, scientific_name) of the species of a family, in UKSI order."""
        if not (self.conn and self.family_ok):
            return []
        return [(r[0], r[1]) for r in self.conn.execute(
            "SELECT tvk, scientific_name FROM taxa WHERE family=? AND rank='Species'"
            " ORDER BY sort_code, scientific_name", (family,))]

    def resolve(self, raw, with_synonyms=False):
        """Turn a raw name or TVK into a SpeciesEntry. With synonyms, names that
        fail the checks in Lector.synonyms are held back (entry.held_back)."""
        tvk, name = (raw, None) if TVK_RE.match(raw) else (None, raw)
        if self.conn and self.taxa_ok:
            if tvk:
                row = self.conn.execute(
                    "SELECT scientific_name FROM taxa WHERE tvk=?", (tvk,)).fetchone()
                if not row:
                    raise ValueError(f"TVK {tvk} not in uksi.taxa")
                name = row[0]
            else:
                rows = self.conn.execute(
                    "SELECT DISTINCT tvk FROM taxa WHERE scientific_name=?",
                    (name,)).fetchall()
                if len(rows) > 1:
                    self.warnings.append(f"{name}: {len(rows)} TVKs in UKSI - used first")
                tvk = rows[0][0] if rows else None
        elif tvk:
            raise ValueError(f"TVK {tvk} supplied but UKSI lookup unavailable")
        entry = SpeciesEntry(name=name, tvk=tvk)
        if with_synonyms:
            from .synonyms import SynonymRules, candidate_names
            for c in candidate_names(self, name, tvk, SynonymRules.load()):
                if c["origin"] == "accepted":
                    continue
                if c["included"]:
                    entry.synonyms.append(c["name"])
                    if c["origin"] == "user_added":
                        entry.added.append(c["name"])
                else:
                    entry.held_back.append((c["name"], c["held_back_reason"]))
        return entry

    def close(self):
        if self.conn:
            self.conn.close()
