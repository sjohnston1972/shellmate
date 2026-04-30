"""
deepseek_client.py — Streaming DeepSeek client for ShellMate.
DeepSeek exposes an OpenAI-compatible API at api.deepseek.com.
"""
import json
import logging
from collections.abc import AsyncIterator

import httpx

from backend.config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL
from backend.ai.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


async def stream_response(
    user_message: str,
    context_block: str,
    model: str | None = None,
) -> AsyncIterator[str]:
    """
    Stream a DeepSeek response token by token.
    Yields text chunks as they arrive.
    """
    if not DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY is not set. Add it to your .env file.")

    full_user_message = (
        f"{context_block}\n\n=== ENGINEER'S QUESTION ===\n{user_message}"
    )

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type":  "application/json",
    }

    payload = {
        "model":      model or DEEPSEEK_MODEL,
        "stream":     True,
        "max_tokens": 2048,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": full_user_message},
        ],
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST", DEEPSEEK_API_URL, headers=headers, json=payload
        ) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                raise ValueError(
                    f"DeepSeek API error {resp.status_code}: {body.decode()[:400]}"
                )

            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                    chunk = (
                        event.get("choices", [{}])[0]
                        .get("delta", {})
                        .get("content", "")
                    )
                    if chunk:
                        yield chunk
                except json.JSONDecodeError:
                    continue
