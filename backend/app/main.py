from __future__ import annotations

import asyncio
import os
import re
import signal
import sys
from contextlib import suppress

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .config import settings
from .graph import boot_agent, run_agent_turn
from .memory import ensure_memory_dirs
from .schemas import UserMessage

app = FastAPI(title=settings.app_name)
_terminal_chat_task: asyncio.Task[None] | None = None


def _read_boot_prompt_for_greeting() -> str:
    raw_prompt = settings.boot_prompt_path.read_text(encoding="utf-8").strip()
    # Keep markdown-heavy formatting out of the first assistant message.
    prompt_without_headers = re.sub(
        r"^#.*$", "", raw_prompt, flags=re.MULTILINE
    ).strip()
    return prompt_without_headers or "Gumbo is ready for your input."


async def _read_terminal_input(prompt: str) -> str | None:
    try:
        return await asyncio.to_thread(input, prompt)
    except EOFError:
        return None


async def _run_terminal_chat_session() -> None:
    print("[gumbo] Chat mode enabled. Type 'exit' to leave.")
    while True:
        user_text = await _read_terminal_input("you> ")
        if user_text is None:
            print("[gumbo] Terminal input closed. Exiting chat mode.")
            return

        cleaned = user_text.strip()
        if cleaned.lower() in {"exit", "quit", "/exit"}:
            print("[gumbo] Leaving terminal chat mode and shutting down backend.")
            os.kill(os.getpid(), signal.SIGINT)
            return
        if not cleaned:
            continue

        result = await run_agent_turn(cleaned)
        assistant_response = result.get("assistant_response", "").strip()
        if not assistant_response:
            assistant_response = (
                "I couldn't generate a response because the local model backend "
                "is unavailable."
            )
        print(f"gumbo> {assistant_response}")

        if result.get("error"):
            print(f"[gumbo] warning: {result['error']}")


async def _wait_for_backend_to_listen(
    timeout_seconds: float = 10.0, poll_interval: float = 0.1
) -> bool:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    host = settings.backend_host
    port = settings.backend_port

    while loop.time() < deadline:
        try:
            _, writer = await asyncio.open_connection(host, port)
            writer.close()
            await writer.wait_closed()
            return True
        except OSError:
            await asyncio.sleep(poll_interval)
    return False


async def _run_terminal_boot_and_chat() -> None:
    if not sys.stdin or not sys.stdin.isatty():
        return

    backend_ready = await _wait_for_backend_to_listen()
    if not backend_ready:
        print("[gumbo] warning: backend readiness check timed out; continuing.")

    print("[gumbo] Running boot prompt...")
    await boot_agent()
    await _run_terminal_chat_session()


@app.on_event("startup")
async def startup_event() -> None:
    global _terminal_chat_task
    ensure_memory_dirs()
    _terminal_chat_task = asyncio.create_task(_run_terminal_boot_and_chat())


@app.on_event("shutdown")
async def shutdown_event() -> None:
    global _terminal_chat_task
    if _terminal_chat_task is None:
        return
    _terminal_chat_task.cancel()
    with suppress(asyncio.CancelledError):
        await _terminal_chat_task
    _terminal_chat_task = None


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json(
        {"type": "status", "message": "Connected to Gumbo backend."}
    )
    await websocket.send_json(
        {"type": "assistant_message", "text": _read_boot_prompt_for_greeting()}
    )

    try:
        while True:
            raw = await websocket.receive_json()
            msg = UserMessage.model_validate(raw)
            await run_agent_turn(msg.text, websocket)
    except WebSocketDisconnect:
        return
    except Exception as exc:  # noqa: BLE001
        await websocket.send_json(
            {"type": "alert", "level": "error", "message": f"Server error: {exc}"}
        )
