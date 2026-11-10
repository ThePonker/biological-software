"""Round 16: away mode refuses Lector's database writes. (Codex Manager has no writable
connect now: its tabs read codex.db through connect_ro; the test pins that.)"""
import sqlite3
from pathlib import Path

import pytest

import paths
from shared.db_open import AwayReadOnly

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def away(monkeypatch):
    monkeypatch.setattr(paths, "AWAY_MODE", True, raising=False)


def test_lector_store_refuses_when_away(tmp_path, away):
    from Lector.store import LectorStore
    db = tmp_path / "lector.db"
    with pytest.raises(AwayReadOnly):
        LectorStore(db)
    assert not db.exists()


def test_lector_store_opens_when_not_away(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "AWAY_MODE", False, raising=False)
    monkeypatch.setattr("shared.away_mode.is_away_machine", lambda: False)
    from Lector.store import LectorStore
    with LectorStore(tmp_path / "lector.db") as st:
        assert st.conn.execute("SELECT 1").fetchone()[0] == 1


def test_lector_upgrade_apply_refuses_when_away(tmp_path, away):
    from Lector import upgrade
    db = tmp_path / "lector.db"
    sqlite3.connect(db).close()
    with pytest.raises(AwayReadOnly):
        upgrade.apply(db, tmp_path / "bk")
    assert not (tmp_path / "bk").exists()


def test_codex_manager_has_no_writable_connect():
    for f in (ROOT / "Codex").glob("*.py"):
        text = f.read_text(encoding="utf-8")
        assert "sqlite3.connect(" not in text and "connect_rw" not in text, f.name
