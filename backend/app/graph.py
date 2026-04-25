from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, List, Literal, TypedDict

from fastapi import WebSocket
from IPython.display import Image, display
from langgraph.graph import END, START, StateGraph
from langsmith import traceable

from .memory import load_recent_turns, make_turn_id, save_turn_record
from .ollama_client import OllamaUnavailableError, stream_chat
from .schemas import Classification, ContextSnapshot, EventLogEntry, TurnRecord


class AgentState(TypedDict):
    messages: List[Any]
    intent: str
    plan: List[str]
    memory_results: List[str]
    response: str
    pre_context: str


@traceable(name="Hydrate AgentState", run_type="chain")
def hydrate_agent_state(state: AgentState):
    # append event
    print("Hydrating...")


@traceable(name="Orchestration Supervisor", run_type="chain")
def orchestration_supervisor(state: AgentState):
    print("Orchestrating...")


@traceable(name="Input Classifier", run_type="chain")
def input_classifier(state: AgentState):
    print("Classifying input...")


@traceable(name="User Intent Classifier", run_type="chain")
def user_intent_classifier(state: AgentState):
    print("User Intent Classifier...")


@traceable(name="Need Clarification?", run_type="chain")
def check_need_clarification(state: AgentState):
    print("Need clarification?...")


@traceable(name="Draft Clarifying Question", run_type="chain")
def draft_clarifying_question(state: AgentState):
    print("Drafting clarifying question...")


@traceable(name="Can Respond Direct?", run_type="chain")
def check_can_respond_direct(state: AgentState):
    print("Can respond direct?...")


@traceable(name="Draft Direct Response", run_type="chain")
def draft_direct_response(state: AgentState):
    print("Drafting direct response...")


@traceable(name="Deliver to User", run_type="chain")
def deliver_to_user(state: AgentState):
    print("Delivering to user...")


@traceable(name="Save Turn", run_type="chain")
def save_turn(state: AgentState):
    print("Saving turn...")


builder = StateGraph(AgentState)

builder.add_node("hydrate_agent_state", hydrate_agent_state)
builder.add_node("orchestration_supervisor", orchestration_supervisor)
builder.add_node("input_classifier", input_classifier)
builder.add_node("user_intent_classifier", user_intent_classifier)
builder.add_node("check_need_clarification", need_clarification)
builder.add_node("draft_clarifying_question", draft_clarifying_question)
builder.add_node("check_can_respond_direct", check_can_respond_direct)
builder.add_node("draft_direct_response", draft_direct_response)
builder.add_node("deliver_to_user", deliver_to_user)
builder.add_node("save_turn", save_turn)

builder.set_entry_point("hydrate_agent_state")
builder.add_edge("hydrate_agent_state", "orchestration_supervisor")
builder.add_edge("orchestration_supervisor", "input_classifier")
builder.add_edge("orchestration_supervisor", "user_intent_classifier")
builder.add_edge("input_classifier", "check_need_clarification")
builder.add_edge("user_intent_classifier", "check_need_clarification")


def route_need_clarification(
    state: AgentState,
) -> Literal["draft_clarifying_question", "check_can_respond_direct"]:
    # Fill in arbitrary logic here that uses the state
    # to determine the next node
    return "draft_clarifying_question"


builder.add_conditional_edges("check_need_clarification", route_need_clarification)
builder.add_edge("draft_clarifying_question", "deliver_to_user")
builder.add_edge("check_can_respond_direct", "draft_direct_response")
builder.add_edge("draft_direct_response", "deliver_to_user")
builder.add_edge("deliver_to_user", "save_turn")
builder.add_edge("save_turn", END)


APP_GRAPH = builder.compile()

# View
display(Image(graph.get_graph(xray=1).draw_mermaid_png()))


async def boot_agent() -> None:
    print("Booting agent...")
    final_state = await APP_GRAPH.ainvoke(initial_state)
    print(final_state)


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
