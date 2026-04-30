"""
ollama_client.py — Streaming Ollama API client for ShellMate.
Connects to a local Ollama instance and streams responses.
"""
import json
import logging
from collections.abc import AsyncIterator

import httpx

from backend.config import OLLAMA_HOST, OLLAMA_MODEL
from backend.ai.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


async def stream_response(
    user_message: str,
    context_block: str,
    model: str | None = None,
) -> AsyncIterator[str]:
    """
    Stream an Ollama response token by token.
    Yields text chunks as they arrive.
    Raises if Ollama is unreachable or returns an error.
    """
    full_user_message = (
        f"{context_block}\n\n=== ENGINEER'S QUESTION ===\n{user_message}"
    )

    url = f"{OLLAMA_HOST.rstrip('/')}/api/chat"
    payload = {
        "model": model or OLLAMA_MODEL,
        "stream": True,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": full_user_message},
        ],
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", url, json=payload) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                raise ValueError(
                    f"Ollama error {resp.status_code}: {body.decode()}"
                )

            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    chunk = event.get("message", {}).get("content", "")
                    if chunk:
                        yield chunk
                    if event.get("done"):
                        break
                except json.JSONDecodeError:
                    continue
