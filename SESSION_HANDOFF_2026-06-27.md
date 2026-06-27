# SESSION HANDOFF — Project Anam — 2026-06-27

> Standing rule, learned the hard way again this session: **verify against git and code, never docs.** Every "committed" claim below carries a commit hash. If a claim has no hash, treat it as unverified. The previous handoff asserted things were "committed and pushed" that were not — do not repeat that.

---

## Current state of the system (verified against git)

**Branch `main`, all of the following committed AND pushed to `origin/main` (HEAD = `bbf0ccc`):**

- `6f632b0` — Agent loop surfaces tool failures honestly (read inner `ok`, frame failures for model). *(Pre-existing; the prior handoff wrongly called this uncommitted.)*
- `a8d956b` — Log a WARNING when a tool fails (agent loop + prefetch). **Task 1.**
- `b571eb5` — Render generated-image cards from real tool results (Chat Media Tool Result Rendering v1). **Task 2 Commit 1.**
- `87d9775` — Add opt-in prompt + tool I/O debug capture (`ANAM_DEBUG_PROMPT`). **Task 3 Part B.**
- `bbf0ccc` — Document retrieval-replay vector findings. **Task 3 Part A (verify-only).**

Plus earlier (this session confirmed in history, not re-touched): `NORTH_STAR.md` IS tracked and in history (`git ls-files` confirmed); the image-gen default-dimensions patch IS committed (`config/defaults.toml`, `comfyui.py`, `image_generation.py`, `test_image_generation.py`). **The prior handoff's "North Star not committed / image-gen staged-not-committed" exposure is CLOSED.**

Working tree at session end: clean except one untracked file — `PLAN-2026-06-25-artifact-cards-from-real-results.md` (CC's plan doc; undecided — commit as docs or delete).

**Running build note:** device-tested live on `:8000` after a fresh server start (`2026-06-26 ~18:44`, later `20:08`). Full model is Gemma 4 (`gemma4:26b`), warm. ComfyUI runs via `./start.sh --with-comfyui`.

---

## What got VERIFIED LIVE this session (not just tested)

1. **Task 1 (tool-failure honesty + WARNING) — WORKS LIVE.** Proven by a real SearXNG failure: `WARNING: tool 'web_search' failed; error=SearXNG returned HTTP 403`, and the entity reported the failure instead of confabulating success. Tool-agnostic (fired on `web_search`, not just image).

2. **Task 2 Commit 1 (cards from real results) — WORKS LIVE.** Confirmed on screen: model-authored `[Artifact source: ...]` blocks — both an invented one (`deadbeef`) and one carrying a REAL artifact ID (`00007`) — render as **plain text, no card.** Only a real `tool_result`/`selection` event produces a card. Fail-safe-empty holds.

3. **IMAGE GENERATION WORKS ON CURRENT CODE.** A novel request ("brass diving helmet on a velvet chair") dispatched `image_generate`, ComfyUI executed, a real card rendered (`anam_generated_00010_`, seed `3189134`). **Do not let anyone "rediscover" generation as broken — it is not.**

4. **Task 3 Part A vector — CONFIRMED end-to-end against the live DB** (`bbf0ccc` / `CODE_REVIEW_2026-06-26-retrieval-replay-vector.md`).

---

## THE CENTRAL FINDING THIS SESSION (the through-line)

**Image generation is NOT broken. Its reliability is gated by the retrieval-replay vector.** The model generates for real when context is clean, and authors a fake/replayed artifact block (with `tool_call_count: 0`, no dispatch) when its context is saturated with prior artifact blocks.

Mechanism, now confirmed in the actual prompt via `ANAM_DEBUG_PROMPT=1`:
- `artifact_indexing.py::_event_text` indexes every generation as a **full verbatim `[Artifact source: ...]` block** (real ID, path, SHA, prompt, seed) — dual-indexed (Chroma + FTS).
- `context.py:292–308` injects those blocks **verbatim** into the model-visible prompt on topical match.
- When the prompt fills with these blocks, the in-context pattern "image request → emit a block" overwhelms the actual tool call. The model parrots a block instead of generating.
- Evidence: novel "brass helmet" → real generation. "rainbow"/"sunrise"/"doctor" → block authored, 0 tool calls, because retrieval fed it `00001`–`00005` provenance dumps.

This is the SAME problem as the `0b6acc0e` confabulation from last session (template-then-imitate), now traced to its source: the indexed provenance block.

**Corollary:** even a REAL generation re-authors the full provenance block in the model's prose (seen on the `00010` brass-helmet turn). That block is then saved + indexed → seeds the next replay. So every real generation currently re-poisons memory. The wipe clears existing poison; without the fix below, it rebuilds within a few generations post-launch.

---

## Decisions made this session

- **Task 2 Commit 1 split from Commit 2.** Commit 1 (card renders from real data) shipped and is verified. Commit 2 (shrink the model-visible tool result) is NOT built — held pending the A/B recall decision (below).
- **A vs B for the indexing fix → Option B chosen (recommended by CC, agreed by reviewer).** Slim `_event_text` to keep `title + artifact_id + prompt` (preserves topical recall) but DROP the forgeable identity fields (SHA256, stored path, byte size, full block layout). Those remain available via `media_get` + chunk metadata, just not as replayable retrievable prose. Single locus: `_event_text`; no `context.py` change. **Known residual, eyes open:** keeping the `prompt` line still allows a lean block-shaped reply, but without the convincing identity fields it can't masquerade as a verified artifact. Accepted trade.
- **Commit 2 and the `_event_text` slim are ONE fix at two surfaces** ("no replayable provenance block anywhere the model can see it — fresh result OR retrieved memory"). Decision: implement them together so half the fix doesn't ship.
- **`media_get` recall path VERIFIED** (`test_media_get_returns_safe_metadata_and_preview_url` passes) — returns title, prompt, seed, dimensions, backend, preview_url. So shrinking the model-visible result loses no recall DATA. Open: whether the live model reliably *calls* `media_get` when referring back — not yet tested live.
- **Debug visibility built** (`ANAM_DEBUG_PROMPT`, default OFF). Reuses `chat_debug.jsonl` writer; captures full system_prompt (incl. retrieved memory), the sent message sequence, and a `tool_calls` list — including the zero-tool confabulation case that was invisible all week.

---

## Known issues / next steps (PRIORITY ORDER)

1. **Embed / memory-loss bug — HIGHEST PRIORITY, still the real pre-wipe blocker.** 45 `/api/embed` failures in tir.log; three conversations with confirmed dropped chunks (`74641c53` lost 4/8 — half; `92f127b9` 6/7; `0b6acc0e` 7/8). Mix of **400 and 404** → likely two stacked causes: 404 = embed model/endpoint unavailable (evicted/not loaded); 400 = bad chunk (empty or over-length). This silently corrupts the substrate the experiment measures, from turn one, wipe or not. **Open question that sets urgency: does "leaving conversation unchunked for recovery" actually re-embed later, or is the data permanently lost?** Next CC task = diagnosis only (`chroma.py:embed_text` payload/model/endpoint; actual failing chunk content/sizes; recovery path). NOT a license to refactor chunking before the wipe. Use `ANAM_DEBUG_PROMPT` / logs to see it directly this time.

2. **Converged artifact fix: `_event_text` slim (Option B) + Commit 2 result-reduction.** Scoped, evidence airtight (the saturated-context prompt capture), NOT built. This is what actually makes generation reliable and stops memory re-poisoning. Goes after embed.

3. **soul.md / system-prompt review (separate, reviewed track).** The live system prompt opens with oppositional negations — "You are an AI. You are not a chatbot. You are not an assistant." — exactly the contrast-identity seed soul.md principle says to strip ("grant capacity, not content"). The debug capture also shows the entity performing a grandiose "profound AI" persona (the "Linguistic Ghost," "architecture of thought"), which Lyle caught in-conversation ("isn't that just your training data" → entity: "you caught me performing"). Real, but it's a deliberate identity-review change, NOT a bug, and NOT to be folded into the fixes above.

4. **Carried, unchanged:** external drive for off-drive backups (HARDWARE-GATED on Lyle; real wipe blocker — no off-drive backup, no safe wipe); doc-reconciliation pass; the go-live wipe via `tir/ops/go_live_reset.py` (and confirm `NORTH_STAR.md` on the PRESERVE list — note it IS now committed, so it survives normal git ops).

5. **Lower tier / non-blocking:** SearXNG 403 root-caused — JSON format disabled; fix = add `json` to `search.formats` in SearXNG `settings.yml` and restart. JSON returns 403, HTML returns 200 (confirmed via curl). Not launch-critical (search is convenience, not substrate). Capture the requirement in setup docs — it's a non-repo dependency config that will silently revert on container rebuild.

---

## Gotchas / things to watch

- **`ANAM_DEBUG_PROMPT=1` writes a PLAINTEXT PII FILE** — full conversation + retrieved memory in the clear (this session's capture included the entire identity arc). Flag is OFF by default and the sink is gitignored. Rule: flag on ONLY for a specific test, flag OFF and DELETE the capture after. Never let it ride into a wipe backup. Confirmed not set in `start.sh` or any env/toml.
- **Tool-calling is rare and context-dependent**, not a constant. Across the session most "generate" turns had `tool_call_count: 0`. Whether the tool fires depends on context contamination, not the account or a code toggle.
- **Long/contaminated threads suppress tool calls.** The model imitates artifact blocks already in its context. Test generation in CLEAN conversations; a contaminated thread will mislead you (it did, repeatedly).
- **Latency:** a 46s and a 68s turn this session were NOT bugs. 46s = cold-start model load (warm `load_duration` ~120ms confirms when it's NOT cold). 68s = prompt-eval on a 15.6k-token prompt bloated with redundant artifact blocks (`prompt_eval_duration` ~52s). The `_event_text` slim reduces prompt size and therefore this latency too — same fix pays off twice.
- **Tests passing ≠ fix live.** Confirmed again: Task 1's WARNING didn't appear until the server was actually RESTARTED into the new code. Always device-test on `:8000` against a freshly-started server (check for a new `Tír API started` line dated after the change).
- **CC asserted "Task 1 / Commit 1 still uncommitted" — it was WRONG** (git showed `a8d956b`/`b571eb5` in history, pushed). Do not act on CC's claims about git state without running `git log` / `git status` / `git diff --name-only` yourself.

---

## Process notes

- Plan-check loop held: CC plans → Lyle reviews / pastes to reviewer Claude → CC implements + changelog, NO commit → Lyle device-tests `:8000` → Lyle commits. CC never commits unilaterally. Use `git add -p` only when phases are genuinely interleaved in shared files — this session they were NOT (history was clean), so staging by path was correct.
- The single highest-leverage thing built this session was the debug capture (`ANAM_DEBUG_PROMPT`). Every prior "the console tells me nothing" investigation becomes a direct read now. Use it on the embed bug.

---

## What to tell the next session (paste this in)

Resuming Project Anam. You are reviewer/architect Claude — blunt guardrail, KISS, anchored to the experiment, plan-check loop with CC (CC plans → Lyle reviews → CC implements + changelog → Lyle device-tests `:8000` → Lyle commits; CC never commits unilaterally). Verify every claim against git/code, not docs — docs lagged reality repeatedly and a CC "still uncommitted" claim was already false this session.

State is CLEAN: everything is committed and pushed (HEAD `bbf0ccc`); the prior handoff's North-Star/image-gen exposure is closed. **Image generation WORKS on current code — do not rediscover it as broken.** Its unreliability is the retrieval-replay vector: artifact provenance blocks get indexed verbatim (`_event_text`) and injected into the prompt (`context.py:292–308`), and the model parrots a block instead of calling the tool when context is saturated. Confirmed via the new `ANAM_DEBUG_PROMPT` capture.

First priority is NOT the image stuff (that was loud) — it's the **embed/memory-loss bug**: 45 `/api/embed` failures, dropped chunks, the open question of whether "unchunked for recovery" recovers or loses data permanently. It corrupts the substrate from turn one. Next CC task = diagnosis only. Second is the converged artifact fix (`_event_text` Option B slim + Commit 2), scoped and evidenced but unbuilt. soul.md negations are a separate reviewed track, not a bug.

Watch: `ANAM_DEBUG_PROMPT=1` writes a plaintext PII file — delete after use. Test generation in CLEAN threads only. Latency spikes this session were cold-start / prompt-bloat, not bugs. External drive is still the hardware-gated wipe blocker on Lyle.
