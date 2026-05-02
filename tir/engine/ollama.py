"""
Tír Ollama Client

Thin wrapper around Ollama's HTTP API. Handles the chat completion call
and response parsing. Nothing else.
"""

import json
import requests
from tir.config import OLLAMA_HOST, CHAT_MODEL


def chat_completion_stream_with_tools(
    system_prompt: str,
    messages: list[dict],
    tools: list[dict] | None = None,
    model: str = CHAT_MODEL,
    ollama_host: str = OLLAMA_HOST,
):
    """
    Stream chat completion with tool support. Yields raw parsed chunks.

    Each chunk is a dict from Ollama's streaming response. Key fields:
        chunk["message"]["content"]    — text token (empty during tool calls)
        chunk["message"]["tool_calls"] — list of tool calls (when model calls a tool)
        chunk["done"]                  — True on the final chunk

    Unlike chat_completion_stream (which yields content strings), this
    yields the full parsed chunk so callers can detect tool_calls.

    CRITICAL: think: false is mandatory. Without it, 800+ reasoning tokens
    and 40s+ response times.

    Yields:
        dict: Individual parsed chunks from Ollama's streaming response.

    Raises:
        requests.RequestException on network/server errors.
    """
    api_messages = [{"role": "system", "content": system_prompt}]
    api_messages.extend(messages)

    payload = {
        "model": model,
        "messages": api_messages,
        "stream": True,
        "think": False,
    }

    if tools:
        payload["tools"] = tools

    resp = requests.post(
        f"{ollama_host}/api/chat",
        json=payload,
        stream=True,
        timeout=300,
    )
    resp.raise_for_status()

    for line in resp.iter_lines():
        if line:
            chunk = json.loads(line)
            yield chunk
