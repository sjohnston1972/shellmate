"""
connections/manager.py — Session lifecycle manager for MATE.

SessionManager is the single source of truth for all active terminal
sessions.  It maintains a dictionary keyed by UUID session_id, creates
new sessions (SSH for now, serial in Phase 4), and tears them down cleanly.

Every other part of the backend (WebSocket handlers, AI router, REST
endpoints) goes through SessionManager — they never touch SSHHandler or
SessionBuffer directly.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.connections.ssh_handler import SSHHandler
from backend.session.buffer import SessionBuffer

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages the full lifecycle of all terminal sessions."""

    def __init__(self) -> None:
        # Primary store: session_id -> session dict
        self._sessions: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Session creation
    # ------------------------------------------------------------------

    def create_session(
        self,
        hostname: str,
        port: int,
        username: str,
        password: str,
        connection_type: str = "ssh",
        display_label: str = "",
    ) -> dict[str, Any]:
        """
        Create a new session, connect to the device, and store it.

        Args:
            hostname:        Target device hostname or IP.
            port:            TCP port (SSH: 22).
            username:        Login username.
            password:        Login password (never stored in the returned dict).
            connection_type: "ssh" (serial support coming in Phase 4).
            display_label:   Human-readable tab label; defaults to hostname.

        Returns:
            Session metadata dict (no password field).

        Raises:
            Exception: Propagates any connection error from SSHHandler so
                       the caller (REST endpoint) can return a useful error.
        """
        session_id = str(uuid.uuid4())
        label = display_label.strip() or hostname

        if connection_type == "ssh":
            handler = SSHHandler(hostname, port, username, password)
            channel = handler.connect()  # Raises on failure
        else:
            raise NotImplementedError(f"Connection type '{connection_type}' not yet supported")

        buffer = SessionBuffer(session_id)

        session: dict[str, Any] = {
            "session_id": session_id,
            "handler": handler,
            "channel": channel,
            "buffer": buffer,
            "hostname": hostname,
            "port": port,
            "username": username,
            "connection_type": connection_type,
            "display_label": label,
            "connected_at": datetime.now(timezone.utc).isoformat(),
            "is_connected": True,
        }

        self._sessions[session_id] = session
        logger.info("Session created: %s (%s@%s:%d)", session_id, username, hostname, port)

        # Return a copy without sensitive or non-serialisable fields
        return self._public_view(session)

    # ------------------------------------------------------------------
    # Session retrieval
    # ------------------------------------------------------------------

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """
        Return the full internal session dict (including handler/channel).

        Returns None if the session_id is not found.
        """
        return self._sessions.get(session_id)

    def get_all_sessions(self) -> list[dict[str, Any]]:
        """
        Return public metadata for all sessions (no sensitive data).

        Used by GET /api/sessions so the frontend can rebuild the tab bar
        after a page refresh.
        """
        return [self._public_view(s) for s in self._sessions.values()]

    # ------------------------------------------------------------------
    # Session destruction
    # ------------------------------------------------------------------

    def destroy_session(self, session_id: str) -> None:
        """
        Disconnect and remove a session entirely.

        Safe to call even if the session is already disconnected.
        """
        session = self._sessions.pop(session_id, None)
        if session is None:
            logger.warning("destroy_session called for unknown id: %s", session_id)
            return

        try:
            session["handler"].disconnect()
        except Exception as exc:
            logger.warning("Error disconnecting session %s: %s", session_id, exc)

        session["buffer"].clear()
        logger.info("Session destroyed: %s", session_id)

    # ------------------------------------------------------------------
    # Buffer helpers
    # ------------------------------------------------------------------

    def write_to_buffer(self, session_id: str, data: str) -> None:
        """
        Append terminal output to the session's buffer.

        Args:
            session_id: Target session.
            data:       Text received from the terminal channel.
        """
        session = self._sessions.get(session_id)
        if session:
            session["buffer"].write(data)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _public_view(session: dict[str, Any]) -> dict[str, Any]:
        """
        Return a serialisable subset of a session dict.

        Excludes the handler object, paramiko channel, SessionBuffer
        instance, and the password (which was never stored anyway).
        """
        return {
            "session_id": session["session_id"],
            "hostname": session["hostname"],
            "port": session["port"],
            "username": session["username"],
            "connection_type": session["connection_type"],
            "display_label": session["display_label"],
            "connected_at": session["connected_at"],
            "is_connected": session["is_connected"],
        }
