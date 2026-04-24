from __future__ import annotations

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .config import settings
from .graph import run_agent_turn
from .memory import ensure_memory_dirs
from .schemas import UserMessage

app = FastAPI(title=settings.app_name)


@app.on_event("startup")
async def startup_event() -> None:
    ensure_memory_dirs()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json({"type": "status", "message": "Connected to Gumbo backend."})

    try:
        while True:
            raw = await websocket.receive_json()
            msg = UserMessage.model_validate(raw)
            await run_agent_turn(msg.text, websocket)
    except WebSocketDisconnect:
        return
    except Exception as exc:  # noqa: BLE001
        await websocket.send_json({"type": "alert", "level": "error", "message": f"Server error: {exc}"})
