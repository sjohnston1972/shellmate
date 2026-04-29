"""
run.py — Entry point for ShellMate.

Loads configuration from .env, starts the uvicorn server, then opens
the browser to http://localhost:<PORT> after a short delay so the server
has time to bind before the browser hits it.
"""

import threading
import time
import webbrowser

import uvicorn
from dotenv import load_dotenv

# Load .env before importing config so os.environ is populated
load_dotenv()

from backend.config import HOST, PORT  # noqa: E402 — must come after load_dotenv


def _open_browser() -> None:
    """Wait 1 second then open the default browser to the ShellMate UI."""
    time.sleep(1)
    webbrowser.open(f"http://localhost:{PORT}")


if __name__ == "__main__":
    # Open browser in a background thread so it doesn't block uvicorn
    threading.Thread(target=_open_browser, daemon=True).start()

    uvicorn.run(
        "backend.app:app",
        host=HOST,
        port=PORT,
        log_level="info",
        reload=False,
    )
