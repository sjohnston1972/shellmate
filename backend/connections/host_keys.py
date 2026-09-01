"""
connections/host_keys.py — Managed known_hosts store and host-key
verification policy for ShellMate SSH connections.

ShellMate never reads or writes the user's system ``~/.ssh/known_hosts``.
It keeps its own store at ``profiles/known_hosts`` and verifies every SSH
connection against it. This module provides:

  - the on-disk path plus load/save helpers for that store
  - RejectUnknownHostKeyPolicy — the default `missing_host_key` policy,
    which refuses any host key not already recorded and raises
    UnknownHostKeyError with enough detail (fingerprint, key type, raw key)
    for a caller to drive a trust-on-first-use approval flow (issue #12)
  - approve_host_key() — persists a key the user has explicitly approved

Host keys that ARE recorded but no longer match what the server presents
are rejected by paramiko itself (`BadHostKeyException`, raised straight out
of `SSHClient.connect()`) before any policy is consulted — that "changed
key" path cannot be bypassed by anything in this module.
"""

import base64
import hashlib
import logging
from pathlib import Path

import paramiko

logger = logging.getLogger(__name__)

# ShellMate-managed known_hosts store — never the user's system file.
KNOWN_HOSTS_FILE = Path(__file__).resolve().parent.parent.parent / "profiles" / "known_hosts"


class UnknownHostKeyError(paramiko.SSHException):
    """
    Raised by RejectUnknownHostKeyPolicy when a server's host key is not in
    the managed known_hosts store.

    Carries the offered key's fingerprint, type, and base64 blob so a
    caller can surface a trust-on-first-use prompt to the UI without
    needing a second, potentially-tampered connection attempt to re-fetch
    the key.
    """

    def __init__(self, hostname: str, key: "paramiko.PKey") -> None:
        self.hostname = hostname
        self.key_type = key.get_name()
        self.fingerprint = key_fingerprint(key)
        self.key_base64 = key.get_base64()
        super().__init__(
            f"Host key for '{hostname}' is not recognised "
            f"({self.key_type} {self.fingerprint}). Refusing to connect "
            f"until the key is approved."
        )


class HostKeyChangedError(paramiko.SSHException):
    """
    Raised (wrapping paramiko's BadHostKeyException) when a host already
    present in the managed known_hosts store presents a DIFFERENT key than
    what's on record — a classic machine-in-the-middle signature. This is
    always fatal: only a genuinely *unknown* host is eligible for
    auto-add/TOFU approval, never a host whose recorded key no longer
    matches.
    """

    def __init__(self, hostname: str, got_key: "paramiko.PKey", expected_key: "paramiko.PKey") -> None:
        self.hostname = hostname
        self.got_fingerprint = key_fingerprint(got_key)
        self.expected_fingerprint = key_fingerprint(expected_key)
        super().__init__(
            f"SSH host key for '{hostname}' has CHANGED since it was last "
            f"recorded — this may indicate a machine-in-the-middle attack. "
            f"Expected {self.expected_fingerprint}, got {self.got_fingerprint}. "
            f"Refusing to connect. If you expect this (e.g. the device was "
            f"reimaged), remove its entry from the ShellMate known_hosts "
            f"file before reconnecting."
        )


class RejectUnknownHostKeyPolicy(paramiko.MissingHostKeyPolicy):
    """
    Default missing-host-key policy: refuse to proceed for any host key
    that isn't already recorded in the managed known_hosts file.

    paramiko only calls this for a host it has genuinely never seen before.
    A previously-seen host whose key has changed is rejected earlier, by
    paramiko itself, with BadHostKeyException — see module docstring.
    """

    def missing_host_key(self, client, hostname, key):
        fp = key_fingerprint(key)
        logger.warning(
            "Rejecting unknown SSH host key for %s (%s %s) — not in managed known_hosts",
            hostname, key.get_name(), fp,
        )
        raise UnknownHostKeyError(hostname, key)


def key_fingerprint(key: "paramiko.PKey") -> str:
    """Return the SHA256 fingerprint in the 'SHA256:<base64>' form OpenSSH uses."""
    digest = hashlib.sha256(key.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


def ensure_known_hosts_file() -> Path:
    """Create the managed known_hosts file (and its parent dir) if missing."""
    KNOWN_HOSTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not KNOWN_HOSTS_FILE.exists():
        KNOWN_HOSTS_FILE.touch()
    return KNOWN_HOSTS_FILE


def load_into(client: "paramiko.SSHClient") -> None:
    """Load the managed known_hosts store into a freshly-created SSHClient."""
    path = ensure_known_hosts_file()
    client.load_host_keys(str(path))


def approve_host_key(hostname: str, key_type: str, key_base64: str) -> str:
    """
    Persist a host key the user has explicitly approved (TOFU accept flow,
    issue #12) into the managed known_hosts store.

    Args:
        hostname:  The paramiko-formatted lookup name — plain hostname for
                   port 22, "[hostname]:port" otherwise. This must be
                   exactly the value returned in the fingerprint prompt
                   (UnknownHostKeyError.hostname) so the entry lines up with
                   what SSHClient.connect() will look up next time.
        key_type:  e.g. "ssh-ed25519", "ssh-rsa", "ecdsa-sha2-nistp256".
        key_base64: The key's base64 blob, as returned by PKey.get_base64().

    Returns:
        The fingerprint of the key that was stored, for logging/confirmation.

    Raises:
        ValueError: If key_type/key_base64 don't decode to a valid key.
    """
    path = ensure_known_hosts_file()
    host_keys = paramiko.HostKeys()
    try:
        host_keys.load(str(path))
    except IOError:
        pass

    try:
        key_bytes = base64.b64decode(key_base64, validate=True)
        key = paramiko.PKey.from_type_string(key_type, key_bytes)
    except Exception as exc:
        raise ValueError(f"Invalid host key data: {exc}") from exc

    host_keys.add(hostname, key_type, key)
    host_keys.save(str(path))

    fp = key_fingerprint(key)
    logger.info("Host key approved and stored for %s (%s %s)", hostname, key_type, fp)
    return fp
