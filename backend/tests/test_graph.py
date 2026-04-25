from __future__ import annotations

from pathlib import Path

import pytest

from app import graph


class FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send_json(self, payload):
        self.sent.append(payload)


@pytest.mark.asyncio
async def test_empty_input_routes_to_clarification(tmp_path, monkeypatch):
    monkeypatch.setattr(graph, "stream_chat", _fake_stream)
    monkeypatch.setattr(graph, "save_turn_record", _save_to_tmp(tmp_path))
    monkeypatch.setattr(graph, "make_turn_id", lambda: "20260424_000000_000")

    ws = FakeWebSocket()
    result = await graph.run_agent_turn("", ws)

    assert "Could you share" in result["assistant_response"]
    assert result["classification"]["needs_clarification"] is True


@pytest.mark.asyncio
async def test_vague_input_routes_to_clarification(tmp_path, monkeypatch):
    monkeypatch.setattr(graph, "stream_chat", _fake_stream)
    monkeypatch.setattr(graph, "save_turn_record", _save_to_tmp(tmp_path))
    monkeypatch.setattr(graph, "make_turn_id", lambda: "20260424_000000_001")

    ws = FakeWebSocket()
    result = await graph.run_agent_turn("help", ws)

    assert result["classification"]["needs_clarification"] is True


@pytest.mark.asyncio
async def test_normal_input_routes_to_direct_response(tmp_path, monkeypatch):
    monkeypatch.setattr(graph, "stream_chat", _fake_stream)
    monkeypatch.setattr(graph, "save_turn_record", _save_to_tmp(tmp_path))
    monkeypatch.setattr(graph, "make_turn_id", lambda: "20260424_000000_002")

    ws = FakeWebSocket()
    result = await graph.run_agent_turn("Tell me a joke", ws)

    assert result["classification"]["can_respond_direct"] is True
    assert result["assistant_response"] == "Hello world"
    assert any(item.get("type") == "token" for item in ws.sent)


@pytest.mark.asyncio
async def test_event_log_and_save_turn(tmp_path, monkeypatch):
    monkeypatch.setattr(graph, "stream_chat", _fake_stream)
    monkeypatch.setattr(graph, "save_turn_record", _save_to_tmp(tmp_path))
    monkeypatch.setattr(graph, "make_turn_id", lambda: "20260424_000000_003")

    ws = FakeWebSocket()
    result = await graph.run_agent_turn("Hello there", ws)

    assert result["saved_path"].endswith("20260424_000000_003.json")
    saved_path = Path(result["saved_path"])
    assert saved_path.exists()


@pytest.mark.asyncio
async def test_boot_agent_streams_boot_response(tmp_path, monkeypatch):
    seen_messages = {}

    async def _fake_boot_stream(messages):
        seen_messages["messages"] = messages
        yield "Boot "
        yield "ready"

    monkeypatch.setattr(graph, "stream_chat", _fake_boot_stream)
    monkeypatch.setattr(graph, "save_turn_record", _save_to_tmp(tmp_path))
    monkeypatch.setattr(graph, "make_turn_id", lambda: "20260424_000000_004")

    ws = FakeWebSocket()
    await graph.boot_agent(ws)

    assert seen_messages["messages"][0]["content"].startswith("# Gumbo Boot Prompt")
    assert {"type": "assistant_message", "text": "Boot ready"} in ws.sent
    assert any(item.get("type") == "token" for item in ws.sent)


async def _fake_stream(_messages):
    yield "Hello "
    yield "world"


def _save_to_tmp(tmp_path):
    def _inner(record):
        path = tmp_path / f"{record.turn_id}.json"
        path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        return path

    return _inner
