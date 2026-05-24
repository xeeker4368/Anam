# Interpretation Trace Design

## Status

Design only. No runtime code, prompts, tests, database schema, Chroma behavior, research generation, Moltbook or web behavior, guidance files, `soul.md`, model configuration, or UI behavior are changed by this document.

Interpretation traces are a proposed visible artifact pattern for future research notes, journals, and working theories. They are not currently required by runtime generation.

## Purpose

Project Anam records source-labeled inputs and durable outputs, but future research continuity needs a clearer visible record of how source material was interpreted.

An interpretation trace should help Lyle and the entity inspect, over time:

- what signals mattered
- what signals were discounted or treated as weak
- what uncertainty remained
- what could change the interpretation later
- whether an interpretation shifted across later research passes

The trace is not meant to expose hidden chain-of-thought or private scratchpad reasoning. It is a concise, visible, source-linked summary of interpretation.

## Core Principles

- Interpretation traces are visible summaries, not hidden chain-of-thought.
- Interpretation traces are not raw scratchpad reasoning.
- Interpretation traces are provisional.
- Interpretation traces are not behavioral guidance.
- Interpretation traces are not self-understanding unless later explicitly promoted through a reviewed path.
- Interpretation traces are not project decisions or runtime instructions.
- Interpretation traces must remain source-linked.
- Interpretation traces must not assign personality, identity, values, avatar, or name.
- Interpretation traces should help Lyle and the entity inspect interpretation over time.

## What An Interpretation Trace Contains

An interpretation trace should record the visible interpretive shape of a research pass.

It should answer:

- Which source-linked observations influenced the note?
- Which available inputs were weak, irrelevant, stale, low-confidence, only analogical, or unusable?
- How were the signals interpreted at a high level?
- What remains unresolved?
- What later evidence or observation would weaken, revise, or replace the current interpretation?

It should not record:

- hidden chain-of-thought
- raw model scratchpad text
- step-by-step private deliberation
- token-level reasoning
- invented motives or personality traits
- conclusions promoted to truth

## Recommended V1 Shape

V1 should use an inline Markdown section in research notes:

```markdown
## Interpretation Trace

### Signals Considered

### Signals Discounted

### Interpretation

### Uncertainty

### What Would Change This View
```

Each subsection should stay short. A bounded research note should usually need only a few bullets per subsection.

### Signals Considered

Concise source-linked observations that influenced the note.

Examples:

- Prior research note `research/2026-05-22-example.md` framed the open loop as unresolved rather than settled.
- Moltbook post `post_id=...` in source trace `research/source-traces/...moltbook-sources.json` provided an external example of the question appearing in live agent discussion.
- The selected open loop `open_loop_id=...` had not been researched before this pass.

### Signals Discounted

Inputs that were present but weak, irrelevant, stale, low confidence, unusable, only analogical, or not source-grounded enough to rely on.

This section must avoid overclaiming. If the system did not deeply evaluate a source, say so plainly.

Examples:

- Moltbook collection failed with `collection_error=true`; this limited interpretation and is not evidence of absence.
- No usable Moltbook results were collected; this is absence of usable collected material, not proof that no relevant material exists.
- A prior note suggested a possible follow-up, but did not include source evidence beyond model-only reasoning.

### Interpretation

A short visible summary of how the considered and discounted signals shaped the note.

This should be a high-level explanation, not a detailed reasoning transcript.

### Uncertainty

What remains unresolved, weak, or dependent on future sources.

### What Would Change This View

Future evidence, source material, observation, or later research that would weaken or revise the interpretation.

Examples:

- A future web source trace finds official documentation contradicting the current interpretation.
- Repeated bounded research passes continue to produce no new source material.
- Later journals show the same pattern was transient rather than recurring.

## Inline Section Versus Sidecar

Recommended v1: inline section only.

Research notes are already durable, inspectable, optionally registered artifacts. Keeping the trace inside the note:

- avoids a new DB table
- avoids a new sidecar file type
- keeps interpretation next to the findings it qualifies
- lets existing research-note registration/indexing include it when explicitly requested

Do not add interpretation trace sidecars in v1.

Future sidecars may be useful for:

- working theories that compare many prior notes
- large multi-source research passes
- machine-readable interpretation revision graphs
- explicit evaluation artifacts for 30/60/90 day reviews

Those should be separate approved designs or runtime patches.

## First Runtime Target

The first runtime target should be bounded research notes.

Bounded research is the best first target because it already has:

- a specific open loop
- prior provisional research context
- optional Moltbook source traces
- explicit write/register behavior
- durable metadata updates only after successful output

Normal chat should not automatically produce interpretation traces.

## Later Targets

After bounded research proves the shape useful:

- Manual research continuation may add interpretation traces when extending or revising prior notes.
- Reflection journals may include lighter interpretation traces only when making interpretive claims.
- Future working theories should likely require interpretation traces, because theories need visible evidence, discounted signals, uncertainty, and revision criteria.

## Indexing And Retrieval

No new DB table in v1.

No Chroma or FTS behavior change in v1.

If a research note is registered and indexed, the inline interpretation trace may be indexed as part of the note through the existing research-note indexing path.

Labels must make clear that the trace is provisional interpretation, not truth.

Recommended future artifact metadata:

```json
{
  "contains_interpretation_trace": true,
  "interpretation_trace_version": "interpretation_trace_v1",
  "interpretation_trace_is_provisional": true
}
```

Retrieved research chunks should continue to use working-research framing. Interpretation traces should not override source labels, source trust metadata, or provisional status.

## Source-Linking Rules

Each trace bullet should ideally reference one of:

- prior research note/path
- Moltbook post id or Moltbook source trace path
- future web URL or web source trace path
- open loop id
- collection failure or no-result state
- explicit absence of useful source material

Do not cite vague impressions as if they were sourced.

If the trace refers to a source collection failure, it should name the failure state rather than converting it into evidence.

If the trace refers to no usable results, it should say no usable material was collected, not that no relevant material exists.

## Failure And No-Result Handling

For source collection failure:

```markdown
- Moltbook source collection failed with `collection_error=true` and `error_type=<type>`. This limited interpretation and is not evidence that no relevant Moltbook material exists.
```

For no usable results:

```markdown
- The Moltbook query/feed returned no usable collected results. This is absence of usable collected material, not proof of absence.
```

For model-only research:

```markdown
- No external source trace was collected in this pass; interpretation is limited to prior provisional research and the current open-loop framing.
```

## Chain-Of-Thought Boundary

Good prompt framing:

```text
Summarize the visible interpretation in concise source-linked terms: what mattered, what was discounted, what remains uncertain, and what could change the view.
```

Bad prompt framing:

```text
Explain your full reasoning step by step.
```

Implementation should not request hidden or private reasoning. It should request a short, inspectable interpretation summary.

The trace should be written as artifact content for human/project review, not as model-private reasoning.

## Temporal Awareness And Revision

Interpretation traces should support future comparison.

Later research can ask:

- Did the same signal recur?
- Did a previously discounted signal become stronger?
- Did a collection failure later become a successful source trace?
- Did a prior uncertainty get resolved, weakened, or reframed?
- Did the entity revise an interpretation based on later source-linked evidence?

This supports the experiment hypothesis without turning any one trace into proof of development.

## Relationship To Working Theories

Research notes and interpretation traces are not working theories.

A future working theory should be a separate reviewed artifact or record that can cite one or more interpretation traces. When working theories are designed, they should likely require:

- evidence considered
- evidence discounted
- current interpretation
- confidence or uncertainty
- revision criteria
- supersession/revision history

Do not promote interpretation traces into working theories automatically in v1.

## Relationship To Journals

Reflection journals should not be forced to produce interpretation traces every day.

A journal may use a lighter trace only when it makes an interpretive claim, such as a recurring pattern, changed interpretation, or uncertainty about prior experience.

Quiet or low-signal journals should remain allowed.

## Risks

- The trace may become performative filler.
- The model may rationalize after the fact.
- The trace may be mistaken for truth.
- The trace may drift too close to chain-of-thought if prompted poorly.
- Research notes may become longer and noisier.
- "Signals Discounted" may overclaim source evaluation.
- The trace may make weak source material seem more deliberate than it was.

## Mitigations

- Keep traces short.
- Keep traces structured.
- Keep traces source-linked.
- Label traces as provisional.
- Do not request hidden/private reasoning.
- Allow "nothing useful to discount" when honest.
- Allow "no external source trace collected" when applicable.
- Require collection failures and no-result states to be represented as limitations, not evidence.

## Deferred

- Runtime prompt changes.
- Required research-note generation changes.
- Reflection journal integration.
- Working theory integration.
- Interpretation trace sidecars.
- DB schema changes.
- Chroma/FTS indexing changes.
- UI surfaces.
- Automated evaluation of interpretation traces.
- Promotion of traces to self-understanding, behavioral guidance, project decisions, or working theories.

