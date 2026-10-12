"""Which older names to search for a species: UKSI synonyms, checked (LEC3).

UKSI gives some names as synonyms of the wrong species. The July 2025 NAMES
sheet maps Lamia sartor, L. sutor and L. titillator to Lamia textor, although
the first two are Monochamus sartor and M. sutor (fault F25). Until UKSI is
corrected, Lector checks every synonym before it is searched and holds back:

  1. names on an exclusion list: the suite's scripts/uksi_synonym_corrections.csv
     ('exclude' rows) and your own data/lector_synonyms.txt ('-' lines);
  2. names whose epithet is current for another species of the same family
     ('Lamia sutor' while 'Monochamus sutor' is current);
  3. names UKSI also gives for another taxon, or that are themselves current.

Names to add (e.g. Cerambyx textor, the original combination) come from the
corrections CSV ('add' rows) and '+' lines in data/lector_synonyms.txt; a '+'
line also confirms a name the checks would hold back.

data/lector_synonyms.txt (one change per line, '#' starts a comment):
    - Lamia sartor                      never search this name, for any species
    - Lamia sutor @ Lamia textor        ...only when searching Lamia textor
    + Cerambyx textor @ Lamia textor    also search this name for Lamia textor
The species after '@' can be a name or a TVK. Text after '|' is your reason.
"""
import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import config

LATIN = re.compile(r"^[A-Z][a-z]+(?: \([A-Z][a-z]+\))? [a-z][a-z-]+"
                   r"(?: (?:(?:var|subsp|ssp|f|ab)\. )?[a-z][a-z-]+)?$")
SUITE_CORRECTIONS = Path(getattr(config.paths, "SCRIPTS_DIR", config.DATA_DIR.parent / "scripts")) \
    / "uksi_synonym_corrections.csv"
USER_FILE_HEADER = """\
# Lector synonym list -- your corrections to UKSI's synonyms (see Lector/synonyms.py).
# One change per line. The species after '@' can be a name or a TVK; text after '|'
# is your reason, shown in Lector.
#   - Lamia sartor                      never search this name, for any species
#   - Lamia sutor @ Lamia textor        ...only when searching Lamia textor
#   + Cerambyx textor @ Lamia textor    also search this name for Lamia textor
"""


def plain(name):
    """Name without a subgenus in brackets: 'Lamia (Lamia) textor' -> 'Lamia textor'."""
    return " ".join(w for w in (name or "").split() if not w.startswith("("))


def epithet(name):
    parts = plain(name).split()
    return parts[-1].lower() if len(parts) > 1 else ""


def is_latin(name):
    return bool(LATIN.match((name or "").strip()))


@dataclass
class Rule:
    sign: str                 # '+' add / '-' exclude
    name: str
    target: str = None        # species name or TVK; None = every species
    reason: str = ""
    source: str = "your list"

    def applies_to(self, accepted_name, tvk):
        if not self.target:
            return True
        t = self.target.strip().lower()
        return t in {(accepted_name or "").lower(), (tvk or "").lower()}


@dataclass
class SynonymRules:
    rules: list = field(default_factory=list)
    user_file: Path = None
    warnings: list = field(default_factory=list)

    @classmethod
    def load(cls, user_file=None, suite_csv=SUITE_CORRECTIONS):
        self = cls(user_file=Path(user_file or config.SYNONYM_FILE))
        if suite_csv and Path(suite_csv).exists():
            with Path(suite_csv).open(encoding="utf-8-sig", newline="") as fh:
                for row in csv.DictReader(fh):
                    action = (row.get("action") or "").strip().lower()
                    if action in ("exclude", "add") and row.get("synonym"):
                        self.rules.append(Rule("-" if action == "exclude" else "+",
                                               row["synonym"].strip(),
                                               (row.get("tvk") or "").strip() or None,
                                               (row.get("reason") or "").strip(),
                                               "suite corrections list"))
        if self.user_file.exists():
            for n, line in enumerate(self.user_file.read_text(encoding="utf-8-sig").splitlines(), 1):
                rule = parse_line(line)
                if rule is False:
                    self.warnings.append(f"{self.user_file.name} line {n} not understood: {line!r}")
                elif rule:
                    self.rules.append(rule)
        return self

    def excluded(self, name, accepted_name, tvk):
        for r in self.rules:
            if r.sign == "-" and plain(r.name).lower() == plain(name).lower() \
                    and r.applies_to(accepted_name, tvk):
                return r
        return None

    def additions(self, accepted_name, tvk):
        return [r for r in self.rules if r.sign == "+" and r.applies_to(accepted_name, tvk)]

    def remember(self, sign, name, target=None, reason=""):
        """Append a line to the user's file (made with its header if missing)."""
        line = f"{sign} {name.strip()}" + (f" @ {target.strip()}" if target else "") \
            + (f" | {reason.strip()}" if reason else "")
        f = self.user_file
        f.parent.mkdir(parents=True, exist_ok=True)
        text = f.read_text(encoding="utf-8-sig") if f.exists() else USER_FILE_HEADER
        if not text.endswith("\n"):
            text += "\n"
        f.write_text(text + line + "\n", encoding="utf-8")
        self.rules.append(parse_line(line))
        return line


def parse_line(line):
    """Rule, None for a blank/comment line, False if not understood."""
    line = line.split("#", 1)[0].strip()
    if not line:
        return None
    m = re.match(r"^([+-])\s*([^@|]+?)\s*(?:@\s*([^|]+?)\s*)?(?:\|\s*(.*))?$", line)
    if not m:
        return False
    return Rule(m.group(1), m.group(2), m.group(3) or None, (m.group(4) or "").strip())


def _held_back(uksi, name, accepted_name, tvk, family):
    """(reason, conflict_name, conflict_tvk) or None when the name looks right."""
    ep, acc_ep = epithet(name), epithet(accepted_name)
    if ep and ep != acc_ep:
        for t in uksi.species_with_epithet(ep, family, exclude_tvk=tvk):
            return (f"Held back: epithet is current in {t['scientific_name']}"
                    f" ({t['tvk']})", t["scientific_name"], t["tvk"])
    for other in uksi.recommended_for(name):
        if other and other != tvk:
            t = uksi.taxon(other) or {"scientific_name": other}
            return (f"Held back: UKSI also gives this name for {t['scientific_name']}"
                    f" ({other})", t["scientific_name"], other)
    for t in uksi.taxa_named(plain(name)):
        if t["tvk"] != tvk:
            return (f"Held back: this is the current name of another taxon ({t['tvk']})",
                    t["scientific_name"], t["tvk"])
    return None


def candidate_names(uksi, accepted_name, tvk, rules=None):
    """Every name that could be searched for a species, checked.

    Returns dicts, accepted name first:
      name, origin ('accepted' | 'uksi_synonym' | 'user_added'), included (bool),
      held_back_reason (str or None), conflict_name, conflict_tvk, source.
    """
    rules = rules or SynonymRules()
    family = (uksi.taxon(tvk) or {}).get("family") if tvk else None
    out = [dict(name=accepted_name, origin="accepted", included=True, held_back_reason=None,
                conflict_name=None, conflict_tvk=None, source="UKSI accepted name")]
    seen = {plain(accepted_name).lower()}
    adds = {plain(r.name).lower(): r for r in rules.additions(accepted_name, tvk)}
    for name, source in (uksi.synonym_names(tvk) if tvk else []):
        name = (name or "").strip()
        key = plain(name).lower()
        if key in seen or not is_latin(name):
            continue
        seen.add(key)
        c = dict(name=name, origin="uksi_synonym", included=True, held_back_reason=None,
                 conflict_name=None, conflict_tvk=None,
                 source="UKSI synonyms" if source == "synonyms" else "UKSI names list")
        held = _held_back(uksi, name, accepted_name, tvk, family)
        if held and key not in adds:
            c.update(included=False, held_back_reason=held[0], conflict_name=held[1],
                     conflict_tvk=held[2])
        elif held:
            c["source"] += " (confirmed on your list)"
        out.append(c)
    for key, r in adds.items():
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(name=r.name.strip(), origin="user_added", included=True,
                        held_back_reason=None, conflict_name=None, conflict_tvk=None,
                        source=r.source + (f": {r.reason}" if r.reason else "")))
    for c in out[1:]:
        rule = rules.excluded(c["name"], accepted_name, tvk)
        if rule and c["held_back_reason"]:
            c["held_back_reason"] += f"; also on the {rule.source}"
        elif rule:
            c.update(included=False, held_back_reason=f"Held back: on the {rule.source}"
                     + (f" ({rule.reason})" if rule.reason else ""))
    return out
