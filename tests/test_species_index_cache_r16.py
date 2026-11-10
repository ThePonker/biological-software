"""Round 16 C4: the species index is cached on disk and searches give identical results."""
import sqlite3

from shared import species_index_cache as disk
from shared import species_search as ss

ROWS = [
    ("T1", "Rhagium mordax", "Species", "Cerambycidae", "Coleoptera", "Rhagium", "Animalia", "T9"),
    ("T2", "Rutpela maculata", "Species", "Cerambycidae", "Coleoptera", "Rutpela", "Animalia", "T9"),
    ("T3", "Bombus lucorum agg.", "Species aggregate", "Apidae", "Hymenoptera", "Bombus",
     "Animalia", None),
    ("T4", "Müllers beetle", "Species", "Carabidae", "Coleoptera", "Mullerus", "Animalia", None),
    ("T9", "Cerambycidae", "Family", "Cerambycidae", "Coleoptera", None, "Animalia", None),
]
QUERIES = ["rhag mor", "mor rhag", "Rhagium mordx", "spotted longhorn", "Strangalia maculata",
           "Mullers", "bombus lucorum agg.", "longhorn", "zzzz"]


def _make(path):
    c = sqlite3.connect(path)
    c.execute('CREATE TABLE taxa (tvk, scientific_name, rank, family, "order", genus, kingdom, '
              'parent_tvk)')
    c.executemany("INSERT INTO taxa VALUES (?,?,?,?,?,?,?,?)", ROWS)
    c.execute("CREATE TABLE taxon_qualifiers (tvk, qualifier, label)")
    c.execute("INSERT INTO taxon_qualifiers VALUES ('T3', 'agg.', 'Bombus lucorum agg.')")
    c.execute("CREATE TABLE common_names (common_name, tvk, preferred)")
    c.executemany("INSERT INTO common_names VALUES (?,?,?)",
                  [("Spotted Longhorn", "T2", 1), ("Longhorn Beetle", "T9", 1)])
    c.execute("CREATE TABLE synonyms (synonym, tvk)")
    c.execute("INSERT INTO synonyms VALUES ('Strangalia maculata', 'T2')")
    c.commit()
    c.close()


def _fresh(monkeypatch):
    monkeypatch.setattr(ss, "_cache", {})


def _results(path, cache_dir):
    return [ss.get_index(str(path), cache_dir=str(cache_dir)).search(q, limit=None)
            for q in QUERIES]


def test_cached_index_gives_identical_results(tmp_path, monkeypatch):
    db, cdir = tmp_path / "uksi.db", tmp_path / "cache"
    _make(db)
    _fresh(monkeypatch)
    built = _results(db, cdir)
    assert len(list(cdir.glob("species_index_*.bin"))) == 1 and not list(cdir.glob("*.tmp"))
    _fresh(monkeypatch)
    calls = []
    monkeypatch.setattr(ss.SpeciesIndex, "__init__", lambda *a, **k: calls.append(1))
    loaded = _results(db, cdir)                      # from the file: no build
    assert not calls and loaded == built
    assert any(built)                                # the queries do find things
    idx = ss.get_index(str(db), cache_dir=str(cdir))
    assert idx.tvk_for_name("Strangalia maculata") == "T2" and idx.ancestors("T1") == ["T1", "T9"]
    assert idx.members("T9") == [0, 1]


def test_changed_source_or_bad_file_rebuilds(tmp_path, monkeypatch):
    db, cdir = tmp_path / "uksi.db", tmp_path / "cache"
    _make(db)
    _fresh(monkeypatch)
    _results(db, cdir)
    c = sqlite3.connect(db)
    c.execute("INSERT INTO taxa VALUES ('T5','Abax parallelepipedus','Species','Carabidae',"
              "'Coleoptera','Abax','Animalia',NULL)")
    c.commit()
    c.close()
    _fresh(monkeypatch)
    assert ss.get_index(str(db), cache_dir=str(cdir)).search("abax par")      # not the old index
    _fresh(monkeypatch)
    (cache_file,) = cdir.glob("species_index_*.bin")
    cache_file.write_bytes(b"not a cache")
    assert ss.get_index(str(db), cache_dir=str(cdir)).search("abax par")
    assert disk.load(cache_file, str(db)) is not None                          # rewritten


def test_code_version_invalidates(tmp_path, monkeypatch):
    db, cdir = tmp_path / "uksi.db", tmp_path / "cache"
    _make(db)
    _fresh(monkeypatch)
    _results(db, cdir)
    (cache_file,) = cdir.glob("species_index_*.bin")
    assert disk.load(cache_file, str(db)) is not None
    monkeypatch.setattr(disk, "CODE_VERSION", disk.CODE_VERSION + 1)
    assert disk.load(cache_file, str(db)) is None


def test_empty_wal_is_ignored_and_nonempty_wal_means_no_cache(tmp_path, monkeypatch):
    db, cdir = tmp_path / "uksi.db", tmp_path / "cache"
    _make(db)
    _fresh(monkeypatch)
    _results(db, cdir)
    (cache_file,) = cdir.glob("species_index_*.bin")
    wal = tmp_path / "uksi.db-wal"
    wal.write_bytes(b"")                                 # a shutdown checkpoint leaves this
    assert disk.load(cache_file, str(db)) is not None
    wal.write_bytes(b"x" * 32)                           # commits not yet in the main file
    assert disk.make_header(str(db)) is None and disk.load(cache_file, str(db)) is None
    assert disk.save(ss.get_index(str(db), cache_dir=str(cdir)), cache_file, None) is False


def test_header_carries_source_hash_and_default_dir_is_local(tmp_path, monkeypatch):
    db = tmp_path / "uksi.db"
    _make(db)
    h = disk.make_header(str(db))
    assert len(h["src_hash"]) == 40 and len(h["src"]) == 3
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr("shared.away_mode.away_active", lambda: False)
    assert disk.default_cache_dir() == tmp_path / "local" / "BiologicalSoftware" / "cache"


def test_explicit_path_without_cache_dir_is_not_cached(tmp_path):
    assert disk.cache_file_for(str(tmp_path / "x.db"), str(tmp_path / "x.db")) is None
