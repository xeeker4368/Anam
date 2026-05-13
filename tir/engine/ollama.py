"""
Tír Ollama Client

Thin wrapper around Ollama's HTTP API. Handles the chat completion call
and response parsing. Nothing else.
"""

import json
import requests
from tir.config import (
    CHAT_MODEL,
    OLLAMA_HOST,
    get_model_options,
    get_model_timeout,
)


def _apply_model_options(payload: dict, role: str, model_options: dict | None = None) -> None:
    options = dict(get_model_options(role))
    if model_options:
        options.update(model_options)

    if "think" in options:
        payload["think"] = bool(options.pop("think"))
    options.pop("timeout_seconds", None)
    if options:
        payload["options"] = options


def chat_completion_stream_with_tools(
    system_prompt: str,
    messages: list[dict],
    tools: list[dict] | None = None,
    model: str = CHAT_MODEL,
    ollama_host: str = OLLAMA_HOST,
    role: str = "chat",
    model_options: dict | None = None,
    timeout: int | None = None,
):
    """
    Stream chat completion with tool support. Yields raw parsed chunks.

    Each chunk is a dict from Ollama's streaming response. Key fields:
        chunk["message"]["content"]    — text token (empty during tool calls)
        chunk["message"]["tool_calls"] — list of tool calls (when model calls a tool)
        chunk["done"]                  — True on the final chunk

    Unlike chat_completion_stream (which yields content strings), this
    yields the full parsed chunk so callers can detect tool_calls.

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
    }
    _apply_model_options(payload, role, model_options)

    if tools:
        payload["tools"] = tools

    resp = requests.post(
        f"{ollama_host}/api/chat",
        json=payload,
        stream=True,
        timeout=timeout or get_model_timeout(role),
    )
    resp.raise_for_status()

    for line in resp.iter_lines():
        if line:
            chunk = json.loads(line)
            yield chunk


def chat_completion_json(
    messages: list[dict],
    model: str = CHAT_MODEL,
    ollama_host: str = OLLAMA_HOST,
    role: str = "default",
    model_options: dict | None = None,
    timeout: int | None = None,
) -> str:
    """
    Run a non-streaming JSON-oriented chat completion.

    This is for bounded offline/admin tasks that need one structured response
    and no tools. It returns the assistant message content as a string; callers
    remain responsible for JSON parsing and validation.
    """
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": "json",
    }
    _apply_model_options(payload, role, model_options)

    resp = requests.post(
        f"{ollama_host}/api/chat",
        json=payload,
        timeout=timeout or get_model_timeout(role),
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("message", {}).get("content", "")


def chat_completion_text(
    messages: list[dict],
    model: str = CHAT_MODEL,
    ollama_host: str = OLLAMA_HOST,
    role: str = "default",
    model_options: dict | None = None,
    timeout: int | None = None,
) -> str:
    """
    Run a non-streaming text chat completion.

    This is for bounded offline/admin tasks that need one Markdown/plain-text
    response and no tools. It returns the assistant message content as a string.
    """
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    _apply_model_options(payload, role, model_options)

    resp = requests.post(
        f"{ollama_host}/api/chat",
        json=payload,
        timeout=timeout or get_model_timeout(role),
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("message", {}).get("content", "")
