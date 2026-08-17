# 2026-08-17 — Make `RETRIEVAL_FAILED` reachable: `retrieve()` signals total search failure

## Summary

`retrieve()` swallowed backend exceptions per leg and returned a bare list, so
"both search backends are down" was indistinguishable from "nothing matched."
`RETRIEVAL_FAILED` — the tri-state marker's third state, shipped in `209fcb2` — had
been **unreachable for its intended purpose since it shipped**, and the entity was being
told *"Memory search ran for this message and returned nothing above the relevance
threshold"* about searches that never completed.

`retrieve()` now returns a `RetrievalResult` (a `list` subclass) carrying
`search_failed`. Implements `PLAN-2026-08-17-retrieve-failure-signal.md` **with a
corrected predicate** (below). No commit.

## The predicate correction — and a pattern worth naming

The plan specified `search_failed = vector_leg_failed and bm25_leg_failed`, and required a
test asserting that an all-stopword query plus a failing vector leg yields
`search_failed=False`, on the reasoning that *"a skip must not be conflated with a
failure."*

The premise is right; the conclusion doesn't follow. The BM25 leg is **skipped entirely**
when `_sanitize_fts5_query` returns `""`. If the vector leg then raises, **one leg was
attempted, zero succeeded, and nothing was searched at all** — yet `True and False` reports
healthy. Verified live before implementing:

```
query 'what is it'  ->  fts5_query = ''
  vector leg called: True | raised: yes
  bm25   leg called: False   <-- skipped, never attempted
  plan's predicate: vector_leg_failed and bm25_leg_failed = False
  legs actually attempted: 1   legs that succeeded: 0
```

And it is production-reachable, not theoretical — these pass `is_greeting` and the
retrieval policy and land in `retrieve()` with an empty FTS query:

| user message | greeting? | policy | reaches `retrieve()`? | fts5 |
|---|---|---|---|---|
| "what is it" | False | normal | **YES** | `''` |
| "what about it" | False | normal | **YES** | `''` |
| "so what did we do about that" | False | normal | **YES** | `''` |
| "is that all of it" | False | normal | **YES** | `''` |

Shipped predicate — **attempted/succeeded, not failed/failed**:

```python
    any_attempted = vector_attempted or bm25_attempted
    any_succeeded = vector_succeeded or bm25_succeeded
    search_failed = any_attempted and not any_succeeded
```

A skipped leg is neither a success nor a failure; it leaves the denominator instead of
counting as a pass.

**This is the second first-pass measurement error caught before shipping today**, and the
pattern is worth naming rather than quietly fixing. Earlier: the "1 catch in 5" gate
false-negative rate, which counted turns whose *prompt* contained fabricated IDs and read
the gate's firing rate across them — measuring the wrong side of the model. Both mistakes
share a shape: **a plausible predicate over a population that was never checked against the
cases it would misclassify.** In both, the fix came from enumerating the reachable cases
and running them, not from re-reading the logic. Worth carrying forward as a habit: when a
predicate decides something the entity will be told as fact, enumerate the reachable inputs
and execute them before shipping the predicate.

## What changed

- **`tir/memory/retrieval.py`**
  - New `RetrievalResult(list)` with `search_failed`, documented — including the caution
    that the attribute does not survive slicing, `sorted()`, `list()`, or `+`.
  - Leg bookkeeping: `vector_attempted` / `vector_succeeded` / `bm25_attempted` /
    `bm25_succeeded`, set inside the existing `try`/`except` blocks. No new failure
    detection — this retains information the function already computed and discarded.
  - **All three return paths** construct the type explicitly (guardrail 1): the empty-query
    guard, the both-legs-empty guard, and the final `return
    RetrievalResult(fused[:max_results], search_failed=search_failed)`. The last one is the
    trap the guardrail exists for — a slice returns a plain list and would drop the
    attribute. Verified by grep after implementing: 3 returns, 3 constructions.
- **`tir/api/routes.py`** — reads `getattr(retrieved_chunks, "search_failed", False)`
  **before** `budget_retrieved_chunks()`, with an inline comment at the point of risk
  (guardrail 2) stating that reordering silently reintroduces the bug because the `getattr`
  default is `False`. The existing `except Exception` is unchanged and now explicitly
  documented as guarding everything *around* `retrieve()`, not the search legs.
- **`docs/PROMPT_INVENTORY.md`** — regenerated (line shifts only).

## Verification

Live reproduction across every reachable case, replicating `routes.py`'s logic exactly:

| case | status | marker shown |
|---|---|---|
| both healthy, real results | `attempted` | chunks |
| genuine empty, both healthy | `attempted` | empty |
| vector DOWN, bm25 healthy + hits | `attempted` | chunks |
| bm25 DOWN, vector healthy + hits | `attempted` | chunks |
| vector DOWN, bm25 healthy + empty | `attempted` | empty |
| **both DOWN** (original investigation) | **`failed`** | **ERROR** |
| **all-stopword + vector DOWN** (the correction) | **`failed`** | **ERROR** |
| all-stopword + vector healthy | `attempted` | empty |

Both target cases now reach `MEMORY_SEARCH_ERROR_MARKER` instead of falsely claiming a
search ran.

**Tests: full suite 1004 passed** (992 + 12 new). All 41 pre-existing `retrieve()` stub
sites across 6 files pass **unmodified** — they return plain lists, and the `getattr`
default degrades them to `attempted`, i.e. current behaviour. Production store untouched
(252 Chroma / 252 FTS).

New tests: both legs fail → `search_failed=True`; one fails/one succeeds → `False`; genuine
empty → `False`; **all-stopword + failing vector leg → `True`** (replacing the plan's
inverted test); all-stopword + healthy vector leg → `False`; empty query → `False`; every
return path carries the attribute; `RetrievalResult` behaves as a plain list. Plus
routes-level integration tests for both `FAILED` cases and a **scope-boundary regression
test** asserting partial failures still report `attempted`, so a future session cannot widen
the fix without a deliberate decision.

## Scope boundary held

Partial failure — one leg down, the other healthy — still reports `attempted`, per the
plan. Cases (c)/(d)/(e)/(f) from the investigation are unchanged: a user cannot currently
tell that half the retrieval stack is down. Tracked in BACKLOG.md, deliberately not fixed
here, and now covered by a test that documents the boundary as intentional.

## Known limitations

- **`search_failed` is fragile by construction.** It survives on the object `retrieve()`
  returns and nowhere else — any slice, `sorted()`, `list()`, or `+` produces a plain list
  and drops it. Mitigated by reading it immediately at the one call site that cares, the
  inline comment there, and the class docstring. It is not mitigated by types.
- **Only the automatic path consumes it.** `memory_search` still cannot distinguish failure
  from empty; its wording (shipped 08-17) is deliberately true under both, so it needs no
  change — but it also gains nothing here.
- **Partial degradation remains invisible**, per scope.

## Project Anam alignment check

1. **Name?** No. 2. **Called the entity Anam/Tír?** No. 3. **Personality?** No.
4. **Raw experience preserved?** Yes — no store access; this is a return-shape change.
5. **Derived artifacts traceable?** Unchanged. 6. **Tool calls recorded?** Unchanged.
7. **Created artifacts remembered?** Unchanged. 8. **Context construction inspectable?**
   Improved — `retrieval_status` now reports failure honestly and is already surfaced in
   both the streamed debug event and `chat_debug.jsonl`.
9. **More cumulative?** Indirectly — the entity stops being told that a broken search found
   nothing. 10. **Anam/entity distinction?** Preserved. 11. **Migration?** None.
12. **Tests?** Above. 13. **Core substrate changed unnecessarily?** `retrieval.py` is core;
    the change is additive bookkeeping plus a return type that is a `list` everywhere it
    matters, with all five callers confirmed unaffected. 14. **External dependencies?** None.
15. **Workspace vs. self-modification?** Unaffected. 16. **Legacy renaming avoided?** Yes.

Invariant 4 note: the entity must distinguish what it experienced from what it did not.
Being told "the search ran and found nothing" when the search never ran is exactly that
distinction failing, in the layer meant to protect it.

## Follow-up

- Partial-failure visibility (BACKLOG.md) — is "half of retrieval is degraded" useful to the
  model, or purely an operator concern? Not forced by current data.
- Still open: the `FABRICATION_DETECTORS` coverage gap (six of seven tools have no
  detector; zero observed exploitation).
