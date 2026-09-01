"""
connections/manager.py — Session lifecycle manager for ShellMate.

SessionManager is the single source of truth for all active terminal
sessions.  It maintains a dictionary keyed by UUID session_id, creates
new sessions (SSH or serial), and tears them down cleanly.

Every other part of the backend (WebSocket handlers, AI router, REST
endpoints) goes through SessionManager — they never touch SSHHandler or
SessionBuffer directly.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.config import DEFAULT_BAUD_RATE, DEFAULT_SERIAL_PORT
from backend.connections.serial_handler import SerialHandler
from backend.connections.ssh_handler import SSHHandler
from backend.session.buffer import SessionBuffer
from backend.settings_store import get_settings

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
        serial_port: str = "",
        baud_rate: int = 0,
    ) -> dict[str, Any]:
        """
        Create a new session, connect to the device, and store it.

        Args:
            hostname:        Target device hostname or IP (ssh only).
            port:            TCP port, e.g. 22 (ssh only).
            username:        Login username (ssh only).
            password:        Login password, never stored in the returned
                              dict (ssh only).
            connection_type: "ssh" or "serial".
            display_label:   Human-readable tab label; defaults to hostname
                              (ssh) or the serial port (serial).
            serial_port:     Serial device, e.g. "COM3" or "/dev/ttyUSB0"
                              (serial only). Falls back to
                              config.DEFAULT_SERIAL_PORT when blank.
            baud_rate:       Serial baud rate (serial only). Falls back to
                              config.DEFAULT_BAUD_RATE when 0/unset.

        Returns:
            Session metadata dict (no password field).

        Raises:
            backend.connections.host_keys.UnknownHostKeyError: Host key not
                recognised (only when the ssh_auto_add_host_keys lab setting
                is off, which is the default) — the REST layer should turn
                this into a trust-on-first-use prompt rather than a bare error.
            backend.connections.host_keys.HostKeyChangedError: A previously
                trusted host presented a different key — possible MITM.
            Exception: Propagates any other connection error from the
                       underlying handler so the caller (REST endpoint) can
                       return a useful error.
        """
        session_id = str(uuid.uuid4())

        if connection_type == "ssh":
            # Default-off lab escape hatch (issue #13): only when a user has
            # explicitly enabled it does SSH fall back to trusting any host
            # key without verification. Off by default everywhere else.
            auto_add_host_keys = bool(
                get_settings().get("security", {}).get("ssh_auto_add_host_keys", False)
            )
            handler = SSHHandler(hostname, port, username, password)
            channel = handler.connect(auto_add_host_keys=auto_add_host_keys)  # Raises on failure
        elif connection_type == "serial":
            resolved_port = (serial_port or "").strip() or DEFAULT_SERIAL_PORT
            resolved_baud = baud_rate or DEFAULT_BAUD_RATE
            handler = SerialHandler(resolved_port, resolved_baud)
            channel = handler.connect()  # Raises on failure
            # Serial sessions have no SSH-style hostname/username — reuse
            # those fields so the tab bar, session list, and AI context
            # (which reads connection_type/hostname) still render sensibly.
            hostname = resolved_port
            port = resolved_baud
            username = ""
        else:
            raise NotImplementedError(f"Connection type '{connection_type}' not yet supported")

        label = display_label.strip() or hostname
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
