from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from .config import settings


class OllamaUnavailableError(RuntimeError):
    """Raised when Ollama cannot be reached."""


async def stream_chat(messages: list[dict]) -> AsyncIterator[str]:
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": True,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if chunk.get("done"):
                        break
    except httpx.HTTPError as exc:
        raise OllamaUnavailableError(str(exc)) from exc
