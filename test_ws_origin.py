"""
test_ws_origin.py — Regression tests for WebSocket Origin validation.

Covers /ws/terminal/{session_id} and /ws/chat: proves a disallowed or
missing Origin is rejected (closed, code 4403) before any session/AI work
happens, and that an allowed Origin proceeds exactly as before.

Run with:  python -m pytest test_ws_origin.py -v
"""
import json

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.app import app

ALLOWED_ORIGIN = "http://127.0.0.1:8765"
DISALLOWED_ORIGIN = "http://evil.example"


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# /ws/terminal/{session_id}
# ---------------------------------------------------------------------------

def test_terminal_ws_rejects_disallowed_origin(client):
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            "/ws/terminal/nonexistent-session",
            headers={"origin": DISALLOWED_ORIGIN},
        ):
            pass
    assert exc_info.value.code == 4403


def test_terminal_ws_rejects_missing_origin(client):
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/terminal/nonexistent-session"):
            pass
    assert exc_info.value.code == 4403


def test_terminal_ws_accepts_allowed_origin(client):
    # A non-existent session id still gets past the Origin gate and then
    # receives the "session not found" message — proving Origin passed.
    with client.websocket_connect(
        "/ws/terminal/nonexistent-session",
        headers={"origin": ALLOWED_ORIGIN},
    ) as ws:
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "output"
        assert "session not found" in msg["data"].lower()


# ---------------------------------------------------------------------------
# /ws/chat
# ---------------------------------------------------------------------------

def test_chat_ws_rejects_disallowed_origin(client):
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            "/ws/chat",
            headers={"origin": DISALLOWED_ORIGIN},
        ):
            pass
    assert exc_info.value.code == 4403


def test_chat_ws_rejects_missing_origin(client):
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/chat"):
            pass
    assert exc_info.value.code == 4403


def test_chat_ws_accepts_allowed_origin(client):
    # The handshake should succeed (no immediate close) with an allowed
    # Origin. We don't send a message — proving the Origin gate passed is
    # enough; exercising stream_chat() is out of scope here.
    with client.websocket_connect(
        "/ws/chat",
        headers={"origin": ALLOWED_ORIGIN},
    ) as ws:
        assert ws is not None
