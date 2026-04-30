"""
openai_client.py — Streaming OpenAI client for ShellMate.
Uses the standard OpenAI chat/completions SSE format.
"""
import json
import logging
from collections.abc import AsyncIterator

import httpx

from backend.config import OPENAI_API_KEY, OPENAI_MODEL
from backend.ai.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"


async def stream_response(
    user_message: str,
    context_block: str,
) -> AsyncIterator[str]:
    """
    Stream an OpenAI response token by token.
    Yields text chunks as they arrive.
    """
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set. Add it to your .env file.")

    full_user_message = (
        f"{context_block}\n\n=== ENGINEER'S QUESTION ===\n{user_message}"
    )

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type":  "application/json",
    }

    payload = {
        "model":      OPENAI_MODEL,
        "stream":     True,
        "max_tokens": 2048,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": full_user_message},
        ],
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST", OPENAI_API_URL, headers=headers, json=payload
        ) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                raise ValueError(
                    f"OpenAI API error {resp.status_code}: {body.decode()[:400]}"
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
