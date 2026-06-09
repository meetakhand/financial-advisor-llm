import sqlite3
from pathlib import Path

from advisor.agent import memory


def test_profile_roundtrip(monkeypatch, tmp_path):
    db = tmp_path / "test_profile.db"
    monkeypatch.setattr(memory, "DB_PATH", db)
    memory.save_profile("alice", {"age": 30, "risk_tolerance": "moderate"})
    got = memory.load_profile("alice")
    assert got["age"] == 30


def test_profile_missing(monkeypatch, tmp_path):
    db = tmp_path / "test_profile2.db"
    monkeypatch.setattr(memory, "DB_PATH", db)
    assert memory.load_profile("nobody") == {}


def test_conversation_log(monkeypatch, tmp_path):
    db = tmp_path / "test_profile3.db"
    monkeypatch.setattr(memory, "DB_PATH", db)
    memory.log_message("u", "user", "hi")
    memory.log_message("u", "assistant", "hello")
    msgs = memory.recent_messages("u", limit=5)
    assert [m["role"] for m in msgs] == ["user", "assistant"]
