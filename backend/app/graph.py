from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal, TypedDict

from fastapi import WebSocket
from langgraph.graph import END, StateGraph
from langsmith import traceable

from .config import settings
from .memory import load_recent_turns, make_turn_id, save_turn_record
from .ollama_client import OllamaUnavailableError, stream_chat
from .schemas import Classification, ContextSnapshot, EventLogEntry, TurnRecord


class AgentState(TypedDict, total=False):
    user_text: str
    assistant_text: str
    event_log: list[dict[str, Any]]
    classification: dict[str, Any]
    error: str | None
    websocket: WebSocket | None
    context_snapshot: dict[str, Any]
    saved_path: Path | None
    boot_mode: bool


def _append_event(
    state: AgentState, event: str, detail: str = ""
) -> list[dict[str, Any]]:
    events = list(state.get("event_log", []))
    events.append(EventLogEntry(event=event, detail=detail).model_dump())
    return events


@traceable(name="Hydrate AgentState", run_type="chain")
def hydrate_agent_state(state: AgentState) -> dict[str, Any]:
    boot_prompt = settings.boot_prompt_path.read_text(encoding="utf-8")
    recent_turns = load_recent_turns(limit=5)
    events = _append_event(state, "hydrated_state")
    return {
        "event_log": events,
        "context_snapshot": ContextSnapshot(
            boot_prompt=boot_prompt,
            recent_turns_loaded=len(recent_turns),
        ).model_dump(),
    }


@traceable(name="Orchestration Supervisor", run_type="chain")
def orchestration_supervisor(state: AgentState) -> dict[str, Any]:
    events = _append_event(state, "orchestration_supervisor")
    return {"event_log": events}


@traceable(name="Input Classifier", run_type="chain")
def input_classifier(state: AgentState) -> dict[str, Any]:
    user_text = (state.get("user_text") or "").strip()
    needs_clarification = (not user_text) or user_text.lower() in {"help", "?", "hmm"}

    classification = Classification(
        needs_clarification=needs_clarification,
        can_respond_direct=not needs_clarification,
        intent="chat",
    ).model_dump()

    events = _append_event(
        state,
        "classified_input",
        f"needs_clarification={classification['needs_clarification']}",
    )
    return {"classification": classification, "event_log": events}


@traceable(name="User Intent Classifier", run_type="chain")
def user_intent_classifier(state: AgentState) -> dict[str, Any]:
    classification = dict(state.get("classification") or {})
    classification["intent"] = "chat"
    events = _append_event(state, "classified_intent", "intent=chat")
    return {"classification": classification, "event_log": events}


@traceable(name="Need Clarification?", run_type="chain")
def check_need_clarification(state: AgentState) -> dict[str, Any]:
    events = _append_event(state, "checked_need_clarification")
    return {"event_log": events}


@traceable(name="Draft Clarifying Question", run_type="chain")
def draft_clarifying_question(state: AgentState) -> dict[str, Any]:
    reply = "Could you share a bit more detail so I can help?"
    events = _append_event(state, "drafted_clarifying_question")
    return {"assistant_text": reply, "event_log": events}


@traceable(name="Can Respond Direct?", run_type="chain")
def check_can_respond_direct(state: AgentState) -> dict[str, Any]:
    events = _append_event(state, "checked_can_respond_direct")
    return {"event_log": events}


@traceable(name="Draft Direct Response", run_type="chain")
async def draft_direct_response(state: AgentState) -> dict[str, Any]:
    messages = [{"role": "user", "content": state.get("user_text", "")}]
    websocket = state.get("websocket")
    chunks: list[str] = []

    try:
        async for token in stream_chat(messages):
            chunks.append(token)
            if websocket is not None:
                await websocket.send_json({"type": "token", "text": token})
    except OllamaUnavailableError as exc:
        error_message = f"Ollama unavailable: {exc}"
        events = _append_event(state, "ollama_unavailable", str(exc))
        return {"assistant_text": "", "error": error_message, "event_log": events}

    assistant_text = "".join(chunks).strip()
    events = _append_event(state, "drafted_direct_response")
    return {"assistant_text": assistant_text, "event_log": events}


@traceable(name="Deliver to User", run_type="chain")
async def deliver_to_user(state: AgentState) -> dict[str, Any]:
    websocket = state.get("websocket")
    if websocket is not None:
        await websocket.send_json(
            {"type": "assistant_message", "text": state.get("assistant_text", "")}
        )

    events = _append_event(state, "delivered_to_user")
    return {"event_log": events}


@traceable(name="Save Turn", run_type="chain")
def save_turn(state: AgentState) -> dict[str, Any]:
    turn_record = TurnRecord(
        turn_id=make_turn_id(),
        created_at=datetime.utcnow().isoformat(timespec="milliseconds"),
        user_input=state.get("user_text", ""),
        assistant_response=state.get("assistant_text", ""),
        classification=Classification.model_validate(state.get("classification", {})),
        event_log=[
            EventLogEntry.model_validate(item) for item in state.get("event_log", [])
        ],
        context_snapshot=ContextSnapshot.model_validate(
            state.get("context_snapshot", {})
        ),
        error=state.get("error"),
    )
    saved_path = save_turn_record(turn_record)

    events = _append_event(state, "saved_turn", str(saved_path))
    return {"saved_path": saved_path, "event_log": events}


builder = StateGraph(AgentState)

builder.add_node("hydrate_agent_state", hydrate_agent_state)
builder.add_node("orchestration_supervisor", orchestration_supervisor)
builder.add_node("input_classifier", input_classifier)
builder.add_node("user_intent_classifier", user_intent_classifier)
builder.add_node("check_need_clarification", check_need_clarification)
builder.add_node("draft_clarifying_question", draft_clarifying_question)
builder.add_node("check_can_respond_direct", check_can_respond_direct)
builder.add_node("draft_direct_response", draft_direct_response)
builder.add_node("deliver_to_user", deliver_to_user)
builder.add_node("save_turn", save_turn)

builder.set_entry_point("hydrate_agent_state")
builder.add_edge("hydrate_agent_state", "orchestration_supervisor")
builder.add_edge("orchestration_supervisor", "input_classifier")
builder.add_edge("input_classifier", "user_intent_classifier")
builder.add_edge("user_intent_classifier", "check_need_clarification")


def route_need_clarification(
    state: AgentState,
) -> Literal["draft_clarifying_question", "check_can_respond_direct"]:
    classification = state.get("classification") or {}
    if classification.get("needs_clarification"):
        return "draft_clarifying_question"
    return "check_can_respond_direct"


builder.add_conditional_edges("check_need_clarification", route_need_clarification)
builder.add_edge("draft_clarifying_question", "deliver_to_user")
builder.add_edge("check_can_respond_direct", "draft_direct_response")
builder.add_edge("draft_direct_response", "deliver_to_user")
builder.add_edge("deliver_to_user", "save_turn")
builder.add_edge("save_turn", END)

APP_GRAPH = builder.compile()


async def boot_agent() -> None:
    """Run exactly one graph cycle at backend startup for LangSmith visibility."""
    initial_state: AgentState = {
        "user_text": "",
        "assistant_text": "",
        "event_log": [
            EventLogEntry(
                event="boot_cycle_started",
                detail="startup one-cycle health check",
            ).model_dump()
        ],
        "classification": Classification(
            needs_clarification=False,
            can_respond_direct=True,
            intent="chat",
        ).model_dump(),
        "error": None,
        "websocket": None,
        "boot_mode": True,
    }
    await APP_GRAPH.ainvoke(initial_state)


async def run_agent_turn(user_text: str, websocket: WebSocket) -> dict[str, Any]:
    initial_state: AgentState = {
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
        "boot_mode": False,
    }
    final_state = await APP_GRAPH.ainvoke(initial_state)
    return {
        "assistant_response": final_state.get("assistant_text", ""),
        "saved_path": str(final_state.get("saved_path", Path(""))),
        "classification": final_state.get("classification", {}),
        "error": final_state.get("error"),
    }
