"""
Tír Ollama Client

Thin wrapper around Ollama's HTTP API. Handles the chat completion call
and response parsing. Nothing else.
"""

import json
import requests
from tir.config import OLLAMA_HOST, CHAT_MODEL


def chat_completion(
    system_prompt: str,
    messages: list[dict],
    model: str = CHAT_MODEL,
    tools: list[dict] | None = None,
    ollama_host: str = OLLAMA_HOST,
) -> dict:
    """
    Call Ollama's /api/chat endpoint.

    Args:
        system_prompt: The system message content.
        messages: Conversation history as [{role, content}, ...].
        model: Model name.
        tools: Tool definitions in Ollama format (Phase 3).
        ollama_host: Ollama server URL.

    Returns:
        The full response dict from Ollama.

    Raises:
        requests.RequestException on network/server errors.
        ValueError if the response is malformed.
    """
    # Build the messages array with system prompt first
    api_messages = [{"role": "system", "content": system_prompt}]
    api_messages.extend(messages)

    payload = {
        "model": model,
        "messages": api_messages,
        "stream": False,
        "think": False,  # Critical: without this, 800+ reasoning tokens and 40s+ response times
    }

    if tools:
        payload["tools"] = tools

    resp = requests.post(
        f"{ollama_host}/api/chat",
        json=payload,
        timeout=120,  # Long timeout for complex responses
    )
    resp.raise_for_status()

    data = resp.json()

    if "message" not in data:
        raise ValueError(f"Malformed Ollama response: missing 'message' key. Got: {list(data.keys())}")

    return data


def chat_completion_stream(
    system_prompt: str,
    messages: list[dict],
    model: str = CHAT_MODEL,
    ollama_host: str = OLLAMA_HOST,
):
    """
    Stream chat completion from Ollama, yielding content strings.

    Same parameters as chat_completion, but yields individual tokens
    as they arrive instead of returning the full response.

    Yields:
        str: Individual content tokens from the model.

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

    resp = requests.post(
        f"{ollama_host}/api/chat",
        json=payload,
        stream=True,
        timeout=300,
    )
    resp.raise_for_status()

    for line in resp.iter_lines():
        if line:
            data = json.loads(line)
            content = data.get("message", {}).get("content", "")
            if content:
                yield content
            if data.get("done", False):
                return


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
