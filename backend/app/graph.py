from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import WebSocket
from langgraph.graph import END, START, StateGraph

from .memory import load_recent_turns, make_turn_id, save_turn_record
from .ollama_client import OllamaUnavailableError, stream_chat
from .schemas import Classification, ContextSnapshot, EventLogEntry, TurnRecord

VAGUE_INPUTS = {"help", "what now", "do it", "?", ""}


class AgentState(dict):
    """Dict-backed state for LangGraph compatibility."""


def _append_event(state: dict[str, Any], event: str, detail: str = "") -> None:
    state.setdefault("event_log", []).append(
        EventLogEntry(event=event, detail=detail).model_dump()
    )


def _boot_prompt_text() -> str:
    from .config import settings

    return settings.boot_prompt_path.read_text(encoding="utf-8")


async def init_or_hydrate_agent_state(state: dict[str, Any]) -> dict[str, Any]:
    recent_turns = load_recent_turns(limit=5)
    state["recent_turns"] = recent_turns
    state["boot_prompt"] = _boot_prompt_text()
    _append_event(state, "init_or_hydrate_agent_state", f"loaded_turns={len(recent_turns)}")
    return state


async def orchestration_supervisor(state: dict[str, Any]) -> dict[str, Any]:
    _append_event(state, "orchestration_supervisor", "routing turn")
    return state


async def classify_and_update_event_log(state: dict[str, Any]) -> dict[str, Any]:
    text = state.get("user_text", "").strip().lower()
    needs_clarification = text in VAGUE_INPUTS
    can_respond_direct = not needs_clarification
    state["classification"] = Classification(
        needs_clarification=needs_clarification,
        can_respond_direct=can_respond_direct,
        intent="chat",
    ).model_dump()
    _append_event(state, "classify_and_update_event_log", f"needs_clarification={needs_clarification}")
    if ws := state.get("websocket"):
        await ws.send_json({"type": "status", "message": "Classifying user input..."})
    return state


def route_after_classification(state: dict[str, Any]) -> str:
    classification = state["classification"]
    if classification["needs_clarification"]:
        return "draft_clarification_question"
    if classification["can_respond_direct"]:
        return "draft_direct_response"
    return "draft_clarification_question"


async def draft_clarification_question(state: dict[str, Any]) -> dict[str, Any]:
    state["assistant_text"] = (
        "Could you share a bit more detail about what you want me to help with?"
    )
    _append_event(state, "draft_clarification_question", "generated deterministic clarification")
    return state


async def draft_direct_response(state: dict[str, Any]) -> dict[str, Any]:
    websocket: WebSocket = state["websocket"]
    _append_event(state, "draft_direct_response", "starting Ollama stream")

    context_lines: list[str] = []
    for turn in state.get("recent_turns", []):
        context_lines.append(f"User: {turn.get('user_input', '')}")
        context_lines.append(f"Assistant: {turn.get('assistant_response', '')}")

    messages = [
        {"role": "system", "content": state["boot_prompt"]},
        {
            "role": "system",
            "content": "Recent turns:\n" + "\n".join(context_lines[-10:]) if context_lines else "Recent turns: none",
        },
        {"role": "user", "content": state["user_text"]},
    ]

    tokens: list[str] = []
    try:
        await websocket.send_json({"type": "status", "message": "Generating response with Ollama..."})
        async for token in stream_chat(messages):
            tokens.append(token)
            await websocket.send_json({"type": "token", "text": token})
        state["assistant_text"] = "".join(tokens).strip() or "I wasn't able to produce a response."
    except OllamaUnavailableError as exc:
        state["assistant_text"] = (
            "I couldn't reach Ollama. Please check if ollama serve is running and try again."
        )
        state["error"] = f"Ollama unavailable: {exc}"
        await websocket.send_json(
            {
                "type": "alert",
                "level": "error",
                "message": "Ollama is not reachable.",
            }
        )
    return state


async def deliver_to_user(state: dict[str, Any]) -> dict[str, Any]:
    websocket: WebSocket = state["websocket"]
    await websocket.send_json({"type": "final", "text": state.get("assistant_text", "")})
    _append_event(state, "deliver_to_user", "final message sent")
    return state


async def save_turn(state: dict[str, Any]) -> dict[str, Any]:
    websocket: WebSocket = state["websocket"]
    turn_id = make_turn_id()
    record = TurnRecord(
        turn_id=turn_id,
        created_at=datetime.utcnow().isoformat(timespec="milliseconds"),
        user_input=state.get("user_text", ""),
        assistant_response=state.get("assistant_text", ""),
        classification=Classification(**state["classification"]),
        event_log=[EventLogEntry(**entry) for entry in state.get("event_log", [])],
        context_snapshot=ContextSnapshot(
            boot_prompt=state.get("boot_prompt", ""),
            recent_turns_loaded=len(state.get("recent_turns", [])),
        ),
        error=state.get("error"),
    )
    file_path = save_turn_record(record)
    _append_event(state, "save_turn", str(file_path))
    await websocket.send_json({"type": "turn_saved", "path": str(file_path).replace("\\", "/")})
    state["saved_path"] = file_path
    return state


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("init_or_hydrate_agent_state", init_or_hydrate_agent_state)
    graph.add_node("orchestration_supervisor", orchestration_supervisor)
    graph.add_node("classify_and_update_event_log", classify_and_update_event_log)
    graph.add_node("draft_clarification_question", draft_clarification_question)
    graph.add_node("draft_direct_response", draft_direct_response)
    graph.add_node("deliver_to_user", deliver_to_user)
    graph.add_node("save_turn", save_turn)

    graph.add_edge(START, "init_or_hydrate_agent_state")
    graph.add_edge("init_or_hydrate_agent_state", "orchestration_supervisor")
    graph.add_edge("orchestration_supervisor", "classify_and_update_event_log")
    graph.add_conditional_edges(
        "classify_and_update_event_log",
        route_after_classification,
        {
            "draft_clarification_question": "draft_clarification_question",
            "draft_direct_response": "draft_direct_response",
        },
    )
    graph.add_edge("draft_clarification_question", "deliver_to_user")
    graph.add_edge("draft_direct_response", "deliver_to_user")
    graph.add_edge("deliver_to_user", "save_turn")
    graph.add_edge("save_turn", END)

    return graph.compile()


APP_GRAPH = build_graph()


async def run_agent_turn(user_text: str, websocket: WebSocket) -> dict[str, Any]:
    initial_state: dict[str, Any] = {
        "user_text": user_text,
        "assistant_text": "",
        "event_log": [
            EventLogEntry(event="received_user_message", detail=user_text).model_dump()
        ],
        "classification": Classification(
            needs_clarification=False,
            can_respond_direct=False,
            intent="chat",
        ).model_dump(),
        "error": None,
        "websocket": websocket,
    }
    final_state = await APP_GRAPH.ainvoke(initial_state)
    return {
        "assistant_response": final_state.get("assistant_text", ""),
        "saved_path": str(final_state.get("saved_path", Path(""))),
        "classification": final_state.get("classification", {}),
        "error": final_state.get("error"),
    }
