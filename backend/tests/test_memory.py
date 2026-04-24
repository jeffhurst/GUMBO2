from __future__ import annotations

from pathlib import Path

from app import memory
from app.schemas import Classification, ContextSnapshot, EventLogEntry, TurnRecord


def test_ensure_memory_dirs_creates_path(tmp_path, monkeypatch):
    monkeypatch.setattr(memory.settings, "memory_turns_dir", tmp_path / "turns")
    memory.ensure_memory_dirs()
    assert (tmp_path / "turns").exists()


def test_make_turn_id_format():
    turn_id = memory.make_turn_id()
    assert len(turn_id) == 19
    assert turn_id[8] == "_"
    assert turn_id[15] == "_"


def test_save_and_load_recent_turns(tmp_path, monkeypatch):
    monkeypatch.setattr(memory.settings, "memory_turns_dir", tmp_path / "turns")
    memory.ensure_memory_dirs()

    record = TurnRecord(
        turn_id="20260424_010203_123",
        created_at="2026-04-24T01:02:03.123",
        user_input="hello",
        assistant_response="hi",
        classification=Classification(
            needs_clarification=False,
            can_respond_direct=True,
            intent="chat",
        ),
        event_log=[EventLogEntry(event="test", detail="ok")],
        context_snapshot=ContextSnapshot(boot_prompt="bp", recent_turns_loaded=0),
        error=None,
    )

    saved = memory.save_turn_record(record)
    assert saved.exists()

    recent_files = memory.list_recent_turns()
    assert len(recent_files) == 1
    assert isinstance(recent_files[0], Path)

    loaded = memory.load_recent_turns()
    assert loaded[0]["user_input"] == "hello"
