"""
connections/serial_handler.py — Serial/console connection handler for
ShellMate.

Wraps pyserial to provide a channel-like object with the same surface the
terminal WebSocket loop (backend/app.py) already drives for SSH sessions:
`send(bytes)`, `recv(n)` (raising `socket.timeout` when idle, returning
`b""` when the port is closed), and a `closed` property. This means the
WebSocket loop needs no changes to support serial sessions — SerialHandler
is a drop-in alongside SSHHandler.

Mirrors the public API of `ssh_handler.SSHHandler`: `connect() -> channel`,
`resize()`, `disconnect()`, and the `is_connected` property.
"""

import logging
import socket

import serial

logger = logging.getLogger(__name__)


class _SerialChannel:
    """
    Channel-like wrapper around a pyserial `Serial` (or `serial_for_url`)
    object.

    Implements just enough of paramiko.Channel's interface for the
    terminal WebSocket loop: `send()`, `recv()`, and `closed`.
    """

    def __init__(self, ser: "serial.SerialBase") -> None:
        self._serial = ser

    def send(self, data: bytes) -> int:
        """Write bytes to the serial port. Returns the number of bytes written."""
        return self._serial.write(data)

    def recv(self, nbytes: int = 4096) -> bytes:
        """
        Read up to `nbytes` from the serial port.

        The underlying `Serial` object is opened with a short read timeout
        (see `SerialHandler.connect`), so a call to `.read()` blocks for at
        most that long. If nothing arrived in that window we raise
        `socket.timeout` — exactly what the WebSocket loop expects from an
        idle-but-still-open SSH channel, so it just keeps looping instead
        of treating idle time as a closed connection.

        Returns `b""` only when the port itself is no longer open (device
        unplugged, or `disconnect()` was called), which the loop correctly
        treats as connection closure.
        """
        if not self._serial.is_open:
            return b""

        try:
            data = self._serial.read(nbytes)
        except (serial.SerialException, OSError):
            # A read error (e.g. the device was unplugged mid-session) is
            # treated the same as the port being closed.
            try:
                self._serial.close()
            except Exception:
                pass
            return b""

        if not data:
            raise socket.timeout()

        return data

    @property
    def closed(self) -> bool:
        return not self._serial.is_open


class SerialHandler:
    """Manages a single serial/console connection using pyserial."""

    def __init__(self, port: str, baudrate: int = 9600) -> None:
        """
        Args:
            port:     Serial device identifier, e.g. "COM3" (Windows) or
                      "/dev/ttyUSB0" (Linux). Also accepts pyserial URL
                      handlers such as "loop://" for a hardware-free
                      loopback used in tests.
            baudrate: Baud rate, e.g. 9600, 115200.
        """
        self.port: str = port
        self.baudrate: int = baudrate

        self._serial: "serial.SerialBase | None" = None
        self._channel: _SerialChannel | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def connect(self) -> _SerialChannel:
        """
        Open the serial port and return a channel-like wrapper around it.

        Uses `serial.serial_for_url` rather than `serial.Serial` directly
        so that, in addition to real device names, pyserial's virtual URL
        handlers work too (notably `loop://`, used for hardware-free
        testing).

        Returns:
            A `_SerialChannel` exposing send/recv/closed for the terminal
            WebSocket loop.

        Raises:
            serial.SerialException: Port doesn't exist, is already in use,
                                     or can't be configured.
            OSError: OS-level failure opening the device.
        """
        logger.info("Opening serial port %s @ %d baud", self.port, self.baudrate)

        # timeout=0.5 mirrors SSHHandler's channel.settimeout(0.5): reads
        # block briefly so the WebSocket loop stays responsive without
        # busy-looping.
        self._serial = serial.serial_for_url(
            self.port,
            baudrate=self.baudrate,
            timeout=0.5,
        )
        self._channel = _SerialChannel(self._serial)

        logger.info("Serial port open: %s @ %d baud", self.port, self.baudrate)
        return self._channel

    def resize(self, cols: int, rows: int) -> None:
        """
        No-op for serial: a physical or virtual console has no concept of
        a browser terminal window size. Kept as a method so the WebSocket
        loop's unconditional `handler.resize(cols, rows)` call is always
        safe to make, regardless of connection type.
        """

    def disconnect(self) -> None:
        """Close the serial port cleanly."""
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None

        self._channel = None
        logger.info("Disconnected from serial port %s", self.port)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        """True if the serial port is open."""
        return self._serial is not None and self._serial.is_open
