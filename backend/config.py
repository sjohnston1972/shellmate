"""
config.py — Configuration loader for ShellMate.

Reads settings from the .env file (via python-dotenv) and exposes them
as module-level constants used throughout the backend.  Defaults are
applied when a variable is absent or empty.
"""

import os

# Server binding
HOST: str = os.getenv("SHELLMATE_HOST", "127.0.0.1")
PORT: int = int(os.getenv("SHELLMATE_PORT", "8765"))

# Claude API — accept either ANTHROPIC_API_KEY or CLAUDE_API_KEY
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY", "")

# Ollama — Ollama itself exports OLLAMA_HOST as a bare address (e.g. "0.0.0.0")
# so we normalise it to a full URL here.
_ollama_host_raw: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
if _ollama_host_raw and not _ollama_host_raw.startswith(("http://", "https://")):
    _ollama_host_raw = f"http://{_ollama_host_raw}"
# A bare address like 0.0.0.0 means Ollama is listening on all interfaces;
# connect to localhost instead.
if _ollama_host_raw in ("http://0.0.0.0", "https://0.0.0.0"):
    _ollama_host_raw = "http://localhost:11434"
OLLAMA_HOST: str = _ollama_host_raw
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

# xAI (Grok) — OpenAI-compatible API
XAI_API_KEY: str  = os.getenv("XAI_API_KEY", "")
XAI_MODEL: str    = os.getenv("XAI_MODEL", "grok-2-latest")

# OpenAI
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str   = os.getenv("OPENAI_MODEL", "gpt-4o")

# DeepSeek
DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL: str   = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# Default AI backend ("claude", "ollama", or "xai")
DEFAULT_AI_BACKEND: str = os.getenv("DEFAULT_AI_BACKEND", "claude")

# Serial / console defaults (Windows COM port)
DEFAULT_SERIAL_PORT: str = os.getenv("DEFAULT_SERIAL_PORT", "COM3")
DEFAULT_BAUD_RATE: int = int(os.getenv("DEFAULT_BAUD_RATE", "9600"))

# Jira integration (optional)
JIRA_URL: str          = os.getenv("JIRA_URL", "")
JIRA_USER_EMAIL: str   = os.getenv("JIRA_USER_EMAIL", "")
JIRA_API_TOKEN: str    = os.getenv("JIRA_API_TOKEN", "")
JIRA_PROJECT_KEY: str  = os.getenv("JIRA_PROJECT_KEY", "")
