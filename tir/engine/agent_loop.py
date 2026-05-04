"""
Tír Agent Loop

The iteration machinery for tool calling. Streams text responses
and dispatches tool calls through the skill registry.

The loop is a generator that yields events:
    {"type": "token",       "content": "..."}           — streaming text token
    {"type": "tool_call",   "name": "...", "arguments": {...}}  — tool being called
    {"type": "tool_result", "name": "...", "ok": bool, "result": "..."}  — tool returned
    {"type": "done",        "result": LoopResult}       — loop complete

Callers iterate over events and handle them appropriately.
The web streaming handler translates them to NDJSON.
Any future caller (CLI, autonomous engine) can use the same interface.

Content is empty during tool calls (verified by smoke test with gemma4:26b).
This means text tokens stream safely — if a tool call appears, no content
tokens were yielded for that iteration.
"""

import logging
from dataclasses import dataclass, field

from tir.config import CHAT_MODEL
from tir.engine.ollama import chat_completion_stream_with_tools
from tir.tools.rendering import render_tool_result

logger = logging.getLogger(__name__)


@dataclass
class LoopResult:
    """What the agent loop returns when it's done."""
    final_content: str | None       # The text response, or None if iteration limit
    tool_trace: list[dict]          # Record of all tool calls and results
    terminated_reason: str          # "complete" | "iteration_limit" | "error"
    iterations: int                 # How many iterations ran
    error: str | None = None        # Error message if terminated_reason == "error"


def run_agent_loop(
    system_prompt: str,
    messages: list[dict],
    registry,
    iteration_limit: int,
    ollama_host: str,
    model: str | None = None,
):
    """
    Run the agent loop. Generator that yields events.

    Calls Ollama with tool definitions from the registry. If the model
    responds with tool calls, dispatches them and loops. If the model
    responds with text, streams it and terminates.

    Args:
        system_prompt: The full system prompt (soul + tools + memories + situation).
        messages: Conversation history as [{"role": ..., "content": ...}, ...].
            This list is mutated — tool call/result messages are appended
            during the loop so the model sees them on the next iteration.
        registry: SkillRegistry instance. Can be None (no tools available).
        iteration_limit: Max iterations before forced termination.
        ollama_host: Ollama server URL.
        model: Model name override. Defaults to config CHAT_MODEL.

    Yields:
        dict: Event dicts. See module docstring for event types.
    """
    if model is None:
        model = CHAT_MODEL

    tools = registry.list_tools() if registry and registry.has_tools() else None
    tool_trace = []

    for iteration in range(iteration_limit):
        # --- Stream from Ollama ---
        accumulated_content = []
        accumulated_tool_calls = []

        try:
            for chunk in chat_completion_stream_with_tools(
                system_prompt=system_prompt,
                messages=messages,
                tools=tools,
                model=model,
                ollama_host=ollama_host,
            ):
                msg = chunk.get("message", {})
                content = msg.get("content", "")
                chunk_tool_calls = msg.get("tool_calls")

                # Stream text tokens as they arrive
                if content:
                    accumulated_content.append(content)
                    yield {"type": "token", "content": content}

                # Accumulate tool calls (appear in their own chunk)
                if chunk_tool_calls:
                    accumulated_tool_calls.extend(chunk_tool_calls)

                if chunk.get("done", False):
                    break

        except Exception as e:
            logger.error(f"Ollama call failed on iteration {iteration}: {e}")
            result = LoopResult(
                final_content=None,
                tool_trace=tool_trace,
                terminated_reason="error",
                iterations=iteration + 1,
                error=str(e),
            )
            yield {"type": "done", "result": result}
            return

        full_content = "".join(accumulated_content)

        # --- Tool-calling iteration ---
        if accumulated_tool_calls:
            # Add assistant message (with tool_calls) to conversation
            messages.append({
                "role": "assistant",
                "content": full_content,
                "tool_calls": accumulated_tool_calls,
            })

            trace_record = {
                "iteration": iteration,
                "tool_calls": [],
                "tool_results": [],
            }

            for tc in accumulated_tool_calls:
                func = tc.get("function", {})
                tool_name = func.get("name", "unknown")
                arguments = func.get("arguments", {})

                yield {
                    "type": "tool_call",
                    "name": tool_name,
                    "arguments": arguments,
                }

                # Dispatch through registry
                envelope = registry.dispatch(tool_name, arguments)
                trace_arguments = (
                    envelope.get("normalized_args", arguments)
                    if envelope["ok"]
                    else arguments
                )

                if envelope["ok"]:
                    rendered = render_tool_result(envelope["value"])
                else:
                    rendered = f"Error: {envelope['error']}"

                yield {
                    "type": "tool_result",
                    "name": tool_name,
                    "ok": envelope["ok"],
                    "result": rendered,
                }

                # Feed result back into conversation for next iteration
                messages.append({
                    "role": "tool",
                    "tool_name": tool_name,
                    "content": rendered,
                })

                trace_record["tool_calls"].append({
                    "name": tool_name,
                    "arguments": trace_arguments,
                })
                trace_record["tool_results"].append({
                    "tool_name": tool_name,
                    "ok": envelope["ok"],
                    "rendered": rendered[:500],
                })

            tool_trace.append(trace_record)
            continue

        # --- Terminal iteration (text response, already streamed) ---
        result = LoopResult(
            final_content=full_content,
            tool_trace=tool_trace,
            terminated_reason="complete",
            iterations=iteration + 1,
        )
        yield {"type": "done", "result": result}
        return

    # --- Exhausted iteration limit ---
    result = LoopResult(
        final_content=None,
        tool_trace=tool_trace,
        terminated_reason="iteration_limit",
        iterations=iteration_limit,
    )
    yield {"type": "done", "result": result}
