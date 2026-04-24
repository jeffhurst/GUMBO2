from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class UserMessage(BaseModel):
    type: Literal["user_message"]
    text: str = ""


class Classification(BaseModel):
    needs_clarification: bool
    can_respond_direct: bool
    intent: str = "chat"


class EventLogEntry(BaseModel):
    time: str = Field(default_factory=lambda: datetime.utcnow().isoformat(timespec="milliseconds"))
    event: str
    detail: str = ""


class ContextSnapshot(BaseModel):
    boot_prompt: str
    recent_turns_loaded: int


class TurnRecord(BaseModel):
    turn_id: str
    created_at: str
    user_input: str
    assistant_response: str
    classification: Classification
    event_log: list[EventLogEntry]
    context_snapshot: ContextSnapshot
    error: str | None = None


class BackendEvent(BaseModel):
    type: str
    message: str | None = None
    text: str | None = None
    level: str | None = None
    path: str | None = None
