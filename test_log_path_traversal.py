"""
test_log_path_traversal.py — Regression tests for session-log filename
sanitisation (path traversal via a hostile hostname).

Proves that _build_log_path() (backend/app.py) always resolves inside the
configured logs directory, no matter what the user-supplied hostname
contains.

Run with:  python -m pytest test_log_path_traversal.py -v
"""
from pathlib import Path

import pytest

from backend.app import _build_log_path, _sanitize_log_component

SESSION_ID = "abcdef1234567890"


@pytest.fixture
def log_dir(tmp_path):
    d = tmp_path / "logs"
    d.mkdir()
    return d


@pytest.mark.parametrize("hostname", [
    "../../evil",
    "..\\..\\evil",
    "a/b/c",
    "....//....//etc/passwd",
    "/etc/passwd",
    "..",
    "...",
    "..hidden",
])
def test_hostile_hostname_stays_inside_log_dir(log_dir, hostname):
    path = _build_log_path(log_dir, SESSION_ID, hostname)
    resolved = path.resolve()
    # Must not escape log_dir, and must actually be a *file inside* it
    # (not log_dir itself).
    assert resolved.parent == log_dir.resolve()
    assert resolved.is_relative_to(log_dir.resolve())


def test_hostile_hostname_does_not_write_outside_log_dir(log_dir, tmp_path):
    # End-to-end: actually write through the resulting path and confirm
    # no file escaped the logs directory tree.
    outside_marker = tmp_path / "evil"
    for hostname in ["../../evil", "..\\..\\evil", "../outside"]:
        path = _build_log_path(log_dir, SESSION_ID, hostname)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write("pwned\n")
        assert not outside_marker.exists()
        # Everything written landed inside log_dir
        assert str(path.resolve()).startswith(str(log_dir.resolve()))


@pytest.mark.parametrize("hostname,expected", [
    ("switch01", "switch01"),
    ("router.example.com", "router.example.com"),
    ("ASA-FW", "ASA-FW"),
    ("10.0.0.1", "10.0.0.1"),
])
def test_normal_hostnames_stay_readable(log_dir, hostname, expected):
    path = _build_log_path(log_dir, SESSION_ID, hostname)
    assert path.name == f"{SESSION_ID[:8]}-{expected}.log"


def test_sanitize_component_strips_separators():
    # No path separators of any kind may survive — that's what actually
    # prevents traversal (a bare ".." or leading dots in a filename
    # component are harmless without a separator to walk with).
    assert "/" not in _sanitize_log_component("../../evil")
    assert "\\" not in _sanitize_log_component("..\\..\\evil")
    result = _sanitize_log_component("../../evil")
    assert result not in (".", "..")
    assert _sanitize_log_component("") == "session"
    assert _sanitize_log_component("...") == "session"
    assert _sanitize_log_component("..") == "session"
