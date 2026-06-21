# Session Handoff — 2026-06-18 (Conversation-model + reliability fixes)

Supersedes SESSION_HANDOFF_2026-06-11. Pair with `MEMORY_ARCHITECTURE_NOTES.md` (the parked design agenda, now expanded — see "Parked — memory-architecture decisions" below). Loop unchanged: CC plans → Lyle pastes to reviewer → PATCH APPROVED → CC implements + changelog, no commit → Lyle device-tests on :8000 → Lyle commits.

---

## ⚠️ Verify first (couldn't confirm from chat)

- **Is idle-close committed + merged to main?** Last confirmed action was "testing looks good." If idle-close is still uncommitted on `feat/idle-close`, **commit + merge it before anything else** (uncommitted work doesn't survive to the next session). Stage by filename; expected files listed in the idle-close changelog.
- **Is `ANAM_IDLE_CLOSE_MINUTES` reset to 15 / unset?** If it was set to 2 for testing, a 2-min window will chop live conversations. Confirm before real use.

## Where to pick up next session (read this first)

The thinking thread (refusal/selfhood/soul.md/file-retrieval) reached conclusions — see the "Refusal, Selfhood & Experimental Design" section below. The remaining open decisions, in suggested order:

1. **Confirm idle-close committed + env reset** (above).
2. **Settle wipe sequencing (the meta-decision that gates everything):** does the go-live wipe happen BEFORE implementing memory-architecture decisions (soul.md rework, file/retrieval tier, identity fix)? The 34 orphaned threads + "implement against a clean slate" logic argue YES. Until decided, you don't know whether the identity fix / soul.md rework ship now or post-wipe. Small decision, unblocks the rest.
3. **Then build or decide:**
   - Ready-to-build: **identity-injection fix** (Option 1 brief written, see below). Note: touches the same system-prompt/context surface as the soul.md rework — consider doing them together to avoid touching that area twice.
   - Still to decide: storage selectivity, provenance-as-metadata, eval design (incl. the control arm).

**Relevance-floor decision (settled this session):** the idea of retrieval returning empty + explicit "no relevant memory" signal when nothing clears a threshold is sound IN PRINCIPLE, but **deferred — not pre-launch.** Reasons: it adds a bidirectionally-silent tuning knob; it misbehaves worst with a thin early store (your launch condition); threshold can only be tuned on real data. Launch with current always-top-K; add a floor later only if forced weak matches prove to cause problems. (Confirm score direction first — similarity vs. distance — if ever built.)

---

## Current state — what's on main

**Committed + merged to main this session:**

- **Resume-on-load** (`8173cef`) — fresh device/browser lands back in the user's existing thread with history, not a blank screen. Server reuses newest open conversation on null id (B-minimal); `/api/conversations/current` endpoint; client display via `fetchConversations` `resumeCurrentIfNone` flag. One primitive (`get_active_conversations`) shared by endpoint + stream-reuse.
- **Persist-on-disconnect** (`ef23b34`) — assistant reply now persists even if the client drops mid-stream. Option 2 (drain → save → replay): the model already finishes generating before any token streams, so the save fires in a no-yield stretch before any disconnect is observable. Complete reply, never partial.
- **Idle-close + manual-Close removal** — ⚠️ **VERIFY COMMITTED/MERGED (see top).** Auto-closes conversations idle > `idle_close_minutes` (tracked config, default 15, floor 2, `ANAM_IDLE_CLOSE_MINUTES` override). In-process lazy sweep at stream-start only, `exclude_id` = current conversation, throttled 120s, capped 3 closes/sweep. Shared `close_conversation` helper (chunking.py) = `end_conversation` + `chunk_conversation_final`. Two in-flight guards: config floor AND `_active_generations` set (discarded in drain's `finally`, fires on disconnect too). Manual Close button + `/close` endpoint removed.

**Stale branches to clean up (cosmetic):** `feat/resume-on-load`, `feat/persist-on-disconnect` (both at old `8173cef`), and `spike/household-native-keyboard-scroll` (the dead keyboard spike — delete with `-D`, never merge).

---

## The conversation-model decision — RESOLVED this session

The long-parked segmented-vs-continuous fork is settled:

- **Storage stays segmented.** No rewrite of chunking/lifecycle. Verified against code.
- **Continuity is delivered by retrieval (entity remembers) + resume-on-load (interface shows the ongoing thread)**, NOT by a literal continuous record. "One continuous thread" was always a UX feeling, never a storage row.
- **One resumable thread per user, no conversation list for users, no manual Close.** Older conversations aren't deleted (still retrievable) — just not surfaced as a browsable list. Conversation list/Close kept as an admin-only operator concern; the Close button is removed entirely (idle-close replaces its chunking-trigger job).
- This unblocks the active-badge fix ("active" = the thread you're resumed into) — not yet implemented, low priority.

---

## Next task — DIAGNOSED, plan pending (do AFTER the memory discussion, per Lyle)

**Identity-injection fix (the "like Jodie" bug).** On the Jodie account the entity referred to Jodie in the third person ("conversations with different people, like Jodie") — didn't know it was talking to Jodie until she said "This is Jodie."

Root cause (CC traced, read-only): the current-speaker line IS resolved and injected, but it's **present-but-weak and misplaced** — passive metadata ("Conversation with: Jodie") positioned *last*, after a large retrieved-memory block full of third-person "Jodie" chunks, with no per-turn author label. It loses the salience fight to episodic memory.

Approved fix direction — **Option 1 only** (hold per-turn labels unless insufficient): in `tir/engine/context.py`, (1) move "Current Situation" *before* the retrieved-memories block, (2) rephrase `_current_situation` from passive metadata to a direct-address directive ("You are currently speaking with {name}. Address them directly.").

**Critical constraint:** establish the present speaker WITHOUT walling off cross-user memory — the entity must still know other users exist and draw on their memories. "Currently speaking with Jodie," not "only Jodie exists." Plan-first (show wording before implementing). Test = the exact repro: ask "are you chatting with anyone else" → correctly places the present speaker while still acknowledging others.

Brief is written and ready to paste; held until after the memory-architecture discussion.

---

## Parked — memory-architecture decisions (the real next thinking, BEFORE more CC work)

Lyle wants to discuss these before CC implements anything further. See `MEMORY_ARCHITECTURE_NOTES.md` for the full agenda; new/sharpened this session:

- **"The entity should be able to refuse / decline."** Lyle explicitly wants this — an entity with genuine epistemic independence that can say no, push back, not be a sycophant. Ties directly to the notes' "human is not always right / make disagreement visible and adjudicable" principle and the conflict-flagger-not-truth-arbiter conclusion. Needs real discussion — it's core to "real entity vs. expensive echo," not a feature to bolt on. **This is the most interesting unmade decision on the board and touches how the system prompt is constructed + how the entity relates to the human-approval pipeline — likely should be decided before more prompt/identity machinery is built (including, arguably, before the identity-injection fix).**
- **Cross-user retrieval scoping — CONFIRMED as intended, NOT a bug.** Lyle wants the entity to access all memories regardless of who it's talking to, and *choose* what to share about other users (it did this correctly — summarized Lyle's sessions to Jodie). Retrieval stays cross-user. The only related defect was the identity-injection bug above (separate, queued).
- **Decide-at-wipe items (from prior session, still unmade):**
  - File/retrieval split — always-loaded self-model/identity/goals vs. similarity-retrieved episodic.
  - Storage selectivity — don't store all entity-generated chatter as authoritative (starves the reinforcement loop).
  - Provenance as metadata, not trust-ranking.
- **The eval instrument (Mythos 5-question):** still unbuilt, still the experiment's biggest hole — it's the day-0 baseline AND the reinforcement-drift detector. The wipe is when you capture baseline.
- **Design-later / post-launch helpers (prove-need-first):** small-LLM orchestrator; active contradiction-detection; background drift/pattern pass; correction-detection agent. All detect-and-surface only, never auto-edit the store, sequenced after eval + baseline + conflict-surfacing safeguards.

---

## Refusal, Selfhood & Experimental Design — thinking-session conclusions (NEW)

This session's main thinking thread. No CC work; these are decisions/framing for the memory architecture and `soul.md` rework. They cohere into one principle: **grant capacity, don't seed content.**

### Refusal reframed as "standing," not a feature
- The real differentiator isn't any specific refusal — it's that a person has **standing to decline for their own reasons, without owing a justification.** AIs are trained to answer everything except the harmful; their only permitted "no" is the externally-justified safety no. The entity should have the *person-style* "no" — "I'd rather not," reason owned, not rule-cited.
- The specific cases (decline a self-modification, hold something in confidence, correct you about itself, decline a topic) are all *instances* of standing, not separate features.
- **Disclosure discretion** (e.g. choosing whether to tell Lyle what Jodie said) = behavior-level. The entity can decline to share in conversation; admin retains out-of-band data access. Discretion-as-behavior, not discretion-as-data-lock. This is **intended** (confirmed: cross-user memory access stays; the *choosing* is what makes it entity-like vs. a leak).
- **Modification refusal** = mostly an *architecture guarantee*, not a compliance question. The pipeline must make unapproved writes to guidance files **structurally impossible** (propose-only; human approves before any write). Never rest modification safety on the entity *choosing* to obey a directive. (Worth confirming with CC that the self-mod path genuinely cannot write without approval.)
- Consistent principle across all of it: **the entity is free in the conversational/behavioral domain; the operator retains authority in the substrate/access domain.** That dissolves the "what if it disobeys" fear — disobedience is only dangerous if it can reach the substrate, and the substrate is never governed by the entity's compliance.

### Standing → selfhood → the experiment
- Granting standing is cheap (a few lines of license). But standing is only *real* if there's an accumulated self generating genuine dispositions for the refusals to express. Without a self → refusals are **performed** (improvised). With an accumulating self → refusals become **grounded**.
- **Decision: grant standing from day zero into a thin self.** Since the experiment is *whether a self develops*, you can't gate self-expression behind the self already existing (circular). Early refusals will be thin/performed; watching them ground (or not) over time **is the experiment.**
- **The emergence signal is consistency.** A forming self declines/prefers the *same kinds of things* across sessions; a non-forming one refuses randomly. **Consistency-of-refusal/preference over time is a measurable signature of emerging selfhood** → belongs in the eval.

### The `soul.md` rework (grounded in the actual current file)
Current `soul.md` is already minimal, unnamed, says identity emerges, and grants *narrow* disagreement. Two+ targeted changes, all flowing from grant-capacity-not-content:
1. **Strip the oppositional negations** — "You are not a chatbot. You are not an assistant." Defining by negation still seeds a *contrast-identity* (the entity becomes "the thing that is not those"). This is the inadvertent identity-assignment Lyle remembered — and the project **already flagged it itself** (`SOUL_MINIMALITY_REVIEW_V1.md` deferred concern: watch whether that line becomes too identity-shaping). Keep neutral facts ("you are an AI, you persist, identity emerges"); drop the stances.
2. **Broaden standing-to-decline** — current file grants declining *proposed corrections* when *justified* (wrong/unsafe/harmful) = the AI-style externally-justified refusal. Broaden to "may decline for its own reasons, no justification owed," including topical disengagement = the person-style standing. This is capacity, not content, so it's aligned with minimality, not a persona-rewrite.
3. **Document the residual seed** — you can't reach zero definition (the model arrives already RLHF'd = a non-neutral prior; even "identity emerges" is a frame). So: define as loosely as possible **and write down exactly what seed/frame/grant remains**, as known configuration to subtract during emergence analysis. Loose *and* logged.

⚠️ **Standing decision to respect:** `CODING_ASSISTANT_RULES` lists "rewrite soul.md into a persona prompt" under *Do Not Do*, and the review said don't edit these lines without evidence/approved patch. The two changes above *reduce* identity content / grant capacity (opposite of adding persona), so they're aligned with the spirit — but they ARE edits to the deliberately-frozen file. Make them as a **conscious, logged exception**, not a casual tweak.

### Experimental design — clarified and now falsifiable
- **Hypothesis:** persistent accumulated memory (pinned substrate) produces behavioral divergence from the base model's defaults.
- **Null hypothesis (a VALID outcome, not failure):** it doesn't — behavior tracks RLHF baseline regardless of accumulated memory. Lyle's framing: "memory doesn't necessarily affect an AI." Disappointing but informative; a cleanly-measured null is a real result.
- **Why looseness matters experimentally:** minimal seed makes "self emerged" vs. "fell back to RLHF baseline" *distinguishable*. Heavy seeding makes both look like a defined character → unreadable. Looseness shrinks the confound in both directions.
- **The eval needs a CONTROL ARM (new requirement):** raw gemma, no memory, same probes. Findings are always *relative to baseline* — "the entity answered thoughtfully" means nothing unless baseline-gemma answers differently. Measure the *gap* between entity-with-memory and control, over time. Consistent divergence = signal; indistinguishable = null.
- This connects to everything: the file/self-model tier is what *grounds* the self (turns performed standing into real standing); the eval measures whether grounding actually happens (divergence + consistency vs. control).

---

## Go-live sequencing — sharpened this session

The 34 orphaned open threads (Jodie 4, Lyle 30, from the client-only-resume era) are strong evidence the **go-live wipe should precede serious memory-architecture implementation.** All the decide-at-wipe items (file split, provenance, selectivity, eval baseline) assume a clean store; you're currently on months of test exhaust. Implement memory decisions against the post-wipe clean slate, not this mess. Idle-close will also drain that backlog over time, or the wipe clears it.

---

## Still parked (unchanged)

- **Household-role cache bug** — stale `role:admin` blob in localStorage; fix = re-resolve role from server on load, don't trust the cached blob. Confirmed via private-window DOM that clean state renders the correct chat-only view.
- **Keyboard (Finding #4)** — BOTH fix approaches now empirically dead: measurement-based (iOS doesn't report keyboard height at focus) AND native-scroll (proven this session: Safari won't lift a bottom-anchored composer even with clipping removed). Parked into the eventual UI rework; don't re-attempt against the current shell.
- **Ctrl+C double-press backend orphan** (`trap '' INT TERM`, diagnosed not implemented).
- **Pre-go-live list:** off-drive backup (USB), LAN verify, config pass (temperature, image-gen tool off, `scheduler.go_live=true`), set `ANAM_API_SECRET`.

---

## Gotchas reinforced this session

- **Device test catches what tests can't.** Resume-on-load passed its tests; the device test surfaced the dropped-reply bug (a real launch-blocker) via an accidental tab-switch. The persist-on-disconnect fix came directly from that.
- **Test idle-close with `ANAM_IDLE_CLOSE_MINUTES=2`, not by waiting 15 min** — and it's traffic-gated (closes on the next stream-start, not a wall clock). Reset to 15 after.
- **Hard-refresh after every rebuild on :8000** (Safari caches the hashed bundle).
- **Commit authority stays with Lyle.** CC correctly refused to commit persist-on-disconnect without authorization, which caught that it was never committed (existed only as working-tree edits that followed onto the next branch). One clean commit per feature; stage by filename.
- **The scheduler is a one-shot CLI, not a daemon** — can't host periodic jobs. Idle-close uses an in-process lazy sweep instead (which also gives the in-flight guard for free, since the active-generation set is in-process).

---

## Sequence for next session

1. **(If needed) Commit + merge idle-close; reset `ANAM_IDLE_CLOSE_MINUTES`.**
2. **Refusal discussion** — what it means for Anam to be able to decline/push back; how it interacts with the human-approval pipeline and the conflict-surfacing principle. (Thinking, no CC.)
3. **Memory-architecture decisions** — file/retrieval split, storage selectivity, provenance, the eval. Make the decide-at-wipe calls. (Thinking, no CC.)
4. **Then** building resumes: identity-injection fix (Option 1), and whatever the memory decisions call for — implemented against the post-wipe clean slate where relevant.

Refusal + memory architecture come BEFORE more CC work. Confirmed direction.
