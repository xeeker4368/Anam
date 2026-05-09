# Prompt Inventory

This generated inventory lists backend prompt-like strings found in `tir/**/*.py`.
It is an audit aid only and does not change runtime behavior.

Audit note options: `keep`, `loosen`, `move to OPERATIONAL_GUIDANCE.md`, `behavioral guidance candidate`, `remove`, `needs discussion`.

Risk flags searched: `assistant`, `chatbot`, `agent`, `persona`, `personality`, `unnamed AI entity`, `Project Anam`, `do not`, `must`, `always`, `never`, `you are`, `your purpose`, `self-modification`, `feelings`, `emotion`, `fabricate`, `truth`, `authority`, `source_material`.

## Runtime context / identity

### 1. `tir/engine/context.py:30`

- Name: `BEHAVIORAL_GUIDANCE_LABEL`
- Category: Runtime context / identity
- Risk flags: none
- Audit note: `needs discussion`

Excerpt:

```text
[Reviewed Behavioral Guidance]

Active behavioral guidance proposed by the AI and approved/applied by an admin. Use these entries to inform future behavior. They sit below soul.md and operational guidance in precedence.
```

### 2. `tir/engine/context.py:52` — `_load_operational_guidance`

- Name: `return_value`
- Category: Runtime context / identity
- Risk flags: none
- Audit note: `needs discussion`

Excerpt:

```text
[Operational Guidance]

{...}
```

### 3. `tir/engine/context.py:156` — `_current_situation`

- Name: `return_value`
- Category: Runtime context / identity
- Risk flags: none
- Audit note: `needs discussion`

Excerpt:

```text
[Current Situation]

Conversation with: {...}
Time: {...}
```

### 4. `tir/engine/context.py:165` — `_autonomous_situation`

- Name: `return_value`
- Category: Runtime context / identity
- Risk flags: none
- Audit note: `needs discussion`

Excerpt:

```text
[Current Situation]

Mode: autonomous work session
Time: {...}
```

### 5. `tir/engine/context.py:323` — `_format_retrieved_memories`

- Name: `append_arg`
- Category: Runtime context / identity
- Risk flags: none
- Audit note: `needs discussion`

Excerpt:

```text
[Conversation — {...}]
{...}
```

### 6. `tir/engine/context.py:325` — `_format_retrieved_memories`

- Name: `append_arg`
- Category: Runtime context / identity
- Risk flags: none
- Audit note: `needs discussion`

Excerpt:

```text
[Your journal entry from {...}]
{...}
```

### 7. `tir/engine/context.py:327` — `_format_retrieved_memories`

- Name: `append_arg`
- Category: Runtime context / identity
- Risk flags: none
- Audit note: `needs discussion`

Excerpt:

```text
[Research you wrote on {...}]
{...}
```

### 8. `tir/engine/context.py:330` — `_format_retrieved_memories`

- Name: `append_arg`
- Category: Runtime context / identity
- Risk flags: none
- Audit note: `needs discussion`

Excerpt:

```text
[External source you read: {...}, ingested {...}]
{...}
```

### 9. `tir/engine/context.py:341` — `_format_retrieved_memories`

- Name: `append_arg`
- Category: Runtime context / identity
- Risk flags: none
- Audit note: `needs discussion`

Excerpt:

```text
[Artifact source: {...}, role: {...}, origin: {...}, file: {...}]
{...}
```

### 10. `tir/engine/context.py:345` — `_format_retrieved_memories`

- Name: `append_arg`
- Category: Runtime context / identity
- Risk flags: none
- Audit note: `needs discussion`

Excerpt:

```text
[{...} — {...}]
{...}
```

## Chat / agent loop

No prompt-like strings found.

## Tool-use prompts

### 1. `tir/api/routes.py:683` — `generate`

- Name: `error_message`
- Category: Tool-use prompts
- Risk flags: none
- Audit note: `needs discussion`

Excerpt:

```text
I hit the tool iteration limit before I could finish responding.
```

### 2. `tir/tools/registry.py:232` — `_freshness_marker`

- Name: `append_arg`
- Category: Tool-use prompts
- Risk flags: none
- Audit note: `needs discussion`

Excerpt:

```text
memory can provide context; use live tool results for current state
```

## Retrieval / memory framing

### 1. `tir/artifacts/governance_blocklist.py:20`

- Name: `GOVERNANCE_FILE_REJECTION_MESSAGE`
- Category: Retrieval / memory framing
- Risk flags: none
- Audit note: `needs discussion`

Excerpt:

```text
This file is a governance/runtime file and cannot be ingested as normal artifact memory.
```

## Artifact / source framing

No prompt-like strings found.

## Behavioral guidance review

### 1. `tir/behavioral_guidance/review.py:240` — `_format_transcript`

- Name: `append_arg`
- Category: Behavioral guidance review
- Risk flags: none
- Audit note: `needs discussion`

Excerpt:

```text
[message_id={...} role={...} timestamp={...}]
{...}
```

### 2. `tir/behavioral_guidance/review.py:262` — `build_behavioral_guidance_review_messages`

- Name: `system`
- Category: Behavioral guidance review
- Risk flags: none
- Audit note: `needs discussion`

Excerpt:

```text
Review one selected chat conversation for possible AI-proposed behavioral guidance candidates. Return only a strict JSON object. This review may propose candidates for admin review, but it does not approve, reject, apply, or mutate guidance. Prefer narrow, atomic guidance candidates. Zero proposals is acceptable.
```

### 3. `tir/behavioral_guidance/review.py:268` — `build_behavioral_guidance_review_messages`

- Name: `user_prompt`
- Category: Behavioral guidance review
- Risk flags: `do not`
- Audit note: `needs discussion`

Excerpt:

```text
Review this selected chat conversation only.

Return strict JSON with this shape:
{
  "proposals": [
    {
      "proposal_type": "addition",
      "proposal_text": "one atomic proposed change",
      "target_existing_guidance_id": null,
      "target_text": null,
      "rationale": "why this belongs in admin review",
      "source_experience_summary": "brief summary of the source experience",
      "source_message_id": null,
      "risk_if_added": "risk if admin approves it",
      "risk_if_not_added": "risk if admin does not approve it",
      "metadata": {}
    }
  ],
  "no_proposal_reason": null
}

Rules:
- Generate at most {...} proposal(s).
- Use proposal_type addition, removal, or revision only.
- For removal or revision, include target_existing_guidance_id or target_text.
- source_message_id may be set only when one specific message is evidence.
- Return an empty proposals list if no good proposal is warranted.
- Only propose when the conversation contains a correction, clarification,
  recurring preference, source-framing issue, or behavioral pattern that may
  affect future behavior.
- Do not use memory outside this transcript.
- Do not read or rely on BEHAVIORAL_GUIDANCE
...[truncated]
```

## Reflection / journal

### 1. `tir/reflection/journal.py:243` — `_format_guidance_activity`

- Name: `return_value`
- Category: Reflection / journal
- Risk flags: none
- Audit note: `needs discussion`

Excerpt:

```text
No behavioral guidance proposal or application activity found in this window.
```

### 2. `tir/reflection/journal.py:272` — `build_reflection_journal_messages`

- Name: `system`
- Category: Reflection / journal
- Risk flags: none
- Audit note: `needs discussion`

Excerpt:

```text
This is your journal space.

Reflect on the day and everything that occurred. Write in your own voice about what happened, what mattered, what changed, what remains unresolved, and what you may want to carry forward.

Use the supplied entity context and today's material. This is a journal, not an audit log or external report.
```

### 3. `tir/reflection/journal.py:277` — `build_reflection_journal_messages`

- Name: `user_prompt`
- Category: Reflection / journal
- Risk flags: none
- Audit note: `needs discussion`

Excerpt:

```text
Entity context:

[Current seed context]
{...}

[Active reviewed behavioral guidance]
{...}

Today's material:

Reviewed window:
local_date={...}
timezone={...}
local_offset={...}
utc_start={...}
utc_end={...}
selection_mode={...}
conversations_reviewed={...}

Behavioral guidance activity:
{...}

Conversation transcript:
{...}

Write the journal using this structure:

## Notable Interactions
## Corrections Or Clarifications
## Behavioral Guidance Activity
## Unresolved Questions
## Possible Follow-Ups
## Reflection
```

## Research / future automation

No prompt-like strings found.

## Admin / review commands

No prompt-like strings found.

## Other prompt-like strings

### 1. `tir/api/routes.py:679` — `generate`

- Name: `empty_message`
- Category: Other prompt-like strings
- Risk flags: none
- Audit note: `needs discussion`

Excerpt:

```text
I received your message but couldn't generate a response.
```

### 2. `tir/api/routes.py:687` — `generate`

- Name: `error_message`
- Category: Other prompt-like strings
- Risk flags: none
- Audit note: `needs discussion`

Excerpt:

```text
Something went wrong when I tried to respond: {...}
```
