# Gumbo MVP

Gumbo is a local desktop AI assistant MVP for Windows. It combines a Python FastAPI + LangGraph backend with a C++ Raylib fullscreen frontend. The frontend launches the backend automatically, talks over WebSockets, and renders live streaming assistant responses.

## Architecture

- **Backend (`backend/`)**
  - FastAPI server with:
    - `GET /health`
    - `WebSocket /ws/chat`
  - Real LangGraph flow for orchestration/classification/response/save
  - Ollama streaming integration through `/api/chat`
  - Timestamped JSON memory files in `backend/memory/turns/`
- **Frontend (`frontend/`)**
  - Fullscreen Raylib UI with:
    - Conversation panel (left)
    - Input panel (bottom-left)
    - FDG placeholder panel + circle (upper-right)
    - Console/events panel (bottom-right)
  - Starts backend process, waits for health, then connects websocket
- **Scripts (`scripts/`)**
  - PowerShell scripts for setup/build/run/test

## Requirements

- Windows 10/11
- PowerShell
- Python 3.11+
- CMake 3.21+
- C++ compiler (MSVC or MinGW)
- Ollama installed

## Backend setup

```powershell
.\scripts\setup_backend.ps1
```

This creates `backend\.venv` (if missing) and installs dependencies from `backend\requirements.txt`.

## Configure environment

```powershell
copy backend\.env.example backend\.env
```

Default values:

```text
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma4:e4b
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
```

If your Ollama model name differs, edit `backend\.env`.

## Prepare Ollama

```powershell
ollama pull gemma4:e4b
ollama serve
```

If `gemma4:e4b` is unavailable, update `OLLAMA_MODEL` in `backend\.env`.

## Build frontend

```powershell
.\scripts\build_frontend.ps1
```

## Run Gumbo

```powershell
.\scripts\run_frontend.ps1
```

The frontend will:

1. Try to start the backend from `backend\.venv\Scripts\python.exe`
2. Fallback to `python` if needed
3. Poll `http://127.0.0.1:8000/health`
4. Connect to `ws://127.0.0.1:8000/ws/chat`

You can also run backend manually:

```powershell
.\scripts\run_backend.ps1
```

If a previous backend is already healthy on port `8000`, the script now reuses that process and exits cleanly.
To force a true restart on the same port, run:

```powershell
.\scripts\run_backend.ps1 -ForceRestart
```

Or build+run frontend in one command:

```powershell
.\scripts\run_all.ps1
```

## Run backend tests

```powershell
.\scripts\test_backend.ps1
```

Tests include:

- memory directory/turn save/load behavior
- graph routing behavior (clarification vs direct)
- event log + save behavior
- Ollama streaming parsing + connection error handling (mocked, no real Ollama required)

## Troubleshooting

### Frontend can't connect to backend

- Verify backend health:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health
```

- Run backend script directly to view errors:

```powershell
.\scripts\run_backend.ps1
```

### Ollama errors in console panel

- Make sure Ollama is running:

```powershell
ollama serve
```

- Ensure model exists:

```powershell
ollama list
```

- Update `backend\.env` with a model available locally.

### Build errors for frontend dependencies

- Ensure `git` is available (CMake FetchContent pulls dependencies).
- Ensure your compiler toolchain is configured in the active PowerShell session.

## Notes

- This MVP intentionally uses simple file-based memory (no DB/vector store).
- FDG visualization is currently a placeholder circle.
- If Ollama is offline, backend sends an `alert` event, returns a fallback message, and still saves the turn.
