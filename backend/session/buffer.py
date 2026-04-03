"""
session/buffer.py — Per-session terminal I/O buffer for MATE.

Each active session gets one SessionBuffer instance.  It keeps a rolling
window of terminal output lines (up to max_lines) using a deque, which
gives O(1) append and automatic eviction of old lines.  A separate raw
list stores the original byte strings for any future full-fidelity replay.
"""

from collections import deque
from typing import Deque


class SessionBuffer:
    """Stores all terminal output for a single session."""

    def __init__(self, session_id: str, max_lines: int = 5000) -> None:
        """
        Args:
            session_id: The UUID string that identifies the owning session.
            max_lines:  Maximum number of lines to keep in memory before
                        old lines are evicted from the front of the deque.
        """
        self.session_id: str = session_id
        self.max_lines: int = max_lines

        # Rolling line buffer — oldest lines fall off the left end
        self._lines: Deque[str] = deque(maxlen=max_lines)

        # Accumulates the current incomplete line until we see a newline
        self._pending: str = ""

        # Raw data appended in arrival order (not length-limited for now)
        self._raw: list[str] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write(self, data: str) -> None:
        """
        Append terminal output to the buffer.

        Splits on newline characters so that each logical line is stored
        as a separate entry in the deque.  The final fragment (no trailing
        newline) is held in _pending and prepended to the next write.

        Args:
            data: Raw string data received from the terminal channel.
        """
        if not data:
            return

        self._raw.append(data)

        # Combine any leftover partial line with the new data
        combined = self._pending + data

        # Split on newlines — the last element may be an incomplete line
        parts = combined.split("\n")

        # All parts except the last are complete lines
        for line in parts[:-1]:
            # Strip carriage returns that come from CR+LF sequences
            self._lines.append(line.rstrip("\r"))

        # The last part is either empty (data ended with \n) or an
        # incomplete line that we hold until the next write
        self._pending = parts[-1]

    def get_lines(self, n: int = 200) -> list[str]:
        """
        Return the last *n* lines stored in the buffer.

        Args:
            n: Number of lines to return.  Clamped to the number of lines
               actually available.

        Returns:
            List of strings, oldest first.
        """
        lines = list(self._lines)
        return lines[-n:] if n < len(lines) else lines

    def get_text(self, n: int = 200) -> str:
        """
        Return the last *n* lines as a single newline-joined string.

        Args:
            n: Number of lines to include.

        Returns:
            Multi-line string.
        """
        return "\n".join(self.get_lines(n))

    def clear(self) -> None:
        """Discard all stored data and reset the pending line fragment."""
        self._lines.clear()
        self._raw.clear()
        self._pending = ""

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def line_count(self) -> int:
        """Number of complete lines currently stored."""
        return len(self._lines)
