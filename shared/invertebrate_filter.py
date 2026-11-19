"""Which taxa are not invertebrates -- the one rule behind every species count in Examen.

Plants, fungi and vertebrates entered by mistake or noted incidentally stay in Observatum
(no data change) but are not counted as species in an assessment: total species, % Key
Species, Table 5.1, Appendix C, the Species tab, the project list and the benchmark all
read the list this rule leaves.

A taxon (TVK) is NOT an invertebrate when, in order:
  1. any of its records in Observatum has a kingdom filled that is not Animalia, or a
     taxon_group that is a vertebrate group (bird, mammal, amphibian, reptile, fish);
  2. otherwise, where no record settles it (kingdom or taxon_group blank, or no record at
     all, e.g. a Data Entry row not yet committed), UKSI places it in a kingdom other than
     Animalia, or in Animalia phylum Chordata.
Anything else counts -- including an aggregate such as 'Forficula auricularia/dentata agg.'
that UKSI's invertebrate list misses: UKSI must positively say it is not an invertebrate.
"""
import re
import sqlite3

_VERTEBRATE_GROUPS = {"bird", "mammal", "terrestrial mammal", "marine mammal", "amphibian",
                      "reptile", "fish"}
_FISH = re.compile(r"^(bony|cartilaginous|jawless) fish\b")


def is_vertebrate_group(taxon_group) -> bool:
    g = str(taxon_group or "").strip().lower()
    return g in _VERTEBRATE_GROUPS or bool(_FISH.match(g))


def _batches(items, n=500):
    for i in range(0, len(items), n):
        yield items[i:i + n]


def _record_verdicts(tvks, observatum_db):
    """{tvk: True (not invertebrate) | False (records say invertebrate)}; absent = unsettled."""
    out = {}
    try:
        c = sqlite3.connect(f"file:{observatum_db}?mode=ro", uri=True)
    except sqlite3.Error:
        return out
    try:
        for batch in _batches(tvks):
            ph = ",".join("?" * len(batch))
            for tvk, kingdom, group in c.execute(
                    f"SELECT DISTINCT species_tvk, kingdom, taxon_group FROM observations "
                    f"WHERE species_tvk IN ({ph})", batch):
                k = str(kingdom or "").strip().lower()
                if (k and k != "animalia") or is_vertebrate_group(group):
                    out[tvk] = True
                elif k == "animalia" and str(group or "").strip():
                    out.setdefault(tvk, False)
    except sqlite3.Error:        # a database without the kingdom / taxon_group columns
        return {}
    finally:
        c.close()
    return out


def _uksi_verdicts(tvks, uksi_db):
    """The TVKs UKSI says are not invertebrates: another kingdom, or Animalia / Chordata."""
    out = set()
    try:
        c = sqlite3.connect(f"file:{uksi_db}?mode=ro", uri=True)
    except sqlite3.Error:
        return out
    try:
        for batch in _batches(tvks):
            ph = ",".join("?" * len(batch))
            for tvk, kingdom, phylum in c.execute(
                    f"SELECT tvk, kingdom, phylum FROM taxa WHERE tvk IN ({ph})", batch):
                k = str(kingdom or "").strip().lower()
                if k and (k != "animalia" or str(phylum or "").strip().lower() == "chordata"):
                    out.add(tvk)
    except sqlite3.Error:
        pass
    finally:
        c.close()
    return out


def non_invertebrate_tvks(tvks, observatum_db=None, uksi_db=None) -> set:
    """The subset of tvks that is not an invertebrate (see the module docstring)."""
    import paths
    tvks = list(dict.fromkeys(t for t in (tvks or []) if t))
    if not tvks:
        return set()
    verdicts = _record_verdicts(tvks, observatum_db or paths.OBSERVATUM_DB)
    out = {t for t, bad in verdicts.items() if bad}
    unsettled = [t for t in tvks if t not in verdicts]
    if unsettled:
        out |= _uksi_verdicts(unsettled, uksi_db or paths.UKSI_DB)
    return out
