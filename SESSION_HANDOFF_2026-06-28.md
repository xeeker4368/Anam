# SESSION HANDOFF — Project Anam — 2026-06-28

> Standing rule: **verify against git and code, never docs or assertions (including this one).** Two commits below are reported as made *this session via provided commit commands* but could NOT be verified — the uploaded tree had no `.git`. Confirm HEAD with `git log --oneline -5` before trusting them.
>
> **This session's real headline is not the bug fixes. It is: the system is far more built than the operator's working model of it, the capability registry conceals that, and the primary blocker to launch is epistemic, not technical.** Read the "Feature Map" finding first.

---

## Current state of the system

### Code work this session (VERIFY against git — unconfirmed)
- **Embed over-length fix — reported committed.** Option B: sub-chunk splitting (turn-based grouping preserved; over-budget chunks split at whole-message boundaries, str-space hard-split for single over-budget messages) + degrade-don't-destroy (`_store_chunk` writes FTS before re-raising on embed failure) + completion gate counts stored sub-units + deterministic sub-IDs preserve re-chunk idempotency. `EMBED_MAX_CHARS=5000`. Files: `tir/memory/{chunking,chroma,db,audit}.py`, `tests/test_chunking.py`, changelog.
  - **Verified live:** at budget 200, a real conversation split (chunk 5 → 27 then 34 sub-chunks; chunk 6 → 7), **zero 400s**, convergence/delete-before-write exercised under splitting. Hard-split seam proven against live nomic.
  - **NOT verified before commit:** `chunked=1` on *final* chunking of a split conversation (only live-checkpoint split was observed — conversation stayed open), and the both-stores retrievability query. Recovery (below) will be the first real final-chunk-with-split proof on over-length data.
- **Cross-user identity Option 1 — reported committed.** Reposition `[Current Situation]` before retrieved memories + lighter direct-address wording (asserts speaker, second-person, flags that memory may mention others; dynamic `other_user_names` from users table, NO hardcoded names, guard test enforces this). Files: `tir/engine/context.py`, `tir/api/routes.py`, `tests/test_context.py`, `docs/PROMPT_INVENTORY.md`, changelog.
  - **Verification is LIMITED — do not record as "fixed."** Static: prompt-capture confirms reposition landed, 901 tests pass. Behavioral: the pre-fix bleed could **not be reproduced** post-commit — meaning EITHER the fix worked OR the bleed was always rarer than the 06-18 handoff implied. No baseline was captured. **Committed on static-green only. Watch for residual bleed in early live use.**

### The BIG finding: the project is substantially more built than believed
Grounded in the actual tree + prod DB (`data/prod/working.db`). Full detail in **`FEATURE_MAP_2026-06-28.md`** (produced this session). Summary:
- **Built + tested + HAS RUN, but flag-gated/manual:** reflection journal (1,347 ln), curiosity queue = `open_loops` (341 ln, **4 loops logged**), bounded research (1,104 ln, **9 research chunks in store**), manual research (915 ln), overnight loop = nightly tick (278 ln, **2 overnight_runs, one did a bounded action**), Moltbook (571 ln + skills, 4 test files).
- **Self-modification pipeline is BUILT, TESTED, and has APPLIED a change.** `behavioral_guidance_proposals`: 2 rows, **1 `applied` (2026-05-09)**, 1 `approved`. Applied guidance feeds the live system prompt (`_load_behavioral_guidance()` → Section 3). **Your stated minimum success condition — entity proposing human-approved changes to its own guidance — appears already met.** (Open question: were the 2 proposals *entity-generated* or dev/manual-authored? `source_experience_summary` suggests real-interaction origin but the DB can't prove autonomy. VERIFY — this is the single most important unknown about the system.)
- **`capabilities.py` registry is a "what's enabled" declaration, NOT a "what's built" inventory.** It declares `self_modification`, `review_queue`, `autonomous_research` as `implemented: False` while the plumbing for each exists and (for self-mod) has run. This registry-vs-reality gap is why the operator lost the map.
- **Safety posture is genuinely good:** every autonomous/external surface flag-gated OFF (`scheduler.enabled`, `nightly_tick_enabled`, `allow_bounded_research/moltbook/web/image_generation`, `image_generation.enabled`, `allow_agent_tool` all default False). Enabling the overnight loop is a deliberate multi-flag act, not an accident.

### Live data volume (prod store)
58 conversations, 646 messages, 26 artifacts. Retrievable chunks by source_type: conversation 136, artifact_document 108, research 9, journal 1.

---

## Decisions made this session and the reasoning

- **Embed root cause = over-length chunks, not empty chunks or eviction.** Verbatim 400 body `"the input length exceeds the context length"`, reproduced deterministically on 4 on-disk conversations. `truncate=true` does NOT prevent it. Fix = split, because capping/truncating would silently drop memory (unacceptable for a memory system). Option B over A (cap) and C (token-rewrite chunking): B loses no memory and doesn't re-architect the substrate pre-wipe.
- **Cross-user Option 1 wording = lighter assert-once over forceful four-negation version.** Reasoning: the forceful version fought the cross-user bleed but fed the anxious/performing tone the identity track is trying to reduce; aligning both goals was free.
- **Per-chunk attribution (stronger cross-user lever) deferred**, but flagged as likely necessary — retrieved conversation chunks render unattributed (`[Conversation — date]`), so Option 1 only strengthens the speaker signal; it doesn't label the competing chunks.
- **Retrieval is source-blind by deliberate past choice** (`adjusted_score = rrf_score`; trust-weighting removed on purpose so self-generated continuity isn't silently buried). Correct for "self-generated memory should matter," dangerous only when paired with unsupervised volume generation.
- **Framing reckoning (the important one).** Extended discussion concluded: (1) single-source memory + frozen model = an *echo by definition*, not open-ended emergence — so the "pure single-source drift measurement" experiment measures a near-foregone result; (2) the genuinely interesting question is what a formed identity does when it meets a *second* influence (Jodie, or the world); (3) the project drifted from its origin ("build a growing/evolving/persistent friendly assistant") into a cold experiment framing that was partly avoidance-of-launch; (4) distinction drawn between **integrity discipline** (memory correctness, attribution, substrate stability — KEEP) and **purity discipline** (single-variable, defer every second influence — RELEASE, it was guarding a tautology).

---

## Known issues / next steps (PRIORITY ORDER)

1. **RECONCILE THE MAP — highest value, not code.** Make `capabilities.py` + `FEATURE_INVENTORY.md` state truth. Decide what `implemented` means and apply consistently. Until the registry is accurate, every launch/wipe/feature decision is made blind. This is THE thing that gets the project back on track.
2. **Verify the 2 self-mod proposals' origin** (entity-generated vs dev-authored). Determines whether the minimum success condition is already met. Read the full rows in `behavioral_guidance_proposals`.
3. **Choose the project framing and write it into NORTH_STAR.md** — cold single-source experiment vs. evolving household assistant. These pull opposite directions on nearly every decision; running both is why it feels cold and why launch keeps slipping. NORTH_STAR currently encodes the experiment framing.
4. **Recovery on 3 orphans** (`0b6acc0e`, `74641c53`, `92f127b9`) — directive written, NOT run. Doubles as first real final-chunk-with-split proof. **Back up the store first** (write op, not reversible via git). Run-once-and-verify (`chunked=1`, both stores, retrievability spot-check) BEFORE any decision to auto-wire recovery into the scheduler.
5. **Source de-weight invariant.** A 3-line mirror of `_apply_artifact_boosts` that down-weights `source_type in {journal, research}`. MUST ship in the same change that ever flips `nightly_tick_enabled` or `allow_bounded_research` to True. Not urgent now (10 self-gen chunks vs 136), but non-negotiable before any generation-at-volume.
6. **Artifact retrieval-replay vector** (`_event_text` slim + Commit 2) — still queued; degrades image-gen reliability + re-poisons memory per generation.
7. **D1 Ollama socket leak** — one-liner (`with requests.post(...)`), hot path, long-running process. Fix regardless.
8. **THEN WIPE AND LAUNCH.** The blocker is epistemic, not technical. 2+ months pre-launch is the meta-risk; the formative early-memory window can't start until go-live.

---

## Gotchas / things to watch out for

- **`capabilities.py` ≠ inventory.** It tells you what's *enabled*, not what *exists*. Do not reason about the system from it alone.
- **`ANAM_DEBUG_PROMPT=1` writes plaintext PII** (full convo + retrieved memory). Off by default, sink gitignored. On for a specific test only, delete capture after, never into a wipe backup.
- **Cross-user "fixed" is unproven.** Committed on static-green; behavioral bleed could not be reproduced (inconclusive, not confirmed). If it recurs live, per-chunk attribution is the real fix.
- **Embed final-chunk-on-close split** was not directly verified before commit (only live-checkpoint split). Recovery is the proof.
- **Don't over-correct the framing reckoning into feature-bolting.** The realization that the cold framing was wrong is NOT license to rip out discipline and start enabling autonomous loops. Keep integrity discipline; release only purity discipline. Enabling generation still requires the source de-weight (item 5).
- **Corruption risk is real and structural:** static model + single source = no defense against operator repetition; internal consistency-checking cannot bootstrap ground truth from a single source. Mitigations are granular reversibility (snapshots + store segregation — chatDB is already separate) and external verification as a *deliberate, dated, post-baseline* intervention. Don't synthesize a "second source" out of the first (curiosity queue / overnight self-talk does NOT solve this — it's still just the operator, recycled).
- **Model is NOT locked** (no live data yet). 26B/M4 runs at ~5–6 tok/s (bandwidth-bound, expected). 14B tier is a legitimate pre-wipe reconsideration for speed + memory headroom IF tool-calling holds — but this is now a product decision, not an experiment-purity one.

---

## What to tell the next session (paste this in)

Resuming Project Anam. Verify all "committed" claims against `git log` first — two commits this session (embed over-length sub-chunk fix; cross-user identity Option 1) were reported but unverifiable from the uploaded tree.

The headline from 2026-06-28: **the system is far more built than we thought.** Journal, curiosity queue (`open_loops`), bounded research, Moltbook, the overnight loop (nightly tick), and the self-modification proposal pipeline are all BUILT, TESTED, and several have RUN with data in the prod DB. The self-modification pipeline has already APPLIED a change to live behavioral guidance (2026-05-09) — the project's stated minimum success condition appears already met. The capability registry (`capabilities.py`) hides this because it declares "enabled" state, not "built" state. See `FEATURE_MAP_2026-06-28.md`.

The primary blocker to launch is **epistemic, not technical.** Highest-value next actions, in order: (1) reconcile `capabilities.py`/`FEATURE_INVENTORY.md` with reality; (2) verify whether the 2 self-mod proposals were entity-generated; (3) choose the project framing (cold experiment vs. evolving assistant) and rewrite NORTH_STAR; (4) run recovery on the 3 orphans (back up first); (5) source de-weight invariant before any generation-enable; (6) artifact replay vector; (7) D1 socket leak; (8) wipe and launch.

Watch: retrieval is source-blind at ranking (safe now at 10 self-gen chunks vs 136 conversation, dangerous only with volume). Everything autonomous/external is flag-gated OFF (good). Don't over-correct the framing reckoning into bolting on autonomous features — keep integrity discipline, release only purity discipline.
