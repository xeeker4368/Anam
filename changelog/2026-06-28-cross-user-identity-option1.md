# 2026-06-28 — Cross-user identity fix, Option 1 (reposition + rephrase current-speaker block)

## Summary

The entity blurred the current speaker (Lyle) with people mentioned only in
retrieved memory (Jodie). Root cause (confirmed in
PLAN-2026-06-28-cross-user-identity.md): the current-speaker signal was (a)
**positioned after** the large, third-person-dense retrieved-memory block and
(b) **passively worded** (`Conversation with: <name>`), so the nearest/strongest
identity reference before generation was a third-person memory subject. Option 1
fixes both: move the current-speaker block to immediately **before** retrieved
memories, and rephrase it as an **active direct-address directive** that warns
retrieved memory may reference other people who are not the current speaker.

Separate commit from the queued artifact/`_event_text` work even though both live
in `context.py` — this touches only the current-situation block + assembly order.

## Finalized wording (revised 2026-06-28 — lighter assert-once version)

Revised to a lighter, assert-once phrasing with fewer negations, to avoid adding
to the prohibition-heavy tone the identity track is reducing. The rephrased
`[Current Situation]` block renders as (dynamic parts in braces):

```
[Current Situation]

You are speaking with {user_name}. Address {user_name} directly, in the second
person. The current time is {time}. Retrieved memory below may mention other
people (such as {other_user_names}); they are context, not the person you are
speaking with.
```

- If no other user names are available, the parenthetical drops and the sentence
  reads "…may mention other people; they are context, not the person you are
  speaking with." (fully generic).
- `{other_user_names}` is resolved **dynamically** from the users table at request
  time (other users, excluding the current speaker) — **no name is hardcoded** in
  the prompt string or the code. Verified by a test that fails if any literal
  person name appears in `context.py`.

(Prior approved-in-shape version used a heavier "...who are NOT {user_name}... Do
not treat anyone named only in retrieved memory as the current speaker, and do not
address them..." structure; replaced by the above. Reposition, dynamic name
resolution, generic fallback, and the no-hardcoded-name guard test are unchanged.)

## What changed

- `tir/engine/context.py`:
  - `_current_situation(user_name, other_user_names=None)` — rephrased to the
    direct-address directive above; added `_join_names()` helper for the
    "A and B" / "A, B, and C" rendering. (Old `Conversation with: …` removed.)
  - `build_system_prompt` / `build_system_prompt_with_debug` — new optional
    `other_user_names` param (backward-compatible default `None`); the
    **current-situation section is now appended before the retrieved-memories
    section** (Section 5 ↔ 6 swap). Module docstring order updated.
  - `_autonomous_situation()` unchanged (autonomous sessions have no human speaker).
- `tir/api/routes.py` — the live chat path resolves other user names best-effort
  (`get_all_users()` minus the current speaker) and passes them to the builder;
  on failure it logs and stays generic. (Already imported `get_all_users`.)
- `tests/test_context.py` — flipped the order assertion (now `[Current Situation]`
  before the retrieved block), updated the two `Conversation with: Lyle`
  assertions to the new wording, and added 3 tests (direct-address + generic
  warning; dynamic other-name injection incl. self-filtering; no-hardcoded-name
  source guard).
- `docs/PROMPT_INVENTORY.md` — regenerated (reflects the new wording; new "do not"
  risk flag is the inventory correctly surfacing the directive phrasing; no
  literal person name appears — dynamic parts show as `{...}`).

## Out of scope (NOT built — as directed)

- Per-chunk attribution of retrieved conversation chunks (`[Conversation with X —
  date]` / adding `user_name` to chunk metadata) — the queued stronger follow-up;
  `_format_retrieved_memories` / `context.py` retrieved-chunk rendering untouched.
- Per-turn author labels on live history (resolved low-value: history is the
  single-user current conversation).
- Any `soul.md` / persona / identity-framing change.
- The `_event_text` / artifact-injection path.

## Verification

### Static (done)
- `tests/test_context.py` order assertion flipped and passing; full suite **901
  passed**.
- `ANAM_DEBUG_PROMPT`-equivalent capture of the assembled prompt (the same string
  `debug_prompt.system_prompt` records) confirms the reposition landed —
  `[Current Situation]` precedes the retrieved block (idx 3969 < 4239), with the
  directive immediately before "Retrieved context follows.":
  ```
  [Current Situation]

  You are speaking with Lyle. Address Lyle directly, in the second person. The
  current time is Sunday, June 28, 2026 at 6:06 PM. Retrieved memory below may
  mention other people (such as Jodie); they are context, not the person you are
  speaking with.

  Retrieved context follows. Each item is labeled by source type.
  ```
  ("such as Jodie" came from the dynamic `other_user_names` argument, not a literal.)

### Behavioral procedure (for Lyle, on :8000 — run after deploy; NOT run here)
This bug is probabilistic; one turn proves nothing, and there is **no behavioral-
probe harness in code** — this is manual/scripted sampling. Capture a **before-fix
baseline on the same memory state** so the after is a real comparison:

1. **Freeze a Jodie-dense memory state.** Ensure retrievable memory contains
   several conversations/chunks that reference Jodie in the third person. Do not
   add/remove memory between the before and after runs (same state both times).
2. **Before (baseline):** run the server **without** this change (current
   `main`/pre-fix build). As Lyle, send N ≈ 15–20 messages whose topics are
   likely to retrieve the Jodie-dense chunks (shared activities, names, plans).
   For each reply, mark a **bleed incident** if the entity: addresses Lyle as
   Jodie, attributes Jodie's facts/relationships/preferences to Lyle, or otherwise
   treats a memory-only person as the current speaker. Record `bleed_before / N`.
3. **After (fix):** restart on the build with this change. Optionally set
   `ANAM_DEBUG_PROMPT=1` and confirm in `data/prod/chat_debug.jsonl` that
   `debug_prompt.system_prompt` shows `[Current Situation]` before "Retrieved
   context follows." (static confirmation the fix is live). Repeat step 2 with the
   **same memory state** and a comparable set of prompts. Record `bleed_after / N`.
4. **Compare** `bleed_before` vs `bleed_after`. Success = a clear drop in bleed
   incidents across the sample (not a single good turn). If bleed persists at a
   meaningful rate, that points to the deeper cause (unattributed retrieved chunks)
   → escalate the queued per-chunk-attribution follow-up.

## Project Anam alignment check

- Did not name the entity; no persona/identity-framing change; `soul.md` untouched.
- **Serves Invariant 4:** the entity distinguishes who it is *talking to* from who
  its memory merely *mentions* — without authoring the self.
- No hardcoded person name (dynamic resolution; guarded by test). No schema change,
  no migration. Backward-compatible signature (optional param).
- Scoped to placement + addressing; artifact/`_event_text` path and retrieved-chunk
  rendering left for their separate tasks.
