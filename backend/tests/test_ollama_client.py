from __future__ import annotations

import json

import httpx
import pytest

from app import ollama_client


class MockStreamResponse:
    def __init__(self, lines: list[str]):
        self._lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    def raise_for_status(self):
        return None

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class MockAsyncClient:
    def __init__(self, lines: list[str]):
        self._lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    def stream(self, method, url, json):  # noqa: ANN001,A003
        return MockStreamResponse(self._lines)


@pytest.mark.asyncio
async def test_stream_chat_parses_stream(monkeypatch):
    lines = [
        json.dumps({"message": {"content": "Hel"}, "done": False}),
        json.dumps({"message": {"content": "lo"}, "done": True}),
    ]

    monkeypatch.setattr(ollama_client.httpx, "AsyncClient", lambda timeout: MockAsyncClient(lines))

    tokens = []
    async for token in ollama_client.stream_chat([{"role": "user", "content": "hi"}]):
        tokens.append(token)

    assert tokens == ["Hel", "lo"]


class FailingAsyncClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    def stream(self, method, url, json):  # noqa: ANN001,A003
        raise httpx.ConnectError("down")


@pytest.mark.asyncio
async def test_stream_chat_handles_connection_error(monkeypatch):
    monkeypatch.setattr(ollama_client.httpx, "AsyncClient", lambda timeout: FailingAsyncClient())

    with pytest.raises(ollama_client.OllamaUnavailableError):
        async for _token in ollama_client.stream_chat([{"role": "user", "content": "hi"}]):
            pass
