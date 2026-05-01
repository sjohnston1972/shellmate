"""
connections/ssh_handler.py — SSH connection handler for ShellMate.

Wraps paramiko to provide a simple interactive shell channel.  Each
SSHHandler manages exactly one SSH connection to one device.  The caller
receives a raw paramiko Channel which can be read/written like a socket,
giving true terminal interactivity (tab completion, paging, etc.).
"""

import logging

import paramiko

logger = logging.getLogger(__name__)


class SSHHandler:
    """Manages a single SSH connection using paramiko's interactive shell."""

    def __init__(
        self,
        hostname: str,
        port: int,
        username: str,
        password: str,
    ) -> None:
        """
        Args:
            hostname: IP address or DNS name of the target device.
            port:     TCP port (usually 22).
            username: SSH login username.
            password: SSH login password.
        """
        self.hostname: str = hostname
        self.port: int = port
        self.username: str = username
        self.password: str = password

        self._client: paramiko.SSHClient | None = None
        self._channel: paramiko.Channel | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def connect(self) -> "paramiko.Channel":
        """
        Establish the SSH connection and open an interactive shell.

        Uses AutoAddPolicy so the user isn't blocked by host-key prompts —
        appropriate for a terminal tool where the user is making deliberate
        connection choices.

        Returns:
            The paramiko Channel for the interactive shell session.

        Raises:
            paramiko.AuthenticationException: Bad credentials.
            paramiko.SSHException: SSH protocol error.
            OSError: Network-level failure (host unreachable, port closed).
        """
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        logger.info("Connecting to %s:%d as %s", self.hostname, self.port, self.username)

        self._client.connect(
            hostname=self.hostname,
            port=self.port,
            username=self.username,
            password=self.password,
            timeout=15,
            allow_agent=False,
            look_for_keys=False,
        )

        # Authentication is complete — paramiko's Transport no longer needs
        # the password, so drop our copy. The session still works because
        # the open SSH channel is independent of the credentials.
        self.password = ""

        # Open an interactive PTY shell — this is what makes tab completion,
        # paging (--More--), and coloured output work correctly.
        self._channel = self._client.invoke_shell(
            term="xterm-256color",
            width=80,
            height=24,
        )
        # Use a timeout so recv() blocks briefly but doesn't hang forever.
        # This lets the read loop detect disconnection while still being
        # responsive. Do NOT use setblocking(False) — that causes recv() to
        # return b"" immediately when no data is available, which is
        # indistinguishable from a closed channel.
        self._channel.settimeout(0.5)

        logger.info("SSH channel open to %s:%d", self.hostname, self.port)
        return self._channel

    def resize(self, cols: int, rows: int) -> None:
        """
        Send a terminal window resize notification to the remote device.

        Called when the user resizes the browser window so that commands
        like 'terminal width' and pagers adapt to the new dimensions.

        Args:
            cols: New terminal width in columns.
            rows: New terminal height in rows.
        """
        if self._channel and not self._channel.closed:
            self._channel.resize_pty(width=cols, height=rows)

    def disconnect(self) -> None:
        """Close the channel and the underlying SSH transport cleanly."""
        if self._channel:
            try:
                self._channel.close()
            except Exception:
                pass
            self._channel = None

        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

        logger.info("Disconnected from %s:%d", self.hostname, self.port)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        """True if the channel exists and has not been closed."""
        return (
            self._channel is not None
            and not self._channel.closed
            and self._client is not None
            and self._client.get_transport() is not None
            and self._client.get_transport().is_active()
        )
