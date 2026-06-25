# Code Review — Project Anam (`tir/` + `skills/`)

**Date:** 2026-06-24
**Mode:** REVIEW ONLY — no code was changed. This document is notes only.
**Scope:** All ~75 Python files under `tir/` and `skills/active/` (~23.4k LOC), excluding the `.pyanam` virtualenv and `__pycache__`.
**Method:** Six parallel manual reviews by module cluster; dead-code claims grep-verified repo-wide (including `tests/`). No automated linter was available in the environment (`ruff`/`pyflakes`/`flake8`/`vulture`/`pylint` all absent) — consider adding one to CI.

> **Nothing here has been actioned.** Severity tags reflect reviewer judgment, not agreed priority. Several items are "confirm intent" rather than "bug." Treat anything touching schema, memory architecture, or capabilities as governed by `NORTH_STAR.md` / `AGENTS.md` before any change.

---

## 0. Reviewer corrections (false positives caught during verification)

- **`tir/memory/chroma.py:290` `empty_collection` — `removed` unbound: NOT a bug.** A reviewer flagged a possible `UnboundLocalError`. Verified false: the `try` has only a `finally` (no `except`), so any exception before `removed` is assigned **propagates** — the `return` is never reached with `removed` unbound. Safe as written. (Optional: initialize `removed = 0` purely for readability.)

---

## 1. Highest-value findings (HIGH)

| # | File:line | Finding |
|---|-----------|---------|
| H1 | `tir/tools/http_declarative.py:319` & `skills/active/web_search/web_search.py:116` | **SSRF / DNS-rebind gap.** URL validators block private/loopback **IP literals** and `localhost`, but a hostname that *resolves* to a private/internal IP (e.g. `169.254.169.254`, `10.x`) passes — DNS resolution happens later inside `requests.get`. These are "read-only safe GET" tools; the most serious finding. Mitigation: resolve host, validate the resolved IP, and pin it before connecting. Logic is duplicated across both files — fix once in a shared helper. |
| H2 | `tir/media/image_generation.py:150` | **`_safe_metadata_value` is a no-op.** `json.dumps(value, sort_keys=True)` is computed and **discarded**; the function returns the raw `value` in all cases. It neither validates serializability nor returns the serialized form. A non-serializable backend metadata value would slip through and only fail later in `create_artifact`. Decide intent (validate-and-drop, or return the string) and implement. |
| H3 | `skills/active/moltbook/moltbook.py:261` | **`mentions` is always empty.** `mentions = []` is initialized, never appended to, and returned at line 338. The tool description advertises separated "mentions"; all results actually flow into `other_results`. Misleading to the model — either wire it up or remove the key. |
| H4 | `tir/behavioral_guidance/apply.py` (whole module) | **Large intentionally-dormant block.** Both entrypoints unconditionally `raise DORMANT_BEFORE_GO_LIVE_ERROR`, making every helper unreachable (`build_guidance_append_block`, `_validate_applicable_proposal`, `_read_guidance_file`, `_append_block`, `_write_atomic`, etc.) plus several unused params. The module docstring says this is deliberate pre-go-live scaffolding, so **keep** — but the **unused imports** (`BehavioralGuidanceValidationError`, `get_behavioral_guidance_proposal`, `update_behavioral_guidance_proposal_status`, `datetime`, `timezone`) are unambiguous cleanup. |

---

## 2. Confirmed dead / unused code

Grep-verified to have zero live callers (some are deliberate scaffolding — confirm against roadmap before deleting):

- **`tir/tools/context.py:15` `ToolContext.request_id`** — assigned in `routes.py:518` but **never read** by any tool. (The `request_id` in the debug payload at `routes.py:974` reads a local var, not the context field.) Field is dead. ✅ verified.
- **`tir/tools/registry.py:459` `SkillRegistry.get_skill`** — zero callers anywhere (tests use `get_skill_for_tool`). ✅ verified.
- **`tir/admin.py:187` `ci = add_channel_identifier(...)`** — return value assigned and never used. The call has side effects (keep the call; drop the binding). ✅ verified.
- **`skills/active/moltbook/moltbook.py:261` `mentions`** — see H3. ✅ verified.
- **`tir/research/moltbook_sources.py:438` `source_trace_relative_path`** — no callers; superseded by `source_trace_unique_relative_path`.
- **`tir/config.py`** dead constants (no code consumers; changelogs confirm several are intentionally inactive): `EMBED_MAX_CHARS` (249), `CONTEXT_WINDOW` (262), `OUTPUT_RESERVE` (263), `RETRIEVAL_FLOOR/CEILING/DEFAULT` (264–266), `TRUST_WEIGHTS` (255–259). At minimum mark them inactive; some document intended tuning.
- **`tir/engine/context.py`** `autonomous` param + `_autonomous_situation()` (91–97) — never invoked with `autonomous=True` in prod or tests. Likely future-use; confirm.
- **`tir/engine/context_debug.py:63` `full_journal_included`** — hardcoded `None`, never populated. Placeholder field.
- **`tir/media/image_generation.py:341-346`** `if seed/width/height is not None` guards are now **always true** (the recent default-fill change coerces all three to ints upstream). Redundant; harmless.
- **`tir/memory/db.py`** — a meaningful block is production-dead (test-only or unwired): `set_channel_auth` (578), `get_messages_since_last_chunk` (824), `save_summary`/`get_summary` (926/941), `save_document`/`update_document_chunk_count` (955/977), `get_unconsolidated_conversations`/`mark_conversation_consolidated` (1109/1099, the `consolidated` flag is never set), and the entire `tasks` table API (`add_task`/`get_pending_tasks`/`update_task_status`, 991–1045, referenced only by `tests/test_db.py`). **Likely planned substrate — confirm against roadmap before removing.**
- **`tir/feedback/service.py`** — whole subsystem is consumed only by tests; no production writer/reader. Dormant. Confirm intent.
- **`tir/retrieval.py:266` `trust_weights`** param — accepted, documented "Deprecated… no longer applies," never read.
- **`tir/tools/http_declarative.py:495`** `auth.header or "Authorization"` fallback for `header_env` is unreachable (validation always sets `header`). Minor dead branch.
- **`tir/artifacts/source_roles.py:61`** `"operational_guidance" → "runtime_guidance"` mapping is unreachable from live ingest (`operational_guidance` not in `ALLOWED_AUTHORITIES`); kept only for legacy DB rows.

---

## 3. Correctness issues to verify (MEDIUM)

### Memory / data integrity
- **`tir/memory/artifact_indexing.py:240` — Chroma metadata not sanitized for `None`/non-scalar.** Unlike `journal_indexing` and `research_indexing` (which run `_chroma_metadata()` before `upsert_chunk`), this module merges `media_metadata` raw. ChromaDB rejects `None`/list/dict values → upsert throws, and the broad `except Exception` (319) turns it into a silent `status="failed"` with content lost. **This is the same sanitizer the other two indexers have — apply it here.**
- **`tir/memory/db.py`** — mixed transaction styles: `create_user` (470) and `save_message` (761) issue explicit `conn.execute("BEGIN")`/manual `COMMIT`, while other writers rely on implicit transactions + `conn.commit()`. Fragile; standardize. Also `save_message` folds the `conversations.message_count` update into the same txn as the archive+working insert, so a missing/FK-invalid conversation row rolls back the "sacred" archive write too — confirm archive should be insulated.
- **`tir/memory/chunking.py:217` `maybe_chunk_live`** — computes `chunk_index = (turn_count // CHUNK_TURN_SIZE) - 1` **and** independently re-derives groups via `_assign_messages_to_chunks`, then indexes one by the other. These can diverge on non-standard turn distributions (trailing orphan user messages → extra tail group), risking wrong-chunk or out-of-range. `chunk_conversation_final` avoids this by iterating groups directly; the live path's dual computation is the latent bug.
- **`tir/memory/db.py:451`** — `chunks_fts` creation wrapped in `try/except OperationalError` that swallows **all** operational errors, potentially masking a genuinely corrupt FTS schema as "already exists."

### Tools / API
- **`tir/api/routes.py:769` vs `tir/engine/agent_loop.py:228`** — prefetch dispatch omits `_context`; agent loop includes it. Harmless for `web_fetch` (ignores context) but a silent attribution gap if the prefetch tool set changes.
- **`tir/api/routes.py:142` vs `agent_loop.py:248`** — inner-envelope (`effective_ok`) handling disagrees: prefetch unwraps a nested `{"ok": False}`; the agent loop streams the **outer** `ok` only. A tool returning `{"ok": True, "value": {"ok": False}}` is reported `ok:True` in the loop but `ok:False` in prefetch. Two result producers, two semantics.
- **`skills/active/moltbook/moltbook.py:326`** — `_is_post_like(compact)` is called on an already-**compacted** dict in the profile path, but `_is_post_like` inspects raw keys (`post`, `post_id`). Posts with empty titles get misclassified and dropped into `other_results`. The first loop correctly passes the raw item; the profile loop passes the wrong shape. Likely a bug.
- **`tir/media/backends/comfyui.py:224-246`** — polling can exceed the intended total timeout: each history `GET` uses the **full** `timeout_seconds` inside a `timeout_seconds` deadline loop, plus separate POST and view-fetch timeouts. End-to-end wall clock can be several× `timeout_seconds`. If a single budget is intended, derive per-request timeouts from `deadline - now`.

### Reflection / research / ops
- **`tir/reflection/operational.py:552` `_candidate_is_duplicate`** — a candidate with no `source_message_id`/`source_artifact_id` dedupes purely on **title** (`return True` at 570), collapsing same-titled items across unrelated windows. Confirm it's not over-suppressing.
- **`tir/ops/backup.py` vs `tir/ops/status.py`** — two different "latest backup" definitions: `find_latest_backup` (backup.py:266) filters to manifest-bearing dirs; `_latest_backup` (status.py:68) picks max-by-name then checks manifest. Also `pre-restore-<ts>` folders sort lexically **after** real `2026-…` backups (`p` > `2`), so "latest" can resolve to a pre-restore safety backup. Reconcile; MEDIUM if `--latest` correctness matters operationally.
- **`tir/open_loops/__init__.py`** — `update_open_loop_metadata` is imported by `bounded.py:17` but omitted from the package `__all__`, while the sibling `update_open_loop_status` is exported. Inconsistent public surface.
- **`tir/diagnostics/service.py:281`** — `update_diagnostic_status` clears `resolved_at` when moving out of a resolved state, erasing the original resolution timestamp. Given the "raw experience is primary" principle, consider recording a transition instead of destroying history. (Product-intent question, not a code bug.)

---

## 4. Optimization opportunities

- **`tir/memory/db.py`** — a fresh `_connect_working()` (connect + `PRAGMA` + `ATTACH`) per call; hot assistant turns open/attach/close several times. A pooled/thread-local connection would remove repeated `ATTACH`/`PRAGMA`.
- **`tir/engine/journal_context.py:145` `_journal_artifacts_for_date`** — selects **all** `journal` rows then filters in Python by JSON-parsing `metadata_json` per row. Grows linearly with journal count. Promoting `journal_date` to an indexable column would allow a `WHERE` (requires migration notes per project rules).
- **`tir/reflection/journal.py`** — per-conversation DB fan-out: `_load_window_messages` is called once in `_format_transcript` (200) and again in `build_reflection_memory_query` (786), plus a separate `COUNT/MIN/MAX` per conversation (361) → ~3×N queries. Batchable; `list_conversations_for_reflection_journal` already returns `window_message_count`.
- **`tir/artifacts/search.py:256` `search_media_artifacts`** — always pulls ~100 rows and scores/JSON-parses all of them in Python even for small `limit`. Fine for V1 scale; obvious optimization point as the table grows. Also `_search_blob`/metadata recomputed per scored artifact.
- **`tir/memory/audit.py`** — five count/ID query pairs run the same `EXCEPT`/`GROUP BY` scan twice each; `chunked_missing_fts` (95) does a structurally heavy FTS5 join (UNINDEXED columns can't be indexed). Admin-triggered, so LOW priority.
- **`tir/memory/chroma.py`** — `query_similar` calls `collection.count()` twice (241/245); `delete_chunks_by_prefix` (200) loads **all** IDs to filter by prefix (Chroma has no prefix query — structural, scales with store size on every research re-index).
- **`skills/active/media_artifacts/media_artifacts.py:21` `_shape_generated_image_result`** — makes an extra DB round-trip (`get_media_artifact_reference`) purely to build `preview_url`, re-fetching the artifact `generate_image` already returned. `_safe_preview_url` is deterministic from the artifact in hand — skip the query. Also that re-fetch omits `user_id`, bypassing the visibility check (not exploitable here, but inconsistent).
- **`tir/media/backends/comfyui.py:195`** — `validate_config()` then `_workflow_path()` resolves/stats the workflow file twice per `generate`, and `image_generation.generate_image` already validated once → up to 3 file stats per generation.
- **`tir/engine/agent_loop.py:281`** — the no-tool text path **buffers the entire response** then replays tokens after `done`, defeating true streaming for the common text-only turn. Buffering is deliberate (to suppress pre-tool-call text), but confirm the latency cost is intended.
- **Duplicated helpers worth consolidating** (drift risk + single-point-of-fix for the SSRF bug):
  - `_normalize_text` + `_chunk_text` (+ `_chroma_metadata`) copied across all three `*_indexing.py` files — and `artifact_indexing` is the one **missing** `_chroma_metadata`, which is exactly bug §3.
  - SSRF validators (`http_declarative._validate_url`, `web_search._validate_fetch_url`) + byte-cap/decoder (`_read_response_bytes`/`_decode_response`) duplicated nearly verbatim across the two tool files.
  - Freshness validators duplicated: `registry._validate_freshness_metadata` ≈ `http_declarative._validate_freshness`.
  - `ALLOWED_INTENDED_USES` defined in both `artifacts/media.py:23` and `media/image_generation.py:35`.
  - `_research_date` duplicated (`research/bounded.py:362` ≈ `research/manual.py:627`).

---

## 5. Lower-severity notes & smells (LOW)

### Engine
- `agent_loop.py` — `tool_context` param undocumented in docstring; relies on `envelope["ok"]` always present (KeyError risk if dispatch contract breaks).
- `artifact_context.py:114` — `effective_limit` silently clamps the caller's `max_results` (8) down to `RECENT_ARTIFACT_LIMIT` (5). Confirm the silent clamp is intended.
- `context.py:198,242` — `type(value) in (int, float)` instead of `isinstance(...)`; fragile around `bool`. `_current_situation`/`_autonomous_situation` differ by one line (share a helper).
- `ollama.py:78` — streaming `resp` not closed on early `break`/exception (no `with`/`try-finally`); connection may not return to the pool promptly. Three near-duplicate `chat_completion_*` functions; inconsistent default `role` (`"chat"` vs `"default"`) is a footgun.
- `journal_context.py:52` — `_now_year` final fallback effectively unreachable for correct callers. Four near-identical `_empty_meta` patch blocks.
- `url_prefetch.py:117` — "save this url and summarize it" may be classified as content-intent before the generic-mention exclusion; verify.

### Memory
- `retrieval.py` — `_apply_artifact_boosts` (178) and distance filter (322) do direct key access (`adjusted_score`, `distance`) — safe only because callers always set them; not self-contained. `db.py:900` `search_bm25` selects `rank as bm25_score` but the score is never read (fusion uses positional rank).
- `journal_indexing.py:97` / `research_indexing.py:88` — partial-failure leaves orphaned chunks in Chroma+FTS with no rollback (research self-heals on re-index; journal has no delete/repair path). `delete_research_chunks` does a `COUNT(*)` then `DELETE` on the same predicate — use `cursor.rowcount`.
- `chunking.py:55` — `%-d`/`%-I` strftime are POSIX-only (documented).
- `chroma.py:200` — `delete_chunks_by_prefix` docstring says "Not used in normal operation" but it **is** used by `research_indexing` — stale docstring.

### Artifacts / media
- `ingestion.py:105` — `_write_bytes` re-resolves the already-resolved parent path per ingest. Double/triple validation of `artifact_type`/`status`/path across `ingestion`→`create_artifact_file`→`create_artifact` (intentional "fail before write," but heavy).
- `media.py:227` — `normalize_media_metadata` forces `intended_use="general"` onto every image artifact even when none was supplied; confirm intent.
- `search.py:215` — exact `artifact_id` match scores +120 **and** +60 substring (redundant double-count).
- `comfyui.py:32` `_safe_base_url` — host allowlist won't cover `0.0.0.0`/IPv6 variants (acceptable for localhost-only V1); `safe_view_url` error string drops `subfolder` (cosmetic mismatch with real request).
- `governance_blocklist.py:32` `governance_file_basename` — public-looking helper with a single internal caller; consider `_`-prefixing.

### API / tools / skills
- `auth.py:28` — `is_public_api_path` is exact-string match (trailing slash/case bypass → forces auth; fails closed, but brittle). Fail-open when no secret configured is documented but worth a security-checklist note.
- `registry.py` — `_validate_freshness_metadata` runs at both decoration time and `__post_init__` (redundant double-work per tool); duplicate-name check duplicated for `@tool` vs declarative paths.
- `http_declarative.py` — `safety.allow_redirects` schema field never affects behavior (`allow_redirects=False` hardcoded at 115); `_find_unbalanced_braces` (351) runs the regex sub twice; `_error_type_for_exception` has a redundant `RequestException` branch.
- `web_search.py` — `web_search` provider response loaded fully via `response.json()` (no byte cap; trusted endpoint, lower risk); broad `except Exception` (463) duplicates the `RequestException` branch above it; `_merge_extracted_text` overlap loop is O(n²)-ish (capped at 80 words).
- `memory_search.py` — takes no `_context`, so it can't scope to user/conversation; confirm global recall is intended.
- `moltbook.py` — `downvotes/upvotes/comment_count` use `item.get(k, post.get(k))` (default eagerly evaluated); `_truncate_preview` may receive non-dict items; `_clamp_limit` duplicates schema bounds.
- `routes.py` — dead inits: `journal_primary_context = None` (620) and the `journal_primary_context_meta` default dict (621–632) are overwritten unconditionally at 633–635; `recent_artifact_context_meta` likewise. `history_message_count` duplicates `model_message_count` (743/746). `prompt_breakdown` exposes four keys carrying two values. Local re-import of `get_connection` inside `api_health` (1627) though imported at module top (50). `import os` at bottom of file (1652). `@app.on_event("startup")` (197) uses deprecated FastAPI API (use lifespan handlers).

### Research / reflection / scheduler / governance
- `moltbook_sources.py` — `_first_value` can't distinguish a real `0` from a default `0`; failure traces add `tool_name`/`status_code`/`path` keys absent from success traces (non-uniform shape).
- `bounded.py` — `to_dict` doesn't surface `metadata_error` as a dedicated field; `model` exposed but `ollama_host` not threaded to moltbook note generation.
- `manual.py` — `_normalize_research_note_path` is a pure alias for `_normalize_continue_file_path`; three copies of the source-metadata validation block; `register_existing_research_note` double-reads the file on the write path.
- `journal.py` — count-reconstruction idiom `len(rows) + skipped` (476/529/684) reads like a double-count bug but is correct; `_activity_limit` helper used by only one of four section builders (inconsistent).
- `operational.py` — `open_loop_candidates` passed through unvalidated beyond the list check; `normalized_observations` keep arbitrary unmodeled keys (`{**item}`) unlike the strict whitelist for review candidates.
- `nightly.py` / `review.py` — broad `except Exception` labels everything `tool_error`/`failed`, masking programming errors as per-conversation failures (acceptable for a heartbeat, but hides real bugs).
- `behavioral_guidance/service.py:290` — redundantly nulls `applied_at` twice.
- `behavioral_guidance/review.py` — `local_day_window_to_utc`/`BehavioralGuidanceReviewError` are imported by `reflection/*` — surprising dependency direction (reflection → behavioral_guidance for a date util). Consider relocating the tz/window helper to a neutral util module.

### Ops / config / admin
- `config.py` — `WEB_HOST/PORT` and `SEARXNG_URL/WEB_SEARCH_TIMEOUT_SECONDS` honor legacy `TIR_*` **and** `ANAM_*`, unlike every other setting (`ANAM_*` only) — undocumented inconsistency. `_env_int`/`_env_float` raise bare `ValueError` at import on bad env values without naming the var. Many `int(_config_value(...))` calls omit a default and rely on the fallback key existing.
- `admin.py` — module docstring command list is stale (missing `set-role`, `go-live-reset`, `review-*`, `research-open-loops-*`). Many handlers have a redundant specific-`except` + identical broad-`except` (both print same message + `sys.exit(1)`); `cmd_backup` lacks the `try/except` that `cmd_restore` has (raw traceback on failure).
- `backup.py` — `restore_backup` `finally` `unlink()` could mask the real error (use `missing_ok=True` + swallow unlink errors); `BACKUP_VERSION` strict equality means a future bump silently makes old backups unrestorable (document intent).
- `go_live_reset.py` — `plan_go_live_reset` builds a count by interpolating a `WHERE` clause into `_count`'s table-name arg (constant string, no injection, but fragile pattern); CLI can't pass `backup_root`/`verify_target_dir` (tests-only). **Positive:** the 5-gate destructive-op design (arm → backup → verify-restore → typed phrase → wipe → audit, with `_assert_all_tables_classified`) is well-built.
- `capabilities.py` / `status.py` — `os.getenv("MOLTBOOK_TOKEN")` read directly (bypassing config) in two places; `status._registry_counts` reaches into private `registry._skills` (fragile coupling — add a public accessor).
- `chat_debug_trace.py` — `_SECRET_RE` quoted-value redaction may leave a dangling trailing quote (secret is still redacted); add a unit test for the quoted case.
- `diagnostics/service.py` — `diagnostic_issue_to_dict` does `json.loads` without `try/except` (crashes on a hand-edited corrupt row).

---

## 6. Cross-cutting themes & recommendations

1. **No SQL injection and no mutable-default-argument bugs** were found anywhere — values are bound, dataclasses use `field(default_factory=...)`. Good baseline.
2. **Duplication is the dominant smell.** The SSRF validators, HTTP byte-cap/decoder, freshness validators, `_normalize_text`/`_chunk_text`/`_chroma_metadata` indexing helpers, and `ALLOWED_INTENDED_USES` each exist in 2–3 copies. The artifact-indexing `_chroma_metadata` omission (bug §3) is a direct consequence — consolidating would both remove drift and give the SSRF/metadata fixes a single home.
3. **Inconsistent DB-access convention:** service modules use a lazy `_db()` import (for test monkeypatching); `reflection/*` import `get_connection` at module top. Standardize.
4. **Broad `except Exception` that mask programming errors** recur in `nightly.py`, `review.py`, `scheduler`, and several `admin.py` handlers. Consider narrowing or at least logging the exception type.
5. **Dormant subsystems** (`behavioral_guidance/apply.py`, `feedback/service.py`, large parts of `db.py`: `tasks`/`summaries`/`documents`/`consolidated`) are extensive. Confirm each against `ROADMAP.md`: if planned scaffolding, leave with a marker comment; if abandoned, remove. This directly serves the NORTH_STAR "minimal, legible substrate" invariant.
6. **Add a linter to CI** (`ruff` would catch the unused imports, dead locals, and redundant branches mechanically — none were auto-detectable here because no linter is installed).

---

## 7. Suggested triage order (if/when changes are approved)

1. **H1 SSRF/DNS-rebind** (`http_declarative.py`, `web_search.py`) — security; fix in a shared helper.
2. **§3 artifact-indexing `_chroma_metadata` omission** — likely real runtime failures on media artifacts.
3. **H2 `_safe_metadata_value` no-op** — decide intent; currently silently inert.
4. **H3/§3 moltbook `mentions` + `_is_post_like(compact)`** — model-facing correctness.
5. **§3 `db.py` transaction styles + `maybe_chunk_live` dual chunk-index** — data-integrity, touch carefully (memory architecture is governed).
6. **Unambiguous dead cleanup** (unused imports in `apply.py`, `ToolContext.request_id`, `SkillRegistry.get_skill`, `admin.py:187 ci`, dead `routes.py` inits, redundant now-always-true guards in `image_generation.py`) — low-risk, after confirming the dormant-subsystem items against the roadmap.

*End of review. No files other than this document were created or modified.*
