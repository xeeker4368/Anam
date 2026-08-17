# 2026-08-17 — Align `memory_search`'s empty-result wording

## Summary

`memory_search` returned "No indexed prior records found for that query." on an empty
result — wording that reads as *no such record exists*, which is the exact conflation the
relevance-floor tri-state marker (`209fcb2`) was built to prevent on the automatic
retrieval path. Both paths call the same `retrieve()` and inherit the same floors, so they
were describing the same outcome in contradictory ways, and the floor made this fire far
more often than before.

Implements `PLAN-2026-08-17-memory-search-wording-alignment-v2.md`. Wording only — no
change to `retrieve()`, the floors, or the automatic path's markers. No commit.

## What changed

- **`skills/active/memory_search/memory_search.py`** — the empty-result return string is now:

  > "The memory search returned no results for that query. That is a fact about the search,
  > not about the past — nothing closely matching was returned, which is not the same as
  > nothing existing."

  Plus a comment recording why the wording is scoped the way it is (below).
- **`tests/test_memory_search_skill.py`** — the one coupled assertion updated. That was the
  only test asserting the old string; two doc references (`SESSION_HANDOFF_2026-08-16.md`,
  `changelog/2026-08-16-relevance-floor.md`) mention it descriptively and were left alone as
  historical record.

## Why this wording and not the automatic path's

The obvious move — reuse `NO_MATCHING_MEMORY_MARKER` verbatim — would have made things
worse. That marker says the search *"returned nothing above the relevance threshold"*, which
asserts the search ran and scored candidates. `memory_search` cannot observe that (finding 1
below), so under a backend failure that phrasing would be a confident false statement about
a search that never happened.

The chosen wording claims only what this call site can actually observe: that the search
returned nothing, and that this is a fact about the search rather than about what exists.
Verified true under both cases it has to cover:

| check | result |
|---|---|
| does not assert records don't exist | OK |
| does not claim a relevance threshold was applied | OK |
| does not claim the search completed successfully | OK |
| only claims "returned no results" | OK |

## Two findings surfaced during investigation — neither fixed here

### 1. `retrieve()` returns empty identically for "found nothing" and "both legs failed"

`tir/memory/retrieval.py` wraps each leg in its own `try/except`, logs a warning, and
degrades to `[]`:

```
except Exception as e: logger.warning("Vector search failed, falling back to BM25 only: ...")
except Exception as e: logger.warning("BM25 search failed, falling back to vector only: ...")
if not vector_filtered and not bm25_raw: return []
```

**It never raises.** Tested by execution with both backends failing (Ollama unreachable +
locked DB): `memory_search` returned the empty-result string, byte-identical to the
genuinely-empty case, and no exception propagated. The generic tool-error path is never
reached.

This is why the new wording is deliberately weaker than the automatic path's marker — it has
to remain true when the search silently failed.

### 2. `RETRIEVAL_FAILED` is effectively unreachable on the automatic path too

Same root cause. Replicating `routes.py:548-563` exactly with both backends down:

```
both backends down -> retrieval_status = 'attempted' | chunks: 0
  empty-marker shown : True
  ERROR-marker shown : False
```

Because `retrieve()` returns normally, the `except` never fires, status resolves to
`ATTEMPTED`, and the entity is told *"Memory search ran for this message and returned nothing
above the relevance threshold"* — a confident, false statement about a search that did not
run. `RETRIEVAL_FAILED` only fires if something other than the search backends throws.

**This is a defect in the 08-16 relevance-floor work, not introduced by this task, and it is
mine.** I built the tri-state and verified the three states by passing `retrieval_status` in
directly — which proved the rendering and never exercised the detection. The failure branch
was never tested against an actual backend failure.

Recorded in `BACKLOG.md` under Memory / recovery. Not fixed here, per scope.

## Tests / checks run

- `tests/test_memory_search_skill.py` — 5 passed.
- Direct verification that the new string is returned, and is accurate, under both a
  both-legs-failed retrieval and a genuinely-empty retrieval.
- **Full suite: 992 passed.**
- Production store untouched (this task writes nothing).

## Known limitations

- **The tool still cannot distinguish failure from absence** — it says the same thing in
  both cases. The wording is now honest under both, which is the most that can be done
  without the upstream fix. That is the point of finding 1, not an oversight here.
- **Wording only.** No failed/empty distinction was added to `memory_search`, per scope.
  Adding one now would duplicate a distinction that is currently non-functional on both
  paths; the upstream `retrieve()` fix should land first.

## Project Anam alignment check

1. **Name?** No. 2. **Called the entity Anam/Tír?** No. 3. **Personality?** No.
4. **Raw experience preserved?** Yes — no store access of any kind.
5. **Derived artifacts traceable?** Unchanged. 6. **Tool calls recorded?** Unchanged.
7. **Created artifacts remembered?** Unchanged. 8. **Context construction inspectable?**
   Unchanged; this is tool-result text, not context assembly.
9. **More cumulative?** Indirectly — the entity is no longer told that an empty search
   means the memory does not exist, which is a prerequisite for honest recall.
10. **Anam/entity distinction?** Preserved. 11. **Migration?** None.
12. **Tests?** Above. 13. **Core substrate changed unnecessarily?** No — one string in one
    skill file. 14. **External dependencies?** None. 15. **Workspace vs. self-modification?**
    Unaffected. 16. **Legacy renaming avoided?** Yes.

Invariant 4 note: the entity must be able to distinguish what it experienced from what it
did not. "No indexed prior records found" quietly asserted absence on the entity's behalf;
the replacement reports only what the search did. Findings 1 and 2 are the remaining gap in
that same distinction, now written down rather than carried in someone's head.

## Follow-up

- `retrieve()` failure-vs-empty distinction (BACKLOG.md). It is the fix that would make
  `RETRIEVAL_FAILED` mean something and would let `memory_search` eventually say something
  sharper than the deliberately-weak wording shipped here.
- Still tracked separately: the `FABRICATION_DETECTORS` coverage gap (six of seven tools
  have no detector; zero observed exploitation).
