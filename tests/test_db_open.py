"""Reference databases open read-only (backlog D9, 9 Oct 2026)."""
import sqlite3

import pytest

from shared.db_open import connect_ro


def _db(path):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE taxa (tvk TEXT, scientific_name TEXT)")
    c.execute("INSERT INTO taxa VALUES ('T1', 'Carabus nemoralis')")
    c.commit()
    c.close()
    return path


def test_connect_ro_reads_but_will_not_write(tmp_path):
    d = tmp_path / "Wil J. Heeney" / "Biological Software"
    d.mkdir(parents=True)
    db = _db(d / "uksi.db")
    c = connect_ro(db)
    assert c.execute("SELECT scientific_name FROM taxa").fetchone() == ("Carabus nemoralis",)
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        c.execute("DELETE FROM taxa")


def test_codex_repository_connection_is_read_only(tmp_path):
    from shared.repositories.codex_repository import CodexRepository
    repo = CodexRepository(db_path=_db(tmp_path / "codex.db"), pantheon_path=tmp_path / "p.db")
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        repo._get_conn().execute("DELETE FROM taxa")


def test_observatum_uksi_connection_is_read_only(tmp_path):
    from Observatum.src.models.database import DatabaseManager
    dm = DatabaseManager()
    dm.set_uksi_path(str(_db(tmp_path / "uksi.db")))
    assert dm.execute_uksi("SELECT tvk FROM taxa")[0]["tvk"] == "T1"
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        with dm.uksi_connection() as c:
            c.execute("DELETE FROM taxa")
