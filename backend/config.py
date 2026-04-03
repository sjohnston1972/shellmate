"""
config.py — Configuration loader for MATE.

Reads settings from the .env file (via python-dotenv) and exposes them
as module-level constants used throughout the backend.  Defaults are
applied when a variable is absent or empty.
"""

import os

# Server binding
HOST: str = os.getenv("MATE_HOST", "127.0.0.1")
PORT: int = int(os.getenv("MATE_PORT", "8765"))

# Claude API
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

# Ollama
OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")

# Default AI backend ("claude" or "ollama")
DEFAULT_AI_BACKEND: str = os.getenv("DEFAULT_AI_BACKEND", "ollama")

# Serial / console defaults (Windows COM port)
DEFAULT_SERIAL_PORT: str = os.getenv("DEFAULT_SERIAL_PORT", "COM3")
DEFAULT_BAUD_RATE: int = int(os.getenv("DEFAULT_BAUD_RATE", "9600"))
