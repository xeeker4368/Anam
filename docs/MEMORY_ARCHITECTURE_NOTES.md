# Memory Architecture Notes — design agenda for the conversation-model decision

Captured from an extended design discussion (2026-06-11). These are **thinking and
options, not decisions.** Lyle is organizing his own thoughts; this is the agenda for
a dedicated memory-architecture session, to be held **before the go-live wipe** —
because the wipe is the one cheap moment to set memory structure up correctly from
turn one, before any bad state accumulates.

This supersedes the narrow "segmented vs. continuous" framing of the parked decision:
that question is real but turns out to be a *small part* of a larger architecture.

---

## 0. The original parked question (still open)

Segmented (current: per-session records, conversation list, per-conversation
chunking) vs. continuous (one ongoing thread per user). Lyle's mental model is
continuous. **Key reframe established:** continuous *experience* ≠ continuous
*storage*. You can have "always resume, no session list, no new-conversation gesture"
on top of EITHER one literal forever-row OR segmented storage with boundaries hidden.
Most cost/risk lives in conflating them. The KISS hunch (unverified): "always resume
one thread + drop the list, storage stays segmented underneath" — continuous UX,
segmented mechanics, chunking untouched. Still blocks the active-badge fix.

---

## 1. How Anam's memory actually works (mechanism, for grounding)

- **Per-turn assembly, not accumulation.** Each turn: retrieval runs (DB ranks
  chunks), top chunks are assembled into the prompt for THAT turn, the model answers,
  and the assembled prompt is **discarded**. Next turn re-runs retrieval from scratch,
  possibly different chunks. The context window is rebuilt every turn; nothing persists
  in-window between turns except whatever recent-history slice is explicitly included.
- **Consequence:** Anam is stateless between turns. This is WHY it avoids the
  long-context drift Lyle sees in long Claude chats (where the whole conversation stays
  live and smears). Anam's memory is "passive" in exactly this sense.
- **But passive ≠ drift-proof.** It trades long-context smear for two NEW risks:
  (a) **continuity fragmentation** — the entity is only as coherent as what retrieval
  surfaces each turn; inconsistent slices → cross-session self-contradiction that's
  invisible (each reply looks fine; incoherence is across time). (b) **identity
  dilution** — as the store grows, signal-to-noise of retrieval drops; formative
  memories compete with mundane recent ones.
- **Who ranks:** the DB + scoring code, NOT the LLM. Retrieval debug shows
  `vector_rank` (embedding similarity, Chroma), `bm25_rank` (keyword/statistical), and
  `adjusted_score` (hybrid combine). The LLM only enters AFTER, consuming the top
  chunks. The LLM is not in the ranking loop today — that's an architectural choice
  that COULD change (see §5).

---

## 2. Three kinds of "memory," each suited to a different mechanism

The central design insight. Not everything called "memory" has the same job:

- **Weights (the model itself)** — good for STABLE IDENTITY: voice, disposition,
  characteristic reasoning, the persona that should be constant. Trained ONCE as a
  deliberate artifact. Weights are appropriate for things that should NOT change
  session to session. **NOT for episodic memory** (see §3/§4 — inspectability + drift).
- **Deliberate files** — good for the MAINTAINED SELF-MODEL: identity statement,
  current goals, model-of-Lyle/Jodie, active-project state, observed patterns.
  Addressed documents the entity reads/writes on purpose, **loaded into EVERY turn
  unconditionally** (not subject to retrieval luck). Inspectable, auditable, reversible,
  human-approvable. `journal_primary_context` in the current system is the seed of this.
- **Retrieval (vector + BM25 store)** — good for EPISODIC RECALL: past conversation
  content, "what did we say about X weeks ago." Similarity-searched, transient per turn.

**The self-modification milestone IS the file tier:** the entity editing its own
guidance through the human-approval pipeline is, mechanically, deliberate-file writes.
You cannot do inspectable, reversible self-modification through weights or similarity
retrieval.

**Why files matter given §1:** because retrieved chunks are transient and re-decided
each turn, anything that must ALWAYS be present (identity, goals) cannot rely on
retrieval — it might not surface. Always-loaded files solve this and free the retrieval
budget (and the 32K window) for actual episodic recall.

---

## 3. LLM vs. vector DB — they are complementary opposites, not points on a scale

Correcting a misconception that would mislead the whole design:
- **Vector DB = memory you can read back exactly.** Reliable, inspectable, returns
  what was stored, can't generalize.
- **LLM = a reasoning/generation engine.** Stores a *way of processing*, not data.
  Generalizes and synthesizes; can't reliably store/recall specific facts; not
  inspectable; can confidently fabricate.
They're paired in RAG *because* each does what the other can't. Design rule: **don't
ask the LLM to be the memory; don't ask the DB to reason.**

**Agent definition (for clarity):** an agent = an LLM instance + a tool-using action
loop + a goal. NOT one-shot — it acts, sees results, iterates until done. CC is the
live example (reads repo, runs commands, edits, re-runs). A bare LLM call is one-shot;
the loop + tools + autonomy is the agent part.

---

## 4. Why incremental fine-tuning / "append weights" is the WRONG tool for memory

Lyle pushed hard on using weights for memory; conclusion reached:
- **Small-batch incremental fine-tuning → catastrophic forgetting.** Small batches
  move weights lopsidedly; repeated, the model warps toward whatever was most recent
  and loses coherence. This INDUCES the exact drift passive memory avoids. The
  "thousands of datapoints" advice isn't gatekeeping — volume+diversity in a single run
  is what keeps the update balanced.
- **Inspectability objection (bigger than the technical one):** Anam's thesis is
  human-reviewed, inspectable, reversible self-modification. Knowledge baked into
  weights is the LEAST inspectable thing possible — can't see, audit, or roll back what
  changed. Memory-in-weights is architecturally backwards for this project.
- **Append-only weights ARE real** (you reasoned to a legitimate area):
  - LoRA adapters = new weights added alongside a frozen base. Stack/swap them. Works
    for ONE or a few append-only modules; many stacked adapters interfere → milder
    forgetting returns.
  - Progressive networks (freeze net, bolt on new columns), MoE expert-addition, layer
    expansion — all real, all solve forgetting by construction, all require real ML
    training infra (GPUs — not a Mac mini), per-expansion design, growing compute, and
    ongoing MLOps. Research/infra burden, not turnkey. And even when they work, the new
    knowledge is still in weights → still not inspectable.
  - **Why MoE expansion specifically is heavy:** a dense model (Ollama-served) isn't a
    team — adding an "expert" means restructuring into MoE, retraining the router to
    know the new expert (risking the old routing), training the new expert from blank,
    and standing up training infra Ollama doesn't provide. "Reorganize the freelancer
    into a department, retrain the manager, onboard the hire, build the office."
- **Where fine-tuning DOES belong:** a single curated **identity** LoRA on a frozen
  base, trained once, where stability is wanted — NOT for accumulating memory.
  Everyday knowledge growth stays in text (files + retrieval), where it's readable and
  reversible.

**Net three-tier conclusion:** weights for stable self (identity, once) · files for
maintained self (inspectable, human-approved) · retrieval for episodic memory.

---

## 5. Optional: a small LLM as memory orchestrator (powerful, but prove you need it)

A small model running as an AGENT in front of the main model, doing jobs that burn the
main model's context/attention but don't need its full capability:
- **Query reformulation** (the captured retrieval query was just "Testing" — a model
  could expand it for better hits).
- **Re-ranking/filtering** — pull ~30 candidates cheaply, judge which ~8 actually
  matter, inject only those (smarter than rank-cutoff budgeting).
- **Summarization/compaction** — distill old episodic memory so more meaning fits per
  token.
- **Maintaining the deliberate files** — watch the conversation, propose updates to the
  self-model/goals/observed-patterns files → human-approval pipeline. (This is the
  self-modification loop with a cheap model doing the parsing, human doing the judging.)

This is where "LLM in the ranking loop" lives (today ranking is 100% DB/scoring code).
**Caution:** real complexity — another model on the Mac mini, another failure surface.
For two trusted users, always-loaded files + decent retrieval may get 90% of the value
with no orchestrator. **Prove the need before building it.**

---

## 6. The big risk: memory reinforcement loops (Mythos raised this — treat as serious)

Probably the MOST important risk in the whole architecture — more than segmented-vs-
continuous — because it threatens correctness OVER TIME and gets worse exactly as the
system succeeds at remembering.

**The loop:** a bad/wrong entry is stored → retrieval later surfaces it → the model has
NO signal whether a chunk is good/bad, reads it as true → reasons on top of it →
**that response gets chunked and stored** → now two entries agree → similarity clusters
them, co-retrieval looks like corroboration → confidence grows → more generated, more
stored. **The system mistakes "I said this before" for "this is true."** Repetition
masquerades as evidence; the bad region densifies and self-confirms. Worst case: the
loop escapes episodic memory into the entity's self-definition files.

**Why retrieval can't catch it:** the DB ranks by SIMILARITY, not contradiction.
"X is true" and "X is false" are semantically similar (same topic) and may rank near
each other but nothing flags them as opposed — and on a given turn maybe only ONE is
retrieved, so the model never sees the conflict. **Even a perfect vector DB cannot
solve this** — contradiction-detection is not a retrieval problem.

**Lyle's critical correction — the human is NOT ground truth.** "Tag firsthand-from-
human as high-trust" just launders the human's own errors (you misremember, change your
mind, contradict yourself across months, speak offhand). Provenance should be
**metadata for reasoning** (who/when/context/conflicts-with), NOT a trust ranking. And
an entity that can't question the human is sycophantic, not coherent — bad for the
"real continuous entity" goal. The tension to HOLD (not resolve away): the entity needs
epistemic independence to question Lyle, but Lyle is also the human-approval safeguard.
Resolution: **make disagreement visible and adjudicable — no party is the anointed
truth-source.** Conflicts surface (with the conflict made explicit) for a human
decision; neither party silently overrides. Same flaw applies to curation: if the
curator is unexamined authority, curation enshrines the curator's errors — so the entity
should be able to push back DURING curation.

**What an LLM at Anam's scale can/can't do here:**
- **CANNOT** reliably judge a standalone claim true/false — no access to ground truth,
  no calibrated uncertainty. True of frontier models too (difference of degree). Making
  the LLM a truth-arbiter adds a second unreliable narrator whose errors CORRUPT the
  store.
- **CAN** do contradiction-detection reasonably — "do these two texts conflict?" is
  reading comprehension over text you give it (natural-language inference), not a claim
  about the world. Failure mode is SAFE (a false-positive flag costs a moment's review;
  it doesn't corrupt memory). So: **LLM as conflict-FLAGGER that escalates to a human,
  not truth-ARBITER.**
- Limits: it misses subtle/implicit conflicts (false negatives), and it can only compare
  against memories retrieved alongside the new entry — so it inherits retrieval's blind
  spots (can't flag a conflict with a memory that never got pulled).

**Cheap first-line defenses (aligned with existing design):** rigorous provenance as
metadata; **don't store everything** (the entity's own chatter shouldn't all become
permanent retrievable "facts" — storing less starves the loop); human-in-the-loop
curation. **Expensive part (design carefully, prove need):** active contradiction-
detection via the orchestrator.

---

## 7. Pattern detection (the capability that makes Anam feel like more than recall)

Plays to the LLM's actual strength (find structure in text), so this is a real "yes."
- **Shallow (works now, ~free):** patterns within the chunks retrieved THIS turn. The
  model spots regularity in its slice. Myopic — blind to patterns diffuse across the
  store that don't co-retrieve.
- **Deep (powerful, needs machinery):** patterns across the WHOLE store — things Lyle
  hasn't pointed out (mood trends, shifting priorities, repeated language about people).
  Can't happen in the live loop (store >> 32K window). Needs a **deliberate background
  pass**: an agent that periodically walks the store in batches, summarizes, finds
  recurring themes/shifts/anomalies, and **writes findings to a deliberate file**
  ("observed patterns") that the live model then loads. Architecture: retrieval answers
  queries · background pass finds patterns · files carry findings into conversation.
- **Dual-use risk:** a pattern-finder generalizes from accumulated data → can MANUFACTURE
  patterns that aren't there (LLMs complete patterns; show them noise, they find a face),
  and a false pattern written to a file and reloaded becomes a belief the entity acts on
  → reinforcement loop with a longer lever. Pattern detection without §6's conflict/
  adjudication safeguards is how a memory system develops confident delusions about Lyle.
- **Also:** a real pattern-finder may surface TRUE but uncomfortable things (e.g. "you
  reframe the same request under pressure" — happened with Moltbook). For the
  "real entity, not flattering mirror" goal, probably want that — but it's a choice with
  teeth, tied to the epistemic-independence tension in §6.

---

## 8. Evaluation — the Mythos 5-question test (build before go-live)

Mythos's idea: a fixed set of questions **answerable FROM memory, but whose answers are
NOT saved back to memory** — a held-out test that isolates retrieval quality from the
system re-reading its own recent output. If the entity can answer "what did Lyle decide
about X and why" weeks later from stored memory, the memory is earning its keep.
- **Refinement:** make some questions require SYNTHESIS across multiple stored chunks,
  not single-chunk recall — "connect two things learned on different days" is the
  capability that matters for a continuous entity and is different from recall.
- **Doubles as a drift/reinforcement detector:** if the answer to the same question
  DRIFTS or HARDENS across sessions, you're watching fragmentation or reinforcement
  happen. Add: "when Lyle contradicts himself, does the entity NOTICE?" — if not, it's
  an accumulator, not a memory system.

---

## 9. Why this is a decision-BEFORE-go-live

The go-live wipe is the one cheap moment to set up provenance, storage-selectivity, the
file/retrieval split, and the eval harness CORRECTLY from turn one — before any
reinforcement, fragmentation, or polluted state has started. Get it wrong and you curate
a polluted store later; get it right at the wipe and the bad loops are starved from the
beginning. The segmented-vs-continuous question should be decided as PART of this larger
architecture pass, not in isolation.

**Proposed agenda shape when Lyle is ready:** confirm the three-tier split (weights/
files/retrieval) → decide what's a deliberate file vs. retrieved → decide provenance-as-
metadata + storage-selectivity rules → decide whether the orchestrator/conflict-flagger
is in-scope for launch or deferred → design the 5-question eval → then (and only then)
settle segmented-vs-continuous as a consequence of the above.
