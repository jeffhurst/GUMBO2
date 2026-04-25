from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"

load_dotenv(BACKEND_ROOT / ".env")


class Settings(BaseModel):
    app_name: str = "gumbo-backend"
    backend_host: str = Field(
        default_factory=lambda: os.getenv("BACKEND_HOST", "127.0.0.1")
    )
    backend_port: int = Field(
        default_factory=lambda: int(os.getenv("BACKEND_PORT", "8000"))
    )
    ollama_base_url: str = Field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    ollama_model: str = Field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL", "gemma4:e4b")
    )
    memory_turns_dir: Path = BACKEND_ROOT / "memory" / "turns"
    boot_prompt_path: Path = BACKEND_ROOT / "prompts" / "boot_prompt.md"
    persona_prompt_path: Path = BACKEND_ROOT / "prompts" / "persona.md"


settings = Settings()
