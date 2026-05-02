"""
app.py — FastAPI application for ShellMate.

Defines all HTTP REST endpoints and WebSocket handlers.  A single global
SessionManager instance tracks every active terminal session.  The frontend
is served as static files from the frontend/ directory.

WebSocket /ws/terminal/{session_id}:
  - Receives JSON from the browser: {type:"input", data:"..."} or
    {type:"resize", cols:N, rows:N}
  - Sends JSON to the browser: {type:"output", data:"..."} or
    {type:"hostname_detected", hostname:"..."}

REST endpoints:
  POST   /api/sessions          — create session, return session_id
  GET    /api/sessions          — list all sessions
  DELETE /api/sessions/{id}     — tear down a session
"""

import asyncio
import json
import logging
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.connections.manager import SessionManager
from backend.profiles import get_profiles, save_profile, delete_profile
from backend.settings_store import get_settings, get_settings_for_ui, update_settings
from backend.ai.router import stream_chat
from backend.ai import chroma_client
from backend.config import DEFAULT_AI_BACKEND, JIRA_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application and globals
# ---------------------------------------------------------------------------

app = FastAPI(title="ShellMate", )

# Single global session manager — all state lives here
session_manager = SessionManager()

# Absolute path to the frontend directory
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# ---------------------------------------------------------------------------
# CORS — allow the browser to call the API from localhost origins
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8765",
        "http://127.0.0.1:8765",
        "http://localhost:*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Static file serving
# ---------------------------------------------------------------------------

# Serve everything under frontend/ at /static (css, js, etc.)
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
async def serve_index() -> FileResponse:
    """Serve the main frontend page."""
    return FileResponse(str(FRONTEND_DIR / "index.html"))


# ---------------------------------------------------------------------------
# REST — Session management
# ---------------------------------------------------------------------------


class CreateSessionRequest(BaseModel):
    """Body for POST /api/sessions."""

    hostname: str
    port: int = 22
    username: str
    password: str
    connection_type: str = "ssh"
    display_label: str = ""


class SaveProfileRequest(BaseModel):
    """Body for POST /api/profiles."""

    name: str = ""
    hostname: str
    port: int = 22
    username: str
    connection_type: str = "ssh"


class UpdateSettingsRequest(BaseModel):
    """Body for POST /api/settings."""

    settings: dict


@app.post("/api/sessions")
async def create_session(request: CreateSessionRequest) -> dict:
    """
    Create a new SSH session and return its metadata.

    The SSH connection is made synchronously here; if it fails the error
    is returned as a 400 so the frontend can show a useful message.
    """
    try:
        # Run the blocking paramiko connect in a thread so we don't stall
        # the event loop during the TCP + SSH handshake
        session = await asyncio.to_thread(
            session_manager.create_session,
            request.hostname,
            request.port,
            request.username,
            request.password,
            request.connection_type,
            request.display_label,
        )
        return session
    except Exception as exc:
        logger.error("Failed to create session: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/sessions")
async def list_sessions() -> list[dict]:
    """Return metadata for all active sessions."""
    return session_manager.get_all_sessions()


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str) -> dict:
    """Tear down a session — closes SSH, clears buffer, removes from manager."""
    session = session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    await asyncio.to_thread(session_manager.destroy_session, session_id)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# REST — Connection profiles
# ---------------------------------------------------------------------------

@app.get("/api/profiles")
async def list_profiles() -> list[dict]:
    """Return all saved connection profiles."""
    return get_profiles()


@app.post("/api/profiles")
async def create_profile(request: SaveProfileRequest) -> dict:
    """Save a connection profile (no password stored)."""
    return save_profile(
        request.name, request.hostname, request.port,
        request.username, request.connection_type,
    )


@app.delete("/api/profiles/{profile_id}")
async def remove_profile(profile_id: str) -> dict:
    """Delete a saved profile."""
    if not delete_profile(profile_id):
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# REST — Settings
# ---------------------------------------------------------------------------

@app.get("/api/settings")
async def get_app_settings() -> dict:
    """Return current application settings (secrets masked, env flags included)."""
    return get_settings_for_ui()


@app.post("/api/settings")
async def save_app_settings(request: UpdateSettingsRequest) -> dict:
    """Persist updated settings and return the merged result."""
    return update_settings(request.settings)


# ---------------------------------------------------------------------------
# REST — Chroma DB health check (used by the settings panel "Test" button)
# ---------------------------------------------------------------------------

@app.get("/api/chroma/health")
async def chroma_health() -> dict:
    """Return whether the configured Chroma DB is reachable."""
    return await chroma_client.health_check()


# ---------------------------------------------------------------------------
# REST — Jira integration
# ---------------------------------------------------------------------------

@app.get("/api/jira/config")
async def jira_config() -> dict:
    """Return whether Jira is configured and the project key."""
    configured = bool(JIRA_URL and JIRA_USER_EMAIL and JIRA_API_TOKEN and JIRA_PROJECT_KEY)
    return {"configured": configured, "project_key": JIRA_PROJECT_KEY, "jira_url": JIRA_URL}


@app.get("/api/jira/search")
async def jira_search(q: str = "") -> list[dict]:
    """Search Jira issues by text within the configured project."""
    if not all([JIRA_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY]):
        raise HTTPException(400, "Jira not configured")
    # Allow empty query — Jira picker returns recent issues
    from backend.jira_client import search_issues
    try:
        return await search_issues(JIRA_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY, q.strip())
    except Exception as e:
        raise HTTPException(502, f"Jira search error: {e}")


@app.get("/api/jira/issue-types")
async def jira_issue_types() -> list[str]:
    """Return available issue types for the configured project."""
    if not all([JIRA_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY]):
        raise HTTPException(400, "Jira not configured")
    from backend.jira_client import get_issue_types
    try:
        return await get_issue_types(JIRA_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY)
    except Exception as e:
        raise HTTPException(502, f"Jira error: {e}")


@app.post("/api/ai/session-summary")
async def ai_session_summary(request: Request) -> dict:
    """Return an AI-generated summary of the open terminal sessions and chat history."""
    body             = await request.json()
    open_session_ids = body.get("open_session_ids") or []
    chat_messages    = body.get("chat_messages") or []
    backend          = (body.get("backend") or DEFAULT_AI_BACKEND).strip()
    model            = body.get("model") or None

    from backend.ai.summarize import summarize_session
    try:
        summary = await summarize_session(
            open_session_ids=open_session_ids,
            chat_messages=chat_messages,
            backend=backend,
            session_manager=session_manager,
            model=model,
        )
    except Exception as e:
        logger.exception("session summary failed")
        raise HTTPException(502, f"Summary failed: {e}")
    return {"summary": summary}


@app.post("/api/jira/session")
async def post_session_to_jira(request: Request) -> dict:
    """Build a rich ADF document from session buffers + chat history and post to Jira."""
    if not all([JIRA_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY]):
        raise HTTPException(400, "Jira not configured — add JIRA_* vars to .env")

    body             = await request.json()
    summary          = body.get("summary", "ShellMate Session").strip() or "ShellMate Session"
    description      = body.get("description", "")
    issue_type       = body.get("issue_type", "Task")
    open_session_ids = body.get("open_session_ids") or []
    chat_messages    = body.get("chat_messages") or []
    existing_key     = (body.get("existing_issue_key") or "").strip().upper()

    # Collect terminal buffers from the session manager
    sessions = []
    for sid in open_session_ids:
        sess = session_manager.get_session(sid)
        if not sess:
            continue
        buf = sess.get("buffer")
        sessions.append({
            "label":           sess.get("display_label") or sess.get("hostname", sid[:8]),
            "hostname":        sess.get("hostname", ""),
            "connection_type": sess.get("connection_type", "ssh"),
            "buffer_text":     buf.get_text(500) if buf else "",
        })

    from backend.jira_client import build_adf, create_issue, add_comment
    adf = build_adf(description, sessions, chat_messages)

    try:
        if existing_key:
            # Add session as a comment on an existing issue
            await add_comment(JIRA_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN, existing_key, adf)
            return {
                "issue_key": existing_key,
                "url": f"{JIRA_URL.rstrip('/')}/browse/{existing_key}",
                "mode": "comment",
            }
        else:
            # Create a brand new issue
            result = await create_issue(
                JIRA_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN,
                JIRA_PROJECT_KEY, summary, adf, issue_type,
            )
            issue_key = result.get("key", "")
            return {
                "issue_key": issue_key,
                "url": f"{JIRA_URL.rstrip('/')}/browse/{issue_key}",
                "mode": "created",
            }
    except Exception as e:
        raise HTTPException(502, f"Jira API error: {e}")


# ---------------------------------------------------------------------------
# REST — Ollama model list
# ---------------------------------------------------------------------------

@app.get("/api/ollama/models")
async def ollama_models() -> list[dict]:
    """Return the list of models installed in the local Ollama instance."""
    from backend.config import OLLAMA_HOST
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{OLLAMA_HOST.rstrip('/')}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return [
                {
                    "name":   m["name"],
                    "size":   m.get("details", {}).get("parameter_size", ""),
                    "family": m.get("details", {}).get("family", ""),
                }
                for m in data.get("models", [])
            ]
    except Exception:
        return []


# REST — Session logs
# ---------------------------------------------------------------------------

@app.get("/api/logs")
async def list_logs() -> list[dict]:
    """Return a list of available session log files."""
    from datetime import datetime
    logs_dir = Path(__file__).parent.parent / "logs"
    if not logs_dir.exists():
        return []
    files = []
    for f in sorted(logs_dir.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True):
        stat = f.stat()
        files.append({
            "filename": f.name,
            "size_bytes": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })
    return files


@app.get("/api/logs/{filename}")
async def download_log(filename: str) -> FileResponse:
    """Download a specific log file."""
    # Sanitize filename — only allow safe characters to prevent path traversal
    if not re.match(r'^[\w\-\.]+\.log$', filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    log_path = Path(__file__).parent.parent / "logs" / filename
    if not log_path.exists():
        raise HTTPException(status_code=404, detail="Log file not found")
    return FileResponse(str(log_path), filename=filename)


# ---------------------------------------------------------------------------
# WebSocket — terminal I/O
# ---------------------------------------------------------------------------

# Regex patterns for Cisco CLI prompts (used for hostname detection)
# Matches lines like:  switch01#   or   Router>   or   ASA-FW(config)#
_PROMPT_PATTERN = re.compile(
    r"(?:^|\r?\n)"           # start of string or new line
    r"([A-Za-z0-9._\-]{1,64})"  # hostname — alphanumeric + common chars
    r"(?:\([^)]*\))?"        # optional mode suffix e.g. (config)
    r"[#>]\s*$"              # prompt character at end of line
)


@app.websocket("/ws/terminal/{session_id}")
async def terminal_websocket(websocket: WebSocket, session_id: str) -> None:
    """
    Bidirectional WebSocket bridge between the browser xterm.js and the
    remote device's paramiko channel.

    Each session_id gets its own WebSocket connection.  Multiple tabs in
    the browser each connect here with their own session_id — they are
    completely independent.
    """
    await websocket.accept()

    session = session_manager.get_session(session_id)
    if session is None:
        await websocket.send_text(
            json.dumps({"type": "output", "data": "\r\nError: session not found.\r\n"})
        )
        await websocket.close()
        return

    channel = session["channel"]
    handler = session["handler"]
    hostname_sent = False  # Only send hostname_detected once per session

    async def read_from_client() -> None:
        """Forward browser keystrokes / resize events to the SSH channel."""
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    # If someone sends plain text, treat it as input
                    msg = {"type": "input", "data": raw}

                msg_type = msg.get("type")

                if msg_type == "input":
                    data: str = msg.get("data", "")
                    if data and handler.is_connected:
                        await asyncio.to_thread(channel.send, data.encode("utf-8", errors="replace"))

                elif msg_type == "resize":
                    cols = int(msg.get("cols", 80))
                    rows = int(msg.get("rows", 24))
                    await asyncio.to_thread(handler.resize, cols, rows)

        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.warning("read_from_client error (session %s): %s", session_id, exc)

    async def read_from_channel() -> None:
        """Forward SSH channel output to the browser and session buffer."""
        import socket as _socket
        nonlocal hostname_sent
        try:
            while True:
                # channel.recv blocks up to the channel timeout (0.5 s).
                # A socket.timeout means no data arrived — just keep looping.
                # b"" means the channel was closed by the remote end.
                try:
                    data_bytes: bytes = await asyncio.to_thread(channel.recv, 4096)
                except _socket.timeout:
                    # No data in this window — check if still connected
                    if channel.closed:
                        data_bytes = b""
                    else:
                        continue
                except Exception:
                    data_bytes = b""

                if not data_bytes:
                    # Channel closed (device disconnected or session ended)
                    session["is_connected"] = False
                    await websocket.send_text(
                        json.dumps({
                            "type": "output",
                            "data": "\r\n\r\n[Connection closed]\r\n",
                        })
                    )
                    break

                text = data_bytes.decode("utf-8", errors="replace")

                # Write to session buffer
                session_manager.write_to_buffer(session_id, text)

                # File logging (if enabled in settings)
                _settings = get_settings()
                if _settings.get("logging", {}).get("enabled"):
                    _log_dir = Path(__file__).parent.parent / _settings["logging"].get("directory", "logs")
                    _log_dir.mkdir(parents=True, exist_ok=True)
                    _log_file = _log_dir / f"{session_id[:8]}-{session.get('hostname', 'session')}.log"
                    from datetime import datetime
                    with open(_log_file, "a", encoding="utf-8") as _lf:
                        _lf.write(f"[{datetime.now().isoformat()}] {text}")

                # Send output to browser
                await websocket.send_text(json.dumps({"type": "output", "data": text}))

                # Try to detect the device hostname from prompt patterns
                if not hostname_sent:
                    match = _PROMPT_PATTERN.search(text)
                    if match:
                        detected = match.group(1)
                        # Sanity check: must look like a real hostname
                        if len(detected) >= 2 and not detected.isdigit():
                            await websocket.send_text(
                                json.dumps({
                                    "type": "hostname_detected",
                                    "hostname": detected,
                                })
                            )
                            hostname_sent = True

        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.warning("read_from_channel error (session %s): %s", session_id, exc)
            session["is_connected"] = False

    # Run both directions concurrently; cancel the other when one finishes
    read_client_task = asyncio.create_task(read_from_client())
    read_channel_task = asyncio.create_task(read_from_channel())

    done, pending = await asyncio.wait(
        {read_client_task, read_channel_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    for task in pending:
        task.cancel()

    session["is_connected"] = False
    logger.info("WebSocket closed for session %s", session_id)


# ---------------------------------------------------------------------------
# WebSocket — AI chat
# ---------------------------------------------------------------------------

@app.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket) -> None:
    """
    Streaming AI chat WebSocket.

    Receives from browser:
      {"message": "...", "session_id": "...", "backend": "claude|ollama", "context_mode": "active|all|1|2..."}

    Streams to browser:
      {"type": "chunk",  "data": "..."}    — one per token
      {"type": "done"}                     — stream complete
      {"type": "error",  "message": "..."}  — on failure
    """
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps({"type": "error", "message": "Invalid JSON"})
                )
                continue

            user_message     = msg.get("message", "").strip()
            session_id       = msg.get("session_id")
            backend          = msg.get("backend", DEFAULT_AI_BACKEND)
            model            = msg.get("model") or None
            context_mode     = msg.get("context_mode", "active")
            open_session_ids = msg.get("open_session_ids") or None
            mode             = msg.get("mode") or None  # "learn" | "tshoot"

            if not user_message:
                continue

            try:
                async for chunk in stream_chat(
                    message=user_message,
                    active_session_id=session_id,
                    backend=backend,
                    context_mode=context_mode,
                    session_manager=session_manager,
                    open_session_ids=open_session_ids,
                    model=model,
                    mode=mode,
                ):
                    await websocket.send_text(
                        json.dumps({"type": "chunk", "data": chunk})
                    )

                await websocket.send_text(json.dumps({"type": "done"}))

            except Exception as exc:
                logger.error("AI chat error: %s", exc)
                await websocket.send_text(
                    json.dumps({"type": "error", "message": str(exc)})
                )

    except WebSocketDisconnect:
        pass
