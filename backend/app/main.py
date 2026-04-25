from __future__ import annotations

import re

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .config import settings
from .graph import boot_agent, run_agent_turn
from .memory import ensure_memory_dirs
from .schemas import UserMessage

app = FastAPI(title=settings.app_name)


def _read_boot_prompt_for_greeting() -> str:
    raw_prompt = settings.boot_prompt_path.read_text(encoding="utf-8").strip()
    # Keep markdown-heavy formatting out of the first assistant message.
    prompt_without_headers = re.sub(r"^#.*$", "", raw_prompt, flags=re.MULTILINE).strip()
    return prompt_without_headers or "Gumbo is ready for your input."


@app.on_event("startup")
async def startup_event() -> None:
    ensure_memory_dirs()
    await boot_agent()


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
