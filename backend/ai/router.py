"""
router.py — Routes AI chat requests to the correct backend (Claude or Ollama).
Builds context from session buffers and streams the response.
"""
import logging
import re
from collections.abc import AsyncIterator

from backend.ai.prompts import build_context_prompt
from backend.connections.manager import SessionManager

logger = logging.getLogger(__name__)

# Regex to extract CLI commands from buffer (lines ending with a prompt + command)
_CMD_RE = re.compile(r"[A-Za-z0-9._\-]{1,64}(?:\([^)]*\))?[#>]\s*(.+)")


def _extract_commands(buffer_text: str) -> list[str]:
    """Pull command strings from terminal output by matching prompt lines."""
    commands = []
    for line in buffer_text.splitlines():
        m = _CMD_RE.match(line.strip())
        if m:
            cmd = m.group(1).strip()
            if cmd:
                commands.append(cmd)
    return commands


async def stream_chat(
    message: str,
    active_session_id: str | None,
    backend: str,
    context_mode: str,          # "active" | "all" | "1" | "2" etc
    session_manager: SessionManager,
) -> AsyncIterator[str]:
    """
    Build context from session buffers, then stream an AI response.
    Yields text chunks.
    """
    # Build sessions summary list
    all_sessions = session_manager.get_all_sessions()
    sessions_summary = [
        {
            "tab_num": i + 1,
            "label":   s.get("display_label") or s.get("hostname", "unknown"),
            "hostname": s.get("hostname", "?"),
            "connection_type": s.get("connection_type", "ssh"),
            "session_id": s.get("session_id"),
        }
        for i, s in enumerate(all_sessions)
    ]

    # Active session buffer
    active_label = "No active session"
    active_buffer = "(No terminal session is currently active.)"
    command_history: list[str] = []

    if active_session_id:
        session = session_manager.get_session(active_session_id)
        if session:
            active_label = (
                session.get("display_label") or
                session.get("hostname", active_session_id[:8])
            )
            buf = session.get("buffer")
            if buf:
                active_buffer = buf.get_text(200)
                command_history = _extract_commands(active_buffer)

    # Extra contexts (/context all or /context N)
    extra_contexts: list[dict] = []

    if context_mode == "all":
        for s in all_sessions:
            sid = s.get("session_id")
            if sid == active_session_id:
                continue
            sess = session_manager.get_session(sid)
            if sess and sess.get("buffer"):
                extra_contexts.append({
                    "label":  sess.get("display_label") or sess.get("hostname", sid[:8]),
                    "buffer": sess["buffer"].get_text(100),
                })
    elif context_mode.isdigit():
        tab_num = int(context_mode)
        if 1 <= tab_num <= len(all_sessions):
            target = all_sessions[tab_num - 1]
            sid = target.get("session_id")
            if sid and sid != active_session_id:
                sess = session_manager.get_session(sid)
                if sess and sess.get("buffer"):
                    extra_contexts.append({
                        "label":  (
                            target.get("display_label") or
                            target.get("hostname", "")
                        ),
                        "buffer": sess["buffer"].get_text(100),
                    })

    context_block = build_context_prompt(
        sessions_summary,
        active_buffer,
        active_label,
        command_history,
        extra_contexts or None,
    )

    # Route to the correct backend
    if backend == "claude":
        from backend.ai.claude_client import stream_response
    else:
        from backend.ai.ollama_client import stream_response

    async for chunk in stream_response(message, context_block):
        yield chunk
