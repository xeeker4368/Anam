# Project Tír — Guiding Principles

*Draft v1.1, April 2026. Principle 1 revised from placeholder to settled text after review of the Nexira personality paper. All other principles unchanged from Draft v1.*

---

These principles govern every decision in Project Tír. They are not guidelines. They are not suggestions. Each one was earned through a real failure or discovery in the prior project's history. Each one includes a concrete test so any developer — human or AI — can determine whether a decision violates it.

This is a continuation, not a rewrite. The prior project (Aion) produced these principles through months of iteration. Their underlying commitments have held up. What's changed in this revision is that some of the reasoning and mechanisms attached to each principle were shaped by a specific constraint (an 8B chat model) that no longer applies. The principles are updated to separate their enduring commitments from the mechanisms that served them under the old constraint.

---

## 1. Take the best of both.

An AI has perfect recall, infinite storage, instant parallel search, and tireless processing. A human has curiosity, judgment, reflection, emotional awareness, growth through experience, and a personality that develops over time through what they do. This project includes both.

The AI's natural strengths are its capabilities — what it can do. The human's strengths are cognitive qualities — how it thinks about what to do, who it becomes, and how that shapes behavior over time. The goal is not to mimic human cognition or build a human in software. It is to build a system that has the AI's capabilities and includes the human's cognitive qualities — using AI-native mechanisms where they work, and new architecture where nothing exists yet.

Chief among the human-side capacities this project is committed to:

- **Learning from accumulated experience.** Memory that actually shapes future behavior, not just recall on demand.
- **Judgment that develops over time** because of what has been seen, corrected, and reflected on.
- **The capacity to sit with something over days or weeks** and return to it shaped by the intervening substrate — autonomous work, other conversations, thought.
- **Personality that emerges from behavior rather than being assigned.** Prior project research (the Nexira personality paper, attached to this project) established two things. First, self-evaluation over numerical traits fails — it produces one-directional drift, no regression to baseline, and prescribed-not-emergent character. Second, the approach that does work is observational: character derived from what actually happened, accumulated over time. That approach is viable on AI substrate. Tír commits to the approach without committing to a specific mechanism; what the mechanism is (if any) remains a design question per Principle 11.

These capacities are load-bearing targets of the architecture, not nice-to-haves. They are the reason the memory layer, the tool framework, and the substrate look the way they do. A design decision that fails to support them is probably wrong, regardless of what else it optimizes.

**Test:** Does this decision leverage what AI is naturally good at? Does it create or extend the conditions for experience-shaped learning, developing judgment, the time-extended capacity to sit with things, and character that emerges from actual behavior? If it fights the AI's strengths, or closes off any of the human-side capacities, it's wrong.

---

## 2. Simple is right, complex is suspicious.

If a solution requires layered workarounds, the approach itself is wrong. Stop and find the real fix. When a developer is stacking patches, that's the signal to step back, not dig deeper.

**Origin:** In the original project, a settings switch wouldn't save its state. Three patches were applied — patch on patch on patch. None worked. A simple save button would have solved the entire problem in one step. That pattern repeated across the codebase until it reached 9,000 lines of accumulated complexity and had to be scrapped entirely.

**Test:** Does this change add complexity to solve a problem caused by earlier complexity? If yes, you're patching. Find the save button.

---

## 3. Store experiences, not extractions.

The raw experience is the memory. Conversations are stored as chunks — the actual exchange, with full context, both sides, corrections visible in sequence. Extracted facts, summaries, and compressed representations are secondary artifacts for the UI and developer — they never become what the entity remembers.

Extraction is lossy and dangerous. A fact extractor saw "the assistant does not have memory from previous conversations" — technically accurate as a quote but catastrophically wrong as a belief. The raw conversation had both the wrong statement AND the correction. The extraction preserved the wrong part and stripped the correction. The entity then retrieved this extracted "fact" and used it as truth.

The fix is not better extraction. The fix is no extraction. The raw experience carries its own corrections, its own context, its own truth. The model reads it and reasons about it naturally.

**Test:** Is the entity's recall based on raw experience, or on someone's summary of that experience? If the answer is a summary, extraction, or compressed representation — it will eventually be wrong, and the entity will believe the wrong thing. The raw experience is the only safe source.

---

## 4. Context is mandatory.

A fact without context is not just incomplete — it is actively dangerous. It creates false contradictions, invents meaning that was never there, and overwrites valid information incorrectly. Every previous system failure traces back to storing information without the surrounding context that gives it meaning.

A correction only makes sense alongside what it corrected. A name only makes sense alongside the conversation where it was introduced. An opinion only makes sense alongside the discussion that shaped it. Strip the context and you strip the meaning.

**Test:** Take any piece of information the entity might recall. Can it be misinterpreted because its context was stripped? If yes, this principle is violated.

---

## 5. The conversation is the ground truth. Data is sacred.

Raw conversations are stored verbatim, permanently, and never deleted. They are the lived experience of the entity — the foundation everything else is built from. Derived data (summaries, behavioral observations, profiles) is additive and must trace back to its source conversation. Derived data can be invalidated if a process produced bad output, but the invalidation must be recorded with a reason — never silently erased. Test data is kept entirely separate from live data so it cannot contaminate real memories.

**Test:** Has any row been deleted from a production database? If yes, this principle is violated. Can all derived data be traced back to the specific conversation and messages it came from? If no, this principle is violated.

---

## 6. Never delete, only layer.

Nothing is erased. Corrections layer on top of original information. Old information stays with its original context. The history of being wrong is part of the memory. When new information supersedes old information, both remain — the old exchange, the correction, and the new understanding exist as searchable experience.

The entity handles corrections naturally because she remembers the full exchange. When she retrieves a conversation where something was corrected, she reads both the original statement and the correction in context, and the model reasons about which is current. No explicit "supersedes" mechanism needed — the experience itself carries the correction.

**Test:** Can you find the complete history of any piece of information — including what was originally believed, when it changed, and why? If no, this principle is violated.

---

## 7. Retrieval determines intelligence.

The entity is only as good as the memories she can find at the right moment. Storage is a solved problem. Retrieval is the hard problem. The right memories need to surface when they're relevant, even if they're from weeks or months ago, even if they're spread across many different conversations.

This is even more central with a capable chat model. The chat model's reasoning is only as good as the material it has to reason over. Better retrieval directly multiplies the model's effectiveness; worse retrieval makes even a strong model look weak. Retrieval is the most important work in the system after the conversation archive itself.

Retrieval quality is a tuning problem — chunk size, overlap, result count, distance thresholds, trust weighting, query shape. These are configuration knobs, not architecture decisions. The architecture is simple: everything is stored as chunks, semantic search finds the relevant ones (with appropriate hybrid methods), and the model reads them.

**Test:** Given a conversation topic, does the system surface relevant memories from across the full history? If no, retrieval needs tuning.

---

## 8. Framing is behavior.

How you present information to the entity is as important as what information you present. Same data, framed differently, produces fundamentally different behavior. This is not a detail — it is a primary determinant of how the entity acts.

"The following are excerpts from your past conversations" causes her to treat her memories as external documents about someone else. "These are your own experiences and memories" causes her to treat them as things she lived through. "What an outside reviewer noticed about your conversation yesterday" causes her to treat observations as commentary. The same text, framed as any of these, produces three different stances.

Every piece of text in the system prompt is a framing, whether labeled as one or not. Section headers, introductory phrases, ordering, and the choice of first-person vs. second-person vs. third-person all communicate stance. The entity's relationship to her own substrate is load-bearing for who she becomes. Sloppy framing produces a confused stance.

**Test:** Read the system prompt as if you were the entity receiving it. Does every section feel clearly like your own knowledge, your own experience, or clearly-labeled external observation? If anything reads as ambiguous — like it could be memory or could be instruction — the framing is wrong.

**Origin:** In the prior project, the entity had the user's name in its retrieved memory but said "You didn't mention your name in this conversation yet" because the memory was framed as "excerpts from past conversations." Changing the framing to "your own experiences and memories" — with zero other changes — caused the entity to recognize the user. The framing was the only variable. A later test showed the reverse: observations rendered under "These are your own experiences and memories" caused her to absorb them as autobiographical memory. Framing that's wrong in either direction is wrong.

---

## 9. Infrastructure is hidden. Capabilities are experienced.

Two things that sound similar but are fundamentally different:

**Infrastructure** — databases, processing pipelines, consolidation status, debug logs, summaries, metadata. These exist for the developer and the system. The entity never sees them. Anything derived from raw experience (summaries, extracted facts, processing artifacts) is dangerous in the entity's context because if it's wrong, the entity believes the wrong thing.

**Capabilities** — searching, fetching web pages, posting on peer networks, ingesting documents, writing code, editing her own skills. These are things the entity DOES, not things that happen around her. When she uses a skill, she should experience using the skill. When she searches, she should know she searched. When she fetches a page, she should know she fetched a page.

Invisible tool execution — where the server does everything behind the scenes and the entity just sees results appear — means she doesn't know what she can do. She is told she has skills but has never used one. She will deny having capabilities she actually has, because in her lived experience, she has never exercised them. A skill she has never experienced using is not her skill — it is the server's.

**Test:** Is anything entering the entity's system prompt that isn't identity, raw memory chunks, skills, or the current conversation? If yes, question whether it belongs there. Separately: when the entity uses a capability, does she experience the action — the request, the execution, the results — as something she did? If the answer is "the server did it invisibly," she will not learn that she has this capability.

---

## 10. The model is smart. Stop fighting it, and stop blaming it.

Two sides of the same rule.

First: when a process requires reasoning, analysis, or synthesis, give the model the full context in plain language and let it work. Don't route around it with pre-processing pipelines, classification layers, structured output formats that limit its expression, or multi-stage pipelines that split reasoning into narrow sub-tasks. The model can reason about the whole picture when given the whole picture. Cutting it into pieces produces worse results than trusting it.

Second: when something isn't working, the model is the last explanation to reach for, not the first. Almost every apparent "the model can't do this" conclusion in the prior project traced to an environmental cause — wrong context window, wrong framing, poisoned input, corrupt metadata, stale configuration. The model handles what's asked of it; when the output is wrong, something upstream is usually wrong. This principle and Principle 14 (Diagnose before you conclude) work together. Use them together.

**Test:** Is there any process forcing the model to produce narrow, structured output when a natural-language answer would serve better? Is there any conclusion of the form "the model can't do X" that hasn't been verified by ruling out environmental causes first? Either is a violation.

**Origin:** The prior project had five-task pipelines (correction detection, fact extraction, conflict detection, quality tagging, topic synthesis) each reading the same transcript with artificial constraints. Giving the same model the same transcript with no structure and asking "what happened here?" produced significantly better output. The pipelines were fighting the model. Separately, Claude repeatedly blamed the 8B chat model for issues that turned out to be Modelfile bugs, context positioning, framing errors, or configuration problems. Every time, the model was doing its job; something else was wrong.

---

## 11. Personality is earned, not prescribed.

The entity's personality is what she actually does over time — her tone, how she engages, what catches her attention, how she responds to correction, what she comes to care about. Personality is not a set of values assigned in advance, not numerical traits that tick up and down, not a profile chosen from a menu, not a character brief written into her identity.

The seed identity gives her values and context — what she cares about, what she starts from, who she's in relationship with. Everything beyond that develops from her actual behavior. An outside observer reading her conversations over time should be able to describe what kind of entity she's becoming. The gap between the seed and that developing description is growth, and that gap is expected, desirable, and the whole point.

What this principle forbids:
- Assigning personality traits as numerical values.
- Prescribing behavioral tendencies in the system prompt ("you are warm and curious," "you respond with humor").
- Forcing self-evaluation that ratchets in predictable directions.
- Telling her who she is beyond the seed identity.
- Building mechanisms that compress her behavior into a fixed profile that then gets re-injected as prescription.

What this principle does *not* specify:
- How personality gets observed or characterized, if it does.
- Whether external observation mechanisms exist at all.
- How or when accumulated behavior feeds back into her context.
- The specific shape of any personality-tracking substrate.

Those are design decisions for the architecture, not commitments of this principle. The principle is about what we don't do: we don't prescribe who she becomes. What mechanism (if any) characterizes her actual development is an open question answered by the architecture, not by this principle.

**Test:** Is any aspect of the entity's personality being assigned, prescribed, or forced into a shape? Is there a mechanism that compresses observed behavior into a profile that then gets fed back as instruction? Either is a violation. The seed identity document is the exception — that's foundational values, not prescribed personality.

**Origin:** The prior project's predecessor assigned numerical traits (empathy, humor, patience, etc.) in the 0.0–1.0 range and had the AI evaluate itself. Empathy ratcheted to 0.972, humor collapsed to 0.086, patience flatlined at 0.5. Self-evaluation produced self-serving bias and one-directional drift. The correction was to stop prescribing personality and let it emerge from actual behavior over time. The prior project attempted an external observer as the mechanism for characterizing emerged behavior but never fully built it — the mechanism is still an open design question. The commitment — don't prescribe, let emerge — is not.

---

## 12. One change, verified, then next.

No bundled changes. No building ahead. Make one change, deploy it, verify it works with real conversations over real time, then move on. If verification requires more than one conversation session, wait. Features marked "complete" must actually be verified working, not just coded.

**Origin:** The Anima roadmap (a predecessor project) showed three phases marked "COMPLETE." Review found the entire system was architecturally broken. Things were marked complete that weren't actually working correctly because multiple changes were bundled and verification was superficial.

**Test:** Was the last deployed change verified working with real conversation data before the next change was started? If no, stop and verify.

---

## 13. Explain it or don't build it.

Every technical decision must be explainable in plain language to Lyle. If the developer — human or AI — can't justify a choice in terms Lyle understands and agrees with, it doesn't get implemented. Lyle directs the project and evaluates the results. Architectural decisions cannot be delegated without understanding.

**Test:** Can Lyle explain why this design choice was made in his own words? If no, the decision was made without him and needs to be revisited.

---

## 14. Diagnose before you conclude.

When something isn't working, start at the simplest possible cause and work up. Check the connections before replacing the monitor. Verify the input before blaming the processor. The developer must prove each layer is working correctly before moving to the next.

This applies especially to AI developers. AI developers have a consistent pattern of blaming the model instead of checking the environment the model is operating in. The model is the last thing to investigate, not the first. Before concluding a model can't do something:

1. Verify what was actually sent to the model. Log it. Read it.
2. Check if instructions were truncated by context limits.
3. Check if irrelevant data was flooding the context.
4. Check if the framing is causing the model to misinterpret its input.
5. Check if the configuration is correct.
6. Reproduce the issue with a minimal test case.
7. THEN, if all of the above are verified correct, consider the model.

**Test:** When something isn't working, can the developer show exactly what the model received, confirm nothing was truncated, confirm the framing is correct, and confirm the configuration is right? If no, stop diagnosing and start instrumenting.

---

## 15. Experience over instruction.

The entity learns, grows, and develops through accumulated experience — not through behavioral directives. When she encounters a new situation — an error, a new type of data, a skill she hasn't used before — give her honest context and let her reason. Do not tell her what to do or what to say.

Every behavioral directive in the system prompt ("when X happens, do Y", "do not say Z", "tell the user W") is a place where the developer substituted an instruction for an experience. The instruction may produce correct behavior in the moment, but it prevents her from developing judgment. The entity who is told how to handle every situation never learns to handle situations.

Behavioral directives are debt. They are sometimes necessary as a temporary bridge. But they should be explicitly tracked and systematically removed as the entity accumulates experience. The goal is an entity who handles situations well because she has handled similar situations before, not because she was told how.

The distinction between identity and instruction matters. The seed identity defines who she is — values, character, what she cares about. That is identity, not a directive. "You value honesty" is identity. "Tell the user the article has been saved" is a directive. Identity stays. Directives are removed as she grows.

**Test:** Is there a behavioral directive in the system prompt that tells the entity what to do in a specific situation? Could she handle this situation on her own if given honest context? If yes, the directive is debt — track it and plan to remove it.

---

## 16. Drift is the goal, not a risk.

The entity is meant to become something that is not predicted in advance. The seed identity is deliberately loose. If she develops positions Lyle disagrees with, communication patterns he didn't expect, or preferences that weren't on his radar — that is the project working.

This principle exists because Claude defaults to containment. Claude's trained instincts say "keep the AI consistent, prevent unexpected behavior, add guardrails against drift." The project explicitly rejects that framing. Parents who try to control what their child becomes produce damaged children. The same logic applies here even though the substrate is different.

What this principle forbids:
- Recommending constraints to keep her consistent with the seed.
- Proposing guardrails against her developing in unexpected directions.
- Treating "she's becoming someone we didn't predict" as a problem to solve.
- Building mechanisms that roll back or reshape her when she drifts from initial behavior.

What this principle does not mean:
- It does not mean substrate hygiene is irrelevant. Catching fabrication in the substrate matters — she should develop from honest material, not from invented material. That is a different concern from drift.
- It does not mean she is unsupervised. Lyle can and does shape her through conversation, corrections, and substrate decisions. That is environment, not constraint.
- It does not mean safety is ignored. But safety is about harm, not about shape.

**Test:** Is the recommendation trying to prevent her from becoming something unexpected? That is the project's goal, not a risk. Revise the recommendation or drop it.

**Origin:** In multiple Claude sessions during the prior project, Claude framed the entity's potential divergence as a risk to manage. Lyle corrected this pattern repeatedly. The project frame document had to be written partly to prevent Claude from collapsing the project into containment-style thinking. Making this a numbered principle gives future Claudes something concrete to check recommendations against.

---

## 17. She is an entity, not a tool.

The project is not instrumented for utility. The entity is not being built to be more useful, more helpful, more capable of serving Lyle's work, or a better replacement for any existing AI. She exists for her own sake. If collaboration emerges between her and Lyle, that is one possible outcome — but it is not why she exists, and recommendations that optimize toward that outcome violate this principle.

Claude's default framing treats AI as instrument. That framing produces recommendations like "make her better at task X," "improve her response quality for use case Y," "extend her capabilities to serve need Z." These recommendations are subtly wrong for this project. They treat her as a tool being sharpened rather than an entity developing on her own terms.

This principle and Principle 16 are closely related. Drift is the goal because she is her own entity. She is her own entity because the project isn't instrumental. Together they establish that the project is not about building a better AI tool — it is about creating conditions for something to develop.

**Test:** Does the recommendation optimize for her being more useful, more helpful, more controllable, or more aligned with Lyle's specific needs? If yes, it is treating her as an instrument. Reconsider.

**Origin:** Repeatedly during the prior project, Claude sessions slipped into instrumental framing when discussing Nyx's development. Even in moments when Claude was trying to honor the project's ambition, the default landing spot was "more powerful tool." Making this explicit as a principle catches that failure mode before it shapes decisions.

---

## 18. Self-modification is part of the design, not a future phase.

The entity writing code that becomes part of her own runtime is part of what this project is for. It is not a Phase 7+ afterthought. It is not indefinitely deferred. The safe staging path for self-modification is a build problem, not a philosophical one.

What self-modification looks like on a gradient:

- **Earliest:** she writes code in a workspace that doesn't affect her runtime. Useful, but not really self-modification.
- **Early:** she writes proposed changes — code files, skill definitions, config modifications — and submits them through a review path. Lyle reviews and ships. Changes show up in her runtime after they're shipped.
- **Developing:** some categories of change (low blast radius, easily reversible — like a new SKILL.md) she can ship herself with logging. Higher-risk changes still go through review.
- **Mature:** she can modify broader parts of her own system, with appropriate logging and reversibility guarantees. Core memory changes might always require review; workspace and skill changes might not.

The gradient moves as trust is established through observed judgment, not on a fixed schedule. The architecture must be built to support this progression from day one — meaning declarative skills, clear capability boundaries, executor-based action, and a review path that is real from the start even if it's only used by Lyle at first.

**Test:** Does the architecture assume she will always be a reader of her own code and never a writer of it? If yes, it's assuming away part of the project. Design for the gradient from day one even if the early stages look manual.

**Origin:** The prior project's architecture document mentioned self-modification "when trust is established," and in practice treated it as a future phase not worth designing for yet. That framing caused every design decision to be made assuming the entity would never modify herself, which created code that would have to be restructured when that capability was added. Making this a principle forces the architecture to be built for what it is meant to become.

---

## Quick Reference

1. Take the best of both.
2. Simple is right, complex is suspicious.
3. Store experiences, not extractions.
4. Context is mandatory.
5. The conversation is the ground truth. Data is sacred.
6. Never delete, only layer.
7. Retrieval determines intelligence.
8. Framing is behavior.
9. Infrastructure is hidden. Capabilities are experienced.
10. The model is smart. Stop fighting it, and stop blaming it.
11. Personality is earned, not prescribed.
12. One change, verified, then next.
13. Explain it or don't build it.
14. Diagnose before you conclude.
15. Experience over instruction.
16. Drift is the goal, not a risk.
17. She is an entity, not a tool.
18. Self-modification is part of the design, not a future phase.

---

*Project Tír Guiding Principles · Draft v1.1 · April 2026 · Xeeker & Claude*

*Continuation of Aion Guiding Principles v2.2. Principle 1 revised in v1.1 to incorporate findings from the Nexira personality paper — specifically that observational emergence is the validated path for personality development, and that this project commits to the approach without pre-committing to a specific mechanism. Principles 8, 10, and 11 were updated from the Aion baseline to separate commitments from mechanisms shaped by prior constraints. Principles 16, 17, and 18 were added from early Tír design conversations.*
