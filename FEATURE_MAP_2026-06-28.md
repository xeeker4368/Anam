# Project Anam — Feature / Capability Map

**Generated:** 2026-06-28, from the uploaded working tree (`Anam copy/`) and the live prod store (`data/prod/working.db`).

## How to read this (method, so you can trust or check each cell)

Every claim here is from **code or data**, not memory of conversation. The columns mean:

- **Built** — the module/logic exists in the tree (line count in parens = substance).
- **Tested** — a dedicated `tests/test_*.py` exists.
- **Live-wired** — reachable from the interactive chat path (`routes.py` / `context.py`), vs. **Admin** = only invokable via `admin.py` CLI, vs. **—** = not called.
- **Enabled** — the config/capability flag state. **OFF** = flag defaults False.
- **Run evidence** — actual rows/data in the prod DB proving it executed.
- **Registry** — what `tir/ops/capabilities.py` *declares* (this is a "what's live," not "what's built," source — see the discrepancy section).

Where I'm inferring rather than certain, the cell says so. Two cells I flag explicitly for you to confirm.

---

## THE HEADLINE

**The system is far more built than tonight's conversation implied, and the capability registry hides it.** Nearly every "future feature" you discussed as something to *build* — curiosity queue, journaling, research, the overnight loop, and the self-modification proposal pipeline — already exists, is tested, and in several cases **has run and left data**. The registry declares several of these `implemented: False`, but that field tracks *"enabled as a live autonomous capability,"* not *"exists in the codebase."* You have been navigating by the registry and lost the built layer under it.

**The sharpest instance:** your stated *minimum success condition* — the entity proposing human-approved changes to its own guidance — **has already occurred.** `behavioral_guidance_proposals` holds 2 real proposals; one is `applied` (2026-05-09), and applied guidance feeds the live system prompt. The project, by its own definition, already hit its minimum bar.

---

## MAP

### Tier 1 — Core, live, running now (this is your actual product today)

| Capability | Built | Tested | Live-wired | Enabled | Run evidence |
|---|---|---|---|---|---|
| Conversation + persistence | Yes | Yes | Yes | ON | 58 conversations, 646 messages |
| Memory chunking + embedding | Yes | Yes | Yes | ON | 136 conversation chunks in FTS |
| Hybrid retrieval (vector+BM25+RRF) | Yes | Yes (`test_retrieval`) | Yes | ON | source-blind ranking (see risk note) |
| Artifact upload + ingestion | Yes | Yes (×3) | Yes | ON | 26 artifacts, 108 artifact chunks |
| Image generation (manual) | Yes | Yes (×2) | Yes (manual trigger) | **OFF** (`image_generation.enabled=False`) | works when on (brass-helmet test) |
| Backups / restore | Yes | Yes | Admin | manual | 2 backup snapshots present |
| Memory maintenance / audit / recovery | Yes | Yes | Admin | manual | orphan-recovery path exists, unwired |

### Tier 2 — Self-generation: BUILT, TESTED, HAS RUN — but flag-gated / manual

| Capability | Built | Tested | Live-wired | Enabled | Run evidence |
|---|---|---|---|---|---|
| **Reflection journal** | Yes (1,347 ln) | Yes (`test_reflection_journal`, `test_journal_context`) | **Retrieval: Yes** (`build_primary_journal_context` in chat path). Generation: manual/nightly. | Registry `manual` | **1 journal chunk in live store** |
| **Curiosity queue (open_loops)** | Yes (341 ln) | Yes (`test_open_loops`, `test_research_open_loops`) | Imported into `routes.py` (`get_open_loop`, `list_open_loops`) | — | **4 open loops logged** (source: manual_research) |
| **Bounded research** | Yes (1,104 ln) | Yes (`test_research_bounded`) | Admin / nightly | **OFF** (`allow_bounded_research=False`) | **9 research chunks in live store** |
| **Manual research** | Yes (915 ln) | Yes (`test_manual_research`) | Admin | manual | feeds research chunks/open loops |
| **Overnight loop (nightly tick)** | Yes (278 ln) | Yes (`test_nightly_tick`) | Admin one-shot | **OFF** (`scheduler.enabled=False`, `nightly_tick_enabled=False`) | **2 overnight_runs** — one did a bounded action (32s) |

### Tier 3 — Self-modification & review: BUILT + EXERCISED, registry says "not implemented"

| Capability | Built | Tested | Live-wired | Enabled | Run evidence |
|---|---|---|---|---|---|
| **Self-modification pipeline** (propose→review→apply) | Yes (schema + API + apply logic) | Yes (`test_behavioral_guidance`, `_apply`, `_review`, `test_api_behavioral_guidance`) | API endpoints exist; applied guidance feeds live prompt | Registry `implemented: False`, `staged_only` | **2 proposals; 1 APPLIED, 1 approved** |
| **Review queue** | Yes | Yes (`test_review_queue`, `test_api_review`) | API exists | Registry `implemented: False` | 3 review_items (test data, operator) |
| Behavioral guidance (live) | Yes | Yes | **Yes** — `_load_behavioral_guidance()` → Section 3 of system prompt | ON | applied proposal is in effect |

### Tier 4 — External / social: BUILT but gated hard OFF

| Capability | Built | Tested | Live-wired | Enabled | Run evidence |
|---|---|---|---|---|---|
| Web search (SearXNG) | Yes | Yes | tool | **OFF** (`allow_web=False`) | (SearXNG JSON 403 known) |
| Web fetch | Yes | Yes | tool | **OFF** | — |
| **Moltbook** (read + source collection) | Yes (571 ln + skills) | Yes (×4: `test_moltbook_*`) | tool / research | **OFF** (`allow_moltbook=False`) | read-only per registry; write disabled |

### Tier 5 — Genuinely not built (registry accurate here)

| Capability | Registry |
|---|---|
| Autonomous research (unsupervised) | `implemented: False` — but note `bounded.py` exists; this means *autonomous*, not *bounded* |
| Vision | `implemented: False` — not built |
| Speech / voice | `implemented: False` — not built |
| Code sandbox | `implemented: False` — not built |
| Write/action capability | `implemented: False`, `requires_approval` — not built |

---

## CRITICAL DISCREPANCIES (registry vs. reality) — read these

1. **`self_modification: implemented=False` but the pipeline has applied a change.** Either the registry is stale, or "implemented" here means "autonomous/entity-initiated self-modification," while the **human-in-the-loop proposal→approve→apply pipeline is in fact built, tested, and exercised.** *You need to decide which the field means and make it accurate*, because right now the one document that's supposed to tell you "what can this system do to itself" is understating it. **Confirm:** did the entity *generate* those 2 proposals, or were they authored through a dev/manual path? The `source_experience_summary` fields suggest they arose from real interactions, but I can't prove autonomy from the DB alone. This is the single most important thing to verify about your own system.

2. **`autonomous_research: implemented=False` but `bounded.py` (1,104 ln) exists, has 9 chunks in the store, and an overnight run executed a bounded action.** The registry distinction is presumably "bounded ≠ autonomous," which is defensible — but the effect is the same: a reader of the registry would conclude "no research capability exists," which is false.

3. **`review_queue: implemented=False` but table, API, and 2 test files exist** (rows are operator test data). Plumbing built, capability declared off.

**Net:** `capabilities.py` is a *safety-posture declaration*, not an inventory. It answers "what is this allowed to do right now," which is valuable, but it is NOT the map of what's built — and you've been treating it (or your memory of it) as the latter.

---

## SAFETY POSTURE (the genuinely good news)

Every autonomous and external surface is **flag-gated OFF by default**, and the gating is real, layered, and consistent:

- `scheduler.enabled=False`, `nightly_tick_enabled=False` → the overnight loop cannot run without an explicit flag.
- `allow_bounded_research / allow_moltbook / allow_web / allow_image_generation = False` → each external/generative action is independently gated.
- `image_generation.enabled=False`, `allow_agent_tool=False` → generation off, and agent-callable generation doubly off.
- A capability state-machine (`disabled / read_only / manual / assisted / autonomous / staged_only`) exists as a first-class concept.

This is **good architecture** and it directly contradicts the fear from tonight's conversation that turning things on is easy-to-do-by-accident. It is not. Enabling the overnight loop is a deliberate, multi-flag act. **The danger was never that it's running — it's that you didn't know it was built and gated, so you couldn't reason about it.**

---

## THE ONE UNFIXED RISK THIS MAP CONFIRMS

Retrieval is **source-blind at ranking** (`retrieval.py:355` — `adjusted_score = rrf_score`; trust-weighting is a deprecated no-op). Self-generated content (`journal`=1, `research`=9) currently sits in the live index competing equal-weight with conversation (=136). **Live but negligible today** (10 vs 136). It becomes a real contamination path only if a generation loop is enabled and starts producing volume.

**Invariant to hold:** the source de-weight (a 3-line mirror of the existing `_apply_artifact_boosts` hook) must ship in the *same change* that ever flips `nightly_tick_enabled` or `allow_bounded_research` to True. Never enable generation-at-volume without the de-weight already in place.

---

## WHAT THIS MEANS (blunt)

You are not at "design and build the evolving-AI features" stage. You are at **"you already built them, they're gated off, and you lost the map"** stage. The highest-value action is not writing new features — it's:

1. **Reconcile `capabilities.py` (and `FEATURE_INVENTORY.md`) with reality** so the registry states truth. Decide what `implemented` means and apply it consistently.
2. **Answer the autonomy question on the 2 proposals** — entity-generated or dev-authored? This determines whether you've already hit your success condition or merely built the pipeline for it.
3. **Then** make launch/wipe decisions from an accurate map, not from memory.

You have been pre-launch for 2+ months partly because you keep re-encountering your own system as if it were unfinished. It is substantially finished. The blocker is epistemic, not technical.
