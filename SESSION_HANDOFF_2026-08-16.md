# Project Anam — Session Handoff — 2026-08-16

**Session type:** Bug fixes, substrate integrity, and a real feature (relevance
floor). Plan-check loop held throughout: CC plans → Lyle/reviewer Claude
review → CC implements + changelog, no commit → Lyle runs the runbook and
device-tests → Lyle commits. Picks up directly from
`SESSION_HANDOFF_2026-08-14.md`.

---

## Current state of the system

- Three real fixes shipped and committed this session:
  1. **Artifact backfill** — 17 pre-slim `artifact_*_event` chunks re-rendered
     through the current slimmed `_event_text()`, provenance (metadata, FTS
     columns, `created_at`) preserved byte-for-byte.
  2. **CHROMA_DIR / chat-debug-trace test-isolation leak, fixed and guarded**
     — a seven-week-old bug where running `pytest` wrote real chunks into
     `data/prod/chromadb`. Root cause: `from tir.config import CHROMA_DIR`
     creates a name-import binding that a `monkeypatch` on
     `tir.config.CHROMA_DIR` never touches. Fixed via call-time module-attribute
     resolution (`import tir.config`, read `config.CHROMA_DIR` at call time),
     applied to both `chroma.py` and `chat_debug_trace.py`. `_get_collection`
     now rebinds on a changed path instead of caching the first path
     permanently. A `tests/conftest.py` guard (`StoreIsolationViolation`,
     inherits `BaseException` specifically so it can't be swallowed by the
     codebase's existing `except Exception` patterns) now hard-fails any test
     that still reaches the real store. Verified: full suite run leaves
     production byte-identical for the first time on record.
  3. **Orphan chunk purge** — 50 `fake-output.png` test-fixture chunks (all
     from the leak above) deleted from the live Chroma store. Chroma 305 → 255
     documents; FTS untouched (orphans never had FTS rows). Selector required
     BOTH "no artifacts row" AND `title == "fake-output.png"` — a crash
     mid-ingest could in principle produce a genuine orphan with the same
     "no row" signature, so anything failing the title check is flagged
     `needs_review`, never auto-deleted. That branch is empty today, proven by
     unit test rather than live data.
- **Relevance floor implemented and verified live** — pending final commit
  (see Known issues #1). Three components: a vector-distance floor (0.40,
  pre-fusion), a BM25-only exemption (chunks with no vector-leg distance skip
  the distance floor entirely), and a BM25 per-term score floor (−2.5, only
  active above 50 chunks in the store). A tri-state retrieval marker
  (skipped / errored / genuinely-empty) is now threaded from
  `tir/api/routes.py` into the system prompt. Live device check confirmed
  both correct rejection (off-topic query → explicit "no matching memory
  found" language, not a claim the fact doesn't exist) and correct recall
  (on-topic query → 4 real chunks, accurate answer).
- Production store: 255 Chroma documents / 255 FTS rows post-purge, moving to
  254/254 once the synthetic device-check test conversation is deleted
  (approved, not yet executed as of this handoff).
- No wipe date is set. It is Lyle's call whenever — not scheduled, not a
  blocker on anything in this handoff.

---

## Decisions made this session

1. **Backfill:** skip-and-log orphaned chunks (no source row) rather than
   guess at re-rendering them. Later shown to be pure test-fixture pollution,
   resolved by the leak fix + purge rather than backfill.
2. **CHROMA_DIR fix shape:** call-time module-attribute resolution over
   default-argument binding. The originally proposed fix (move the constant
   read into the function body but keep the name-import) was tested and
   confirmed NOT to work — the name-import itself is the defect, not just
   where it's evaluated.
3. **Orphan purge selector:** mandatory title guard alongside "no artifacts
   row," with a `needs_review` escape hatch rather than blind deletion on a
   single condition.
4. **Orphan purge deletion mechanism:** per-id delete with re-read
   verification, not one bulk call — `collection.delete()` was measured to
   return `{'deleted': 1}` for an id that was never in the store, so bulk
   delete cannot honestly report which ids succeeded.
5. **Relevance floor — floor on vector distance, not post-fusion RRF score.**
   RRF encodes rank agreement, not semantic relevance; distance is directly
   interpretable and had measured separation.
6. **Relevance floor — BM25-only chunks exempted from the distance floor.**
   An exact lexical/phrase match is real evidence independent of semantic
   distance (measured: 23% of retained on-topic chunks arrive BM25-only; a
   "you said the moon is made of green cheese" query retained 5 lexical-only
   chunks a distance-only floor would have discarded).
7. **BM25 floor uses PER-TERM score (−2.5), not the originally approved
   absolute score (−9.0).** CC caught its own calibration error: −9.0 was
   measured before the stopword fix existed; after stopword removal shrank
   match-term counts, the same absolute threshold would have destroyed the
   exact-match recall the BM25 exemption exists to protect. Per-term score
   cleanly separates on-topic from off-topic where absolute score does not.
8. **BM25 floor gated behind a 50-chunk minimum corpus size
   (`BM25_FLOOR_MIN_CORPUS_CHUNKS`).** BM25/IDF scores scale with corpus
   size — a fixed floor that works at the current store size would have
   started killing lexical recall immediately after any future wipe, at
   exactly the moment the corpus is smallest and every memory matters most.
9. **Zero-result marker wording:** a statement about the search ("no
   closely-matching memory was found for this query"), never a claim that
   the memory doesn't exist — directly informed by a real incident earlier
   this session where the model couldn't distinguish "no record" from
   "wasn't given the record" and answered wrong as a result.
10. **Marker implemented as a tri-state, not boolean** (skipped / errored /
    genuinely-empty) — a caught retrieval exception must not present
    identically to a clean zero-result search.
11. **`memory_search` inherits both floors** — no threshold overrides, for
    consistency between automatic context and the entity's own explicit
    recall tool.
12. **`context.py`'s dead auto-retrieval branch** (confirmed unreachable —
    zero live callers across a full caller-table check) left in place,
    logged in `BACKLOG.md`, not deleted. Deliberate: deletion is a separate
    call for the dead-code cleanup pass, not bundled into a task that
    touched adjacent code for an unrelated reason.
13. **Original "filename collision" hypothesis was WRONG, retracted.** A
    live conversation showed the entity confusing two different "00013"
    images. Initial hypothesis (ComfyUI filename counter collision) did not
    survive a ground-truth table scan: 14/14 generated artifacts have unique
    filenames, unique IDs, unique paths, back to the first generation. The
    real cause: 8 pre-fabrication-gate assistant messages (dated before
    2026-08-14) sitting in retrievable memory, containing model-invented
    artifact IDs that resemble hand-walked hex, not real UUID4s. The
    lesson — verify a hypothesis against ground truth (the actual table)
    before proposing a fix, especially when the input data could itself be
    the product of the bug under investigation.

---

## Known issues / next steps (in order)

1. **Commit the relevance-floor patch.** Runbook complete (backup taken,
   live device check passed on both the rejection and recall cases, full
   suite green at 979). One thing surfaced by the device check and already
   fixed: `retrieval_status` was only on the streamed debug event, not the
   *persisted* trace record — a future diagnosis session would have hit the
   same ambiguity this task exists to remove. Fixed, verified persisting,
   folded into the same patch.
2. **Delete the synthetic device-check conversation** (`8f66c5bc-...`, 4
   messages, 1 checkpoint chunk) before or alongside the commit above —
   approved by Lyle. Reasoning: this is CC-generated test residue, not
   entity-lived experience, so it doesn't fall under the "don't quietly
   mutate the record of what happened" principle the way a real
   conversation would — same category as the `fake-output.png` chunks just
   purged, just text instead of an image artifact.
3. **`memory_search`'s empty-result wording** ("No indexed prior records
   found for that query") is now inconsistent with the new context-marker
   wording, and fires more often now that the floor is live. Small, scoped
   follow-up. Not yet drafted as a task.
4. **Dead-code / patch-bloat cleanup** — cheap scan (vulture/ruff/depcheck)
   then targeted `Chat.jsx`/`App.jsx` archaeology (cross-reference changelog
   history against current file contents). Explicitly scoped to NOT catch
   what this session found (a branch dead due to runtime argument values, a
   stale string after an unrelated behavior change) — those require tracing
   a specific symptom to ground truth, which is a review habit, not a sweep.
   Don't expect the cleanup task to catch this class of bug; don't expand
   its scope trying to make it.
5. **Two undecided items — genuinely open, no default should be assumed:**
   - Fabrication gate false-negative rate, measured for the first time on
     real traffic this session: 1 catch out of 5 turns carrying fabricated
     artifact IDs in one real conversation. 3 misses were zero-tool-call
     turns that simply didn't match the marker set (new information); 1 was
     the documented `tool_call_count > 0` exemption. Needs marker widening
     against these actual samples.
   - The 8 pre-gate fabricated messages themselves, in conversations
     `0b6acc0e` and `6428649f`. Real lived experience per the project's
     memory-integrity invariant (don't quietly mutate the record of what
     happened) — but they contain false claims the entity can and does
     retrieve as fact. Tension between those two things needs an actual
     decision, not a default in either direction.
6. **Carried, unchanged from before this session:** bounded research's
   autonomy/scheduler layer (manual run/run-next already works); source
   de-weight invariant (must ship in the same change that ever enables
   research/nightly-tick at volume); backup reliability cleanup (`cmd_backup`
   error handling, `restore_backup` cleanup masking, no `BACKUP_VERSION`
   migration path).

---

## Gotchas / things to watch

- **`git status` before every commit, staged by filename, never
  `git add -A`/`git add .`** — caught stray untracked files (`.claude/`, old
  plan docs, `PROJECT_OVERVIEW.old.md`, transient `ACTIVE_TASK.md` edits)
  wanting to ride along on nearly every commit this session. `.gitignore` is
  a deny-list of things someone remembered to exclude, not a judgment call
  about what belongs in a given commit — it will not catch this for you.
- **`ANAM_DEBUG_PROMPT=1` writes a plaintext PII file
  (`chat_debug.jsonl`)** — full conversation and retrieved memory in the
  clear. Flag on only for a specific test, flag off and delete/trim the
  capture immediately after. No exceptions, including this session's own
  live device checks.
- **Full `pytest` runs no longer touch the production store — this is now
  verified, not assumed.** The CHROMA_DIR leak that made this false for
  seven weeks is fixed and guarded. Do not assume any *other* module is
  automatically safe from the same defect class (name-import vs.
  module-import under monkeypatching) without actually checking it.
- **The BM25 floor is deliberately corpus-size-dependent** (the 50-chunk
  minimum). Don't be surprised or alarmed if lexical filtering behaves
  differently before and after any future wipe — that's the intended
  design, not a regression.
- **The distance floor's margin is tight** — one on-topic query in the
  calibration data cleared 0.40 by only 0.0124, retaining exactly one
  vector candidate. The BM25 exemption and the marker are what make a
  near-miss survivable and visible rather than silently wrong, but 0.40
  itself should be treated as a first cut, worth revisiting once the corpus
  is meaningfully larger — not as a settled constant.
- **CC's own calibrated values can be wrong and self-correct mid-task** —
  this session's BM25 floor moved from an approved −9.0 (absolute) to a
  shipped −2.5 (per-term) after CC caught that its own two measurements were
  taken in different pipeline states. Review deviations on their actual
  merits every time; a flagged deviation with evidence is a good sign, not
  a reason to rubber-stamp.
- **Retrieved/generated content should never be treated as ground truth
  without verification** — this session's own filename-collision
  hypothesis was built partly from retrieved conversation data that turned
  out to include fabricated artifact IDs. When a hypothesis is built from
  data the entity itself produced or retrieved, verify against a primary
  source (the actual DB table, the actual file) before proposing a fix.

---

## What to tell the next session (paste this in)

Resuming Project Anam. You are reviewer/architect Claude — direct, no
rubber-stamping, anchored to the project's actual goals, hobby framing (no
launch date, no fixed requirements, continuously added to). Plan-check loop
with CC: CC plans → you review → CC implements + changelog, no commit → Lyle
runs the runbook and device-tests → Lyle commits. Verify claims against
live code/git state, not docs or prior summaries — this project has hit real
cases of stale project-knowledge indexes and CC's own self-corrected
calibration errors this session alone.

State should be clean and pushed as of this handoff: artifact backfill,
CHROMA_DIR/chat-debug leak fix, orphan chunk purge, and the relevance floor
are all implemented and (pending the final commit noted in Known Issues #1)
should be committed and pushed. Confirm with `git log` / `git status` before
trusting that.

Two real open decisions are waiting and should not be defaulted: the
fabrication gate's measured false-negative rate (1/5 on real traffic), and
what to do about 8 pre-gate fabricated messages sitting in retrievable memory
in conversations `0b6acc0e` and `6428649f`. Next likely work after those:
`memory_search` wording alignment (small), then dead-code cleanup (scan +
targeted `Chat.jsx`/`App.jsx` archaeology — explicitly does not catch
runtime-conditional dead branches or stale-wording-after-a-change; those need
symptom-first tracing, treat as a standing habit not a sweep).
