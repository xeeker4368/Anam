# Investigation — Failed `image_generate` reported to the entity as success

**Date:** 2026-06-24
**Mode:** REVIEW ONLY — no code was changed. This document is an investigation finding.
**Trigger:** A live `image_generate` call failed (`backend_unavailable`) and the entity narrated it as a success, inventing a plausible artifact block.
**Evidence (archive `tool_trace`):**
```json
"tool_results": [{
  "tool_name": "image_generate",
  "ok": true,
  "rendered": "{\"ok\": false, \"generation_error\": true, \"error_type\": \"backend_unavailable\", \"artifact_created\": false, ...}"
}]
```
Outer `ok: true`, inner `rendered.ok: false`. The failure data is present in the result; the entity acted as if it succeeded.

**Related prior note:** `CODE_REVIEW_2026-06-24.md` §3 flagged the smell `routes.py:142` vs `agent_loop.py:248` — "inner-envelope (`effective_ok`) handling disagrees… outer `ok` reported, inner `ok:false` ignored." This investigation confirms and details that smell as the mechanism.

---

## NORTH_STAR check

No conflict. This is an integrity defect: the entity narrated a fabricated success it did not experience, violating **Invariant 4** (it must be able to distinguish what it *experienced* / *created* from what it did not) and the **§2** stance "we are measuring, not performing." Diagnosing it serves the experiment rather than altering its nature.

---

## (a) Where the doubled envelope is created

Two layers. The conflation is deliberate at the lower one:

- **Inner `{"ok": false, ...}`** is the tool's own honest return value. Path:
  `image_generate` (`skills/active/media_artifacts/media_artifacts.py`) → `generate_image` → **`_failure_trace(...)`** (`tir/media/image_generation.py:39-62`). For `backend_unavailable`, `ComfyUIBackend.generate` raises `ImageGenerationBackendError(error_type="backend_unavailable")`, which `generate_image` catches and converts into the failure dict (`ok:false, generation_error:true, artifact_created:false`).

- **Outer `{"ok": true, "value": <inner>}`** is created by **`registry.dispatch`** at `tir/tools/registry.py:523`:
  ```python
  return {"ok": True, "value": result, "normalized_args": normalized_args}
  ```
  Its own docstring (`registry.py:489-490`) says this explicitly: *"{'ok': True...} on success (**including tool-returned errors**)."* The outer `ok` means **"the tool ran without raising,"** not "the operation succeeded." **This conflation is the root cause.**

- **The self-contradictory trace record** is then assembled in **`tir/engine/agent_loop.py:268-275`**:
  ```python
  tool_result_trace = {
      "tool_name": tool_name,
      "ok": envelope["ok"],     # True  (outer / "ran")
      "rendered": rendered[:500] # inner JSON, contains ok:false
  }
  ```
  This is exactly the `ok:true` / `rendered.ok:false` shape captured in the archive.

## (b) Which layer reads which `ok`

- **Agent loop reads the OUTER `ok` only.** `agent_loop.py:235, 239, 253, 270` all branch on `envelope["ok"]`. It **never unwraps `value.ok`**. An inner failure is therefore **invisible to the loop's control flow** — the loop treats the call as a normal success, feeds the result back into `messages`, and continues.
- **Prefetch path reads the INNER `ok`.** `routes.py:776` calls `_render_tool_envelope` (`routes.py:142-149`), which computes `effective_ok = not (isinstance(value, dict) and value.get("ok") is False)`.

## (c) What the entity actually saw — the key answer

**The entity's context contained the failure. It was shown the failure and missed it — NOT "never shown."**

In `agent_loop.py:241`, `rendered = render_tool_result(tool_value)` serializes the **inner** dict to JSON (`tir/tools/rendering.py:7-19`, a plain `json.dumps`). That string — literally
`{"ok": false, "generation_error": true, "error_type": "backend_unavailable", "artifact_created": false, ...}` —
becomes the tool message the model reads on the next turn (`agent_loop.py:258-262`):
```python
messages.append({"role": "tool", "tool_name": tool_name, "content": rendered})
```

So the model was handed the raw failure payload and narrated success anyway.

Critically, **the misleading outer `ok:true` is *not* in the model's text.** It appears only in:
- the streamed `tool_result` event (`agent_loop.py:250-255`), consumed by the UI/stream, and
- the trace record (`agent_loop.py:270`), persisted to the archive.

Neither is part of the model-visible context. The content the model read was honest JSON. What is missing is any **natural-language framing or instruction** telling the model "this failed; do not claim an artifact." It received a JSON blob and pattern-matched *tool returned → success*.

## (d) Was failure-detection intended?

**No detection exists on the agent path. This is an absence-of-handling finding, not a handler that failed to fire.**

The **only** inner-`ok`-aware logic in the codebase is `_render_tool_envelope` (`routes.py:142-149`), and:
1. It is wired **only into the prefetch / `web_fetch` path** (`routes.py:776`), never into `run_agent_loop`.
2. Even where it runs, it only flips the reported `ok` flag in the streamed event and trace record — it does **not** change the `rendered` content the model reads, and does **not** halt narration.

Nothing anywhere searches for `generation_error`, `artifact_created: false`, or inner `ok: false` to reframe the tool message, warn the model, or stop it narrating a result.

## (e) Prefetch vs agent-loop divergence (cross-check)

Confirmed — same dispatch envelope, two opposite readings:

| | model-visible tool content | reported `ok` (event + trace) | inner failure visible to control flow? |
|---|---|---|---|
| **Prefetch** (`routes.py:776-816`) | inner JSON | `effective_ok` (honest → `false`) | yes |
| **Agent loop** (`agent_loop.py:239-275`) | inner JSON | `envelope["ok"]` (outer → `true`) | **no** |

The prefetch path is the inner-aware ("correct") behavior **already present** in the repo — direct evidence that the intended semantics are inner-aware and that the agent loop is the surface that omitted it.

> Note: even the prefetch path only corrects the *reported `ok` flag*; both paths still feed the model the same raw JSON content with no failure framing. So the prefetch path is "more correct" for downstream/trace consumers but would not, on its own, have stopped the model from misreading the JSON.

## Secondary impact

The contradictory trace `ok` also corrupts the iteration-limit summarizer: `agent_loop.py:68-69` labels each tool `"succeeded" if ok else "failed"` using the **outer** `ok`, so a failed `image_generate` would be summarized back to the entity as "succeeded" there too.

---

## Bottom line

- **(a)** The doubled envelope is created at the dispatch boundary: `registry.dispatch` (`registry.py:523`) wraps the tool's own `ok:false` dict in an `ok:true` *execution* envelope (by design — outer `ok` = "ran without raising"). The contradictory trace is recorded in `agent_loop.py:268-275`.
- **(b)** The agent loop reads only the **outer** `ok`; the prefetch path reads the **inner** `ok`. The inner failure is invisible to the loop.
- **(c)** The entity's context **did contain the failure** (the tool message content was the full inner JSON, `ok:false`/`generation_error:true`/`artifact_created:false`). It was shown the failure and missed it; it was never given a non-JSON signal that the call failed.
- **(d)** No intended failure-handling exists on the agent path. The one inner-aware helper (`_render_tool_envelope`) is wired only to prefetch and only affects the reported flag, not the model-visible content.

*No files other than this document were created or modified.*
