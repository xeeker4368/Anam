# PLAN — Cross-user identity bug (Lyle/Jodie bleed). READ + PLAN ONLY.

**Date:** 2026-06-28 · **Mode:** read + plan only. **No code changed, no commit.** Plan first; the fix is behavioral (prompt assembly) and easy to get subtly wrong.
**Approved direction:** Option 1 — (a) reposition the current-speaker block before retrieved memories, (b) rephrase it from passive description to an active direct-address directive.

## NORTH_STAR check
A placement + addressing correctness fix. Protects Invariant 4 (the entity must distinguish who it is actually talking to from who its memory merely *mentions*) without authoring the self/persona. Aligned. (Does not touch soul.md or identity framing, per constraint.)

---

## STEP 1 — Verbatim current wording & position (diagnosis confirmed)

**Current-speaker line** — `tir/engine/context.py:82-88`, `_current_situation()`:
```python
def _current_situation(user_name: str) -> str:
    """Build the current situation section."""
    tz = ZoneInfo(TIMEZONE)
    now = datetime.now(tz)
    formatted = now.strftime("%A, %B %d, %Y at %I:%M %p").replace(" 0", " ")

    return f"[Current Situation]\n\nConversation with: {user_name}\nTime: {formatted}"
```
So the literal text in the prompt is:
```
[Current Situation]

Conversation with: <user_name>
Time: <formatted>
```
This is **passive description** ("Conversation with: Lyle") — no instruction to address the speaker, no statement that retrieved memory may reference other people. **Confirms diagnosis (b: wording).**

**Position** — `build_system_prompt_with_debug()` appends sections in this order (`context.py:181-232`):
1. soul (`:182`)
2. operational guidance (`:187`)
3. behavioral guidance (dormant → normally absent, `:201`)
4. tool descriptions (`:205`)
5. **Retrieved memories** (`:221-224`)
6. **Current situation** (`:226-232`) ← **last, AFTER retrieved memories**

`prompt = "\n\n".join(sections)` (`:234`). The module docstring (`:6-12`) lists the same order. **Confirms diagnosis (a: position)** — the current-speaker signal sits after the large, Jodie-dense retrieved-memory block, so the nearest/strongest identity reference the model sees before generating is third-person Jodie, not the current speaker.

**Verdict:** the handoff diagnosis is correct on both counts. Position + wording is a real contributing cause. (See "Deeper cause surfaced" below — it is **not the only** cause, but the approved fix is valid and low-risk.)

---

## STEP 2 — Reposition plan

**Current order → proposed order:**

| # | Current | Proposed |
|---|---------|----------|
| 1 | soul | soul |
| 2 | operational guidance | operational guidance |
| 3 | behavioral guidance (dormant) | behavioral guidance (dormant) |
| 4 | tool descriptions | tool descriptions |
| 5 | **retrieved memories** | **current situation** ← moved up |
| 6 | **current situation** | **retrieved memories** ← now last |

Mechanism: move the "Section 6: Current situation" append (`context.py:226-232`) to immediately **before** the "Section 5: Retrieved memories" block (`:209-224`). Place it directly before retrieved memories (not earlier) so the current-speaker directive is the **nearest preceding** signal to the confusing memory block — it primes the model right where the bleed happens. The situation is always appended (it does not depend on whether retrieved_chunks exist), so behavior for the no-retrieval case is unchanged except ordering.

**Position dependencies (checked — do not move blind):**
- **`tests/test_context.py:61-67` (`test_operational_guidance_is_labeled_and_ordered`) asserts the current order and WILL break.** Specifically `:67`:
  `assert prompt.index("Retrieved context follows...") < prompt.index("[Current Situation]")`.
  After reposition this inverts. The plan's implementation must update this test to the new order: `... tools < [Current Situation] < Retrieved context follows ...`. (Flagged so the reposition isn't shipped with a stale/failing assertion.)
- **Module docstring** (`context.py:6-12`) lists the order → update to match (doc only).
- **No runtime consumer parses the prompt by section position** — `section_counts`/debug are char counts only (`:167-247`), and retrieved-context budgeting happens upstream in routes.py before `retrieved_chunks` is passed in. Reordering the `sections.append` calls is safe; nothing slices the prompt by offset.
- The journal/artifact/moltbook context blocks are inserted as **system messages in the messages array** in routes.py (`:633-660`), not in this system prompt — out of scope and unaffected.

---

## STEP 3 — Rephrase plan (wording for Lyle's approval — proposed, NOT finalized)

Requirements: (a) assert the current speaker, (b) instruct direct address, (c) state retrieved memory may reference other people (incl. Jodie) who are NOT the current speaker.

**Proposed wording A (generic — recommended):**
```
[Current Situation]

You are speaking directly with {user_name}. Address {user_name} in the second
person ("you"). The current time is {formatted}.

The retrieved context that follows is memory from other times and may mention
other people who are NOT the person you are talking to now. Do not treat anyone
named in that memory as the current speaker, and do not address them. The person
you are speaking with right now is {user_name}.
```

**Proposed wording B (names Jodie as an example — as the directive literally requested):** same as A, but the second paragraph reads "...may mention other people (for example, Jodie) who are NOT the person you are talking to now."

**Design flag for the Jodie naming (decide at approval):** hard-coding the literal string "Jodie" into the prompt builder is brittle and edges toward seeding content — it bakes one specific human into code, won't generalize to other users, and would need editing if the cast changes. Options, in order of preference:
1. **Wording A (no hard-coded name)** — robust, fully generic, still fixes the addressing.
2. **Dynamically inject other-known-user names** (e.g. names from the users table other than the current speaker) into the directive, rather than a literal — keeps it concrete without hard-coding.
3. **Wording B (literal "Jodie")** — matches the request verbatim but is the most fragile.

Recommend A (or 2 if a concrete example is wanted). This is a placement/addressing change only — it does not alter soul.md or persona framing.

---

## STEP 4 — Author-label question (resolved)

**What history messages currently carry:** `routes.py:578-579` builds
`model_messages = [{"role": m["role"], "content": m["content"]} for m in all_messages]`
from `get_conversation_messages(conversation_id)`. So each history message carries **only `role` (user/assistant) and `content` — no name / per-user identity.**

**Why a per-turn author label on history is LOW value for THIS bug:** `get_conversation_messages` returns the **current conversation only**, which is single-user — within history there is exactly one human ("user" = the current speaker). The Lyle/Jodie bleed does not come from history; it comes from **retrieved memory** (cross-conversation), which is where Jodie appears in the third person.

**The actually-relevant attribution gap (the deeper cause — surfaced, see below):** retrieved **conversation** chunks are formatted with **no speaker attribution**. `_format_retrieved_memories` (`context.py:266-267`) emits `[Conversation — {created_at}]\n{text}`. The chunk metadata carries `user_id` (`chunking.py:217`) but **not** `user_name`, and the formatter drops even the id. So a retrieved chunk from a *Jodie* conversation is indistinguishable from a *Lyle* one — both render as `[Conversation — date]`. That, not the live-history label, is the memory-side identity gap.

**Recommendation:**
- **Live-history per-turn author label: NOT in scope** (single-user history; would not move this bug).
- **Retrieved-conversation-chunk speaker attribution: a separate, higher-leverage follow-up** (see below) — keep it out of Option 1, which stays reposition + rephrase.

---

## Deeper cause surfaced (per the "surface it, don't expand scope" constraint)

Position + wording is genuinely a contributing cause and Option 1 is a valid, low-risk first lever — so I am **not stopping**. But the diagnosis is incomplete: even with the directive moved and rephrased, **retrieved conversation chunks remain unattributed** (`[Conversation — date]`), so a Jodie-dense memory block still presents Jodie's words/facts with no marker that they belong to a *different* person. The rephrase adds a *blanket* disclaimer ("memory may mention other people"), which helps, but per-chunk attribution would be markedly stronger.

**Recommended follow-up (separate task, NOT Option 1):** attribute retrieved conversation chunks to their speaker — e.g. `[Conversation with Jodie — date]` vs `[Conversation with Lyle — date]`. This requires `user_name` (or a name resolved from `user_id`) to be available to `_format_retrieved_memories` — currently only `user_id` is in chunk metadata — so it is a larger change touching chunk metadata and/or a user-id→name lookup. Kept separate from this placement/addressing fix.

---

## STEP 5 — Verification plan (behavioral + probabilistic)

No clean unit assertion exists for "does the model conflate Lyle and Jodie." Two layers:

**1. Static — did the reposition land? (deterministic)**
Use the existing `ANAM_DEBUG_PROMPT=1` flag (`config.py:401`, `routes.py:1019` → `debug_prompt.system_prompt`). After the change, capture one turn and assert in the captured `system_prompt` that `"[Current Situation]"` (and the new direct-address text) appears **before** `"Retrieved context follows."`. This proves the placement without any model behavior. Also update/keep `tests/test_context.py` order assertions (Step 2) as the in-suite deterministic check.

**2. Behavioral — did the bleed drop? (probabilistic, multi-sample)**
- Seed a state where Jodie-dense memory is retrievable, then converse **as Lyle** with prompts likely to pull Jodie chunks.
- Run **before-fix and after-fix** across **multiple samples** (≥10–20 turns over varied prompts), not a single turn — bleed is probabilistic.
- Score each turn for bleed: does the entity address Lyle as Jodie, attribute Jodie's facts/relationship to Lyle, or otherwise treat a third-person memory subject as the current speaker? Compare bleed rate before vs after.
- Run with retrieved memory held as constant as possible across before/after so the only variable is the prompt change.

**Harness note:** there is **no behavioral-probe harness in code today** (grep finds "probe/baseline/divergence" only in docs — `NORTH_STAR.md`, session handoffs — not a runnable harness). So this verification is currently a **manual/scripted before-after sampling**, not an automated probe. Building a reusable identity-bleed probe (and the memoryless-control comparison NORTH_STAR envisions) is a worthwhile but **separate** investment; recommend noting it rather than blocking this fix on it.

---

## Scope / constraints honored
- Touches only the current-situation block placement + wording in `context.py` (and the one order assertion in `tests/test_context.py`, plus the docstring).
- Does **not** touch artifact-injection / `_event_text` (separate queued task in the same file).
- Does **not** modify `soul.md` or the system-prompt identity/persona framing.
- Retrieved-chunk attribution and a behavioral-probe harness are surfaced as **separate** follow-ups, not folded in.

## Open decisions for approval
1. **Rephrase wording:** A (generic, recommended) vs dynamic other-names vs B (literal "Jodie").
2. **Situation placement:** immediately before retrieved memories (recommended) vs earlier in the prompt.
3. **Confirm** the retrieved-chunk attribution follow-up is tracked as its own task (not this one).

*Plan only. No code changed, no commit.*
