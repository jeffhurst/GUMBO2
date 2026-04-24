from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .config import settings
from .schemas import TurnRecord


def ensure_memory_dirs() -> None:
    settings.memory_turns_dir.mkdir(parents=True, exist_ok=True)


def make_turn_id() -> str:
    now = datetime.utcnow()
    return now.strftime("%Y%m%d_%H%M%S_%f")[:-3]


def list_recent_turns(limit: int = 5) -> list[Path]:
    ensure_memory_dirs()
    files = sorted(settings.memory_turns_dir.glob("*.json"), reverse=True)
    return files[:limit]


def load_recent_turns(limit: int = 5) -> list[dict]:
    turns: list[dict] = []
    for file_path in reversed(list_recent_turns(limit)):
        with file_path.open("r", encoding="utf-8") as handle:
            turns.append(json.load(handle))
    return turns


def save_turn_record(record: TurnRecord) -> Path:
    ensure_memory_dirs()
    file_path = settings.memory_turns_dir / f"{record.turn_id}.json"
    with file_path.open("w", encoding="utf-8") as handle:
        json.dump(record.model_dump(), handle, indent=2)
    return file_path
