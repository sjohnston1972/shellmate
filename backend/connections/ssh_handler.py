"""
connections/ssh_handler.py — SSH connection handler for ShellMate.

Wraps paramiko to provide a simple interactive shell channel.  Each
SSHHandler manages exactly one SSH connection to one device.  The caller
receives a raw paramiko Channel which can be read/written like a socket,
giving true terminal interactivity (tab completion, paging, etc.).
"""

import logging

import paramiko

from backend.connections import host_keys

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

    def connect(self, auto_add_host_keys: bool = False) -> "paramiko.Channel":
        """
        Establish the SSH connection and open an interactive shell.

        By default, the server's host key is verified against ShellMate's
        managed known_hosts store (backend/connections/host_keys.py) and
        the connection is REFUSED if the key is unrecognised — the caller
        is expected to catch host_keys.UnknownHostKeyError and drive a
        trust-on-first-use approval flow (issue #12) rather than connect
        blind. A host whose recorded key has changed is always refused
        (host_keys.HostKeyChangedError), regardless of any setting — that
        is the classic machine-in-the-middle signature.

        Args:
            auto_add_host_keys: Legacy insecure behaviour — silently trust
                and store ANY unknown host key with no prompt. Defaults to
                False (secure). Should only ever be True when the caller has
                confirmed the user explicitly opted in via the default-off
                "ssh_auto_add_host_keys" lab setting (issue #13); doing so
                disables MITM protection for this connection.

        Returns:
            The paramiko Channel for the interactive shell session.

        Raises:
            host_keys.UnknownHostKeyError: Host key not recognised and
                auto_add_host_keys is False.
            host_keys.HostKeyChangedError: A previously-known host presented
                a DIFFERENT key than what's on record — possible MITM.
            paramiko.AuthenticationException: Bad credentials.
            paramiko.SSHException: Other SSH protocol error.
            OSError: Network-level failure (host unreachable, port closed).
        """
        self._client = paramiko.SSHClient()
        host_keys.load_into(self._client)

        if auto_add_host_keys:
            logger.warning(
                "SSH host-key verification is DISABLED for %s:%d — the "
                "'ssh_auto_add_host_keys' lab setting is ON. Any host key "
                "will be trusted and stored WITHOUT prompting. This "
                "disables protection against machine-in-the-middle attacks.",
                self.hostname, self.port,
            )
            self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        else:
            self._client.set_missing_host_key_policy(host_keys.RejectUnknownHostKeyPolicy())

        logger.info("Connecting to %s:%d as %s", self.hostname, self.port, self.username)

        try:
            self._client.connect(
                hostname=self.hostname,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=15,
                allow_agent=False,
                look_for_keys=False,
            )
        except paramiko.BadHostKeyException as exc:
            # Raised by paramiko itself, independent of the policy above,
            # whenever a host we already have on record presents a
            # different key. Re-raise as our own clearly-worded error so
            # this is never confused with a routine "unknown host".
            logger.error(
                "SSH host key for %s:%d has CHANGED since it was last "
                "recorded — possible machine-in-the-middle attack.",
                self.hostname, self.port,
            )
            raise host_keys.HostKeyChangedError(exc.hostname, exc.key, exc.expected_key) from exc

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
