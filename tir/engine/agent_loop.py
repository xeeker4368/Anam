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
from tir.engine.tool_trace_context import selection_metadata_for_tool_result
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
    ollama_stats: dict | None = None # Final stream counters, if Ollama supplied them.


def _format_iteration_limit_response(
    tool_trace: list[dict],
    *,
    iteration_limit: int,
) -> str:
    """Build a bounded, user-visible response when the tool loop exhausts."""
    lines = [
        (
            f"I reached the tool iteration limit for this turn "
            f"({iteration_limit} iterations), so I am stopping cleanly."
        ),
        "",
        "Partial progress:",
    ]

    summaries = []
    for trace in tool_trace:
        iteration = trace.get("iteration")
        calls = trace.get("tool_calls") or []
        results = trace.get("tool_results") or []
        for index, call in enumerate(calls):
            tool_name = call.get("name", "unknown_tool")
            result = results[index] if index < len(results) else {}
            rendered = str(result.get("rendered") or "").strip()
            ok = result.get("ok")
            status = "succeeded" if ok else "failed" if ok is False else "finished"
            if rendered:
                rendered = rendered.replace("\n", " ")
                if len(rendered) > 220:
                    rendered = rendered[:217].rstrip() + "..."
                summaries.append(
                    f"- Iteration {iteration + 1 if isinstance(iteration, int) else '?'}: "
                    f"`{tool_name}` {status}; result preview: {rendered}"
                )
            else:
                summaries.append(
                    f"- Iteration {iteration + 1 if isinstance(iteration, int) else '?'}: "
                    f"`{tool_name}` {status}."
                )

    if summaries:
        lines.extend(summaries[:8])
        omitted = len(summaries) - 8
        if omitted > 0:
            lines.append(f"- {omitted} additional tool result(s) omitted from this summary.")
    else:
        lines.append("- No usable tool results were available before the limit.")

    lines.extend([
        "",
        "No further tool calls will be made in this turn.",
        (
            "A smaller bounded next step would be to pick one specific question, "
            "source, or tool action to run next."
        ),
    ])
    return "\n".join(lines)


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
    ollama_stats = None

    for iteration in range(iteration_limit):
        # --- Stream from Ollama ---
        accumulated_content = []
        accumulated_tool_calls = []
        iteration_stats = None

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

                # Buffer text until the iteration is known to be a normal
                # response. Some models can emit text before a tool call;
                # that text must not become user-visible or final content.
                if content:
                    accumulated_content.append(content)

                # Accumulate tool calls (appear in their own chunk)
                if chunk_tool_calls:
                    accumulated_tool_calls.extend(chunk_tool_calls)

                if chunk.get("done", False):
                    iteration_stats = {
                        key: chunk[key]
                        for key in (
                            "load_duration",
                            "prompt_eval_count",
                            "prompt_eval_duration",
                            "eval_count",
                            "eval_duration",
                        )
                        if key in chunk
                    }
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

        if iteration_stats:
            ollama_stats = iteration_stats

        full_content = "".join(accumulated_content)

        # --- Tool-calling iteration ---
        if accumulated_tool_calls:
            # Add assistant message (with tool_calls) to conversation
            messages.append({
                "role": "assistant",
                "content": "",
                "tool_calls": accumulated_tool_calls,
            })

            trace_record = {
                "iteration": iteration,
                "tool_calls": [],
                "tool_results": [],
            }
            if full_content:
                trace_record["suppressed_content_chars"] = len(full_content)
                trace_record["suppressed_content_preview"] = full_content[:200]

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
                    tool_value = envelope["value"]
                    rendered = render_tool_result(tool_value)
                    selection = selection_metadata_for_tool_result(
                        tool_name,
                        tool_value,
                    )
                else:
                    rendered = f"Error: {envelope['error']}"
                    selection = None

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
                tool_result_trace = {
                    "tool_name": tool_name,
                    "ok": envelope["ok"],
                    "rendered": rendered[:500],
                }
                if selection:
                    tool_result_trace["selection"] = selection
                trace_record["tool_results"].append(tool_result_trace)

            tool_trace.append(trace_record)
            continue

        # --- Terminal iteration (text response) ---
        for content in accumulated_content:
            yield {"type": "token", "content": content}

        result = LoopResult(
            final_content=full_content,
            tool_trace=tool_trace,
            terminated_reason="complete",
            iterations=iteration + 1,
            ollama_stats=ollama_stats,
        )
        yield {"type": "done", "result": result}
        return

    # --- Exhausted iteration limit ---
    result = LoopResult(
        final_content=_format_iteration_limit_response(
            tool_trace,
            iteration_limit=iteration_limit,
        ),
        tool_trace=tool_trace,
        terminated_reason="iteration_limit",
        iterations=iteration_limit,
        ollama_stats=ollama_stats,
    )
    yield {"type": "done", "result": result}
