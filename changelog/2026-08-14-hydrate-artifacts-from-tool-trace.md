# 2026-08-14 — Chat: hydrate artifact cards from `tool_trace` on message fetch

## Summary

A generated-image card rendered during streaming, then disappeared on any reload,
conversation switch, or (on mobile) tab switch away and back. The card was never
persisted-and-lost — it was never *rebuilt*. `fetchMessages` mapped the server's
message rows into a shape that simply omitted `artifacts`, so every persisted
message came back with no cards regardless of what its stored trace contained.

The data was already on the wire the whole time. `/api/conversations/{id}/messages`
does `SELECT * FROM main.messages`, so `tool_trace` (a JSON string) is already in
every response; the frontend just dropped it on the floor.

Fix is the mirror image of the streaming path: one pure helper that reads the same
structured `tool_results[].selection` records the stream reads, applied in the
`fetchMessages` map. Implements the approved diagnosis in `ACTIVE_TASK.md`. No commit.

## Files changed

- `frontend/src/components/Chat.jsx` — added pure helper `artifactsFromToolTrace(message)`
  (module scope, directly after `ArtifactCard`); added `artifacts: artifactsFromToolTrace(m)`
  to the `serverMessages` map in `fetchMessages`.
- `tests/test_messages_endpoint_tool_trace.py` (new) — backend contract test pinning
  `tool_trace` in the `/messages` response.
- `changelog/2026-08-14-hydrate-artifacts-from-tool-trace.md` (this file).

Deliberately **not** touched, per the approved scope: `ArtifactCard`,
`mergeServerMessagesWithLocalPending` and the other merge helpers, the resume path,
`tir/api/routes.py`, and the backend generally. The change is additive: two edits,
one new file.

## Behavior changed

- Persisted assistant messages whose `tool_trace` contains a
  `tool_results[].selection` of `kind === "generated_image"` now render their
  artifact card(s) after a fetch, in trace order, matching what streaming showed.
- Nothing else changes. Messages with no trace, an unparseable trace, or only
  non-image selections (e.g. `moltbook_authored_posts`) get `artifacts: []` — the
  same empty state as before this patch.

### Why the helper is written the way it is

- **Structured-only, never text.** A card comes solely from a `selection` object
  the backend emitted for a real, successful artifact record. Message prose is
  never parsed. This is the same rule the streaming branch enforces at
  `Chat.jsx` (`data.selection && data.selection.kind === 'generated_image'`), and
  it is what keeps the June/August confabulation class of bug from reaching the UI —
  a fabricated provenance block in message text can never produce a card.
- **Fail-safe-empty.** Missing / null / empty / unparseable / non-array traces, null
  records, non-array `tool_results`, and non-object results all yield `[]`. A
  malformed trace renders nothing rather than a broken or invented card. `ArtifactCard`
  already returns `null` when its preview fetch fails, so the two layers agree.
- **Pure and dependency-free.** No hooks, no fetch, no state — it is a data
  transform over one message row, so it is trivially reasoned about and (later)
  trivially testable once a frontend harness exists.
- Tolerates an already-parsed array as well as the JSON string the API returns, so
  it does not silently break if the endpoint ever starts deserializing the column.

## Tests / checks run

- **New backend contract test** (`tests/test_messages_endpoint_tool_trace.py`, 3 cases):
  `tool_trace` survives the endpoint verbatim; the `generated_image` selection is
  reachable with its `artifact_id`/`preview_url`/`title`; messages without a trace
  still carry the field as `null`.
- **Mutation-checked the contract test** — temporarily made `api_get_messages` strip
  `tool_trace` from its rows; all 3 cases failed as intended; reverted. The test has
  teeth, rather than passing vacuously.
- **Full Python suite → 916 passed, 0 failed.**
- **Helper behavior verified directly** (15 cases, all pass) with a throwaway node
  script outside the repo, since there is no frontend test runner: no/null/empty/
  unparseable/non-array trace, null record, missing or non-array `tool_results`,
  result without selection, non-image selection ignored, single image selection,
  two records with order preserved, and already-parsed array input.
- `npm run build` → clean. `npm run lint` → 1 pre-existing error only
  (`react-hooks/set-state-in-effect` at `Chat.jsx:14`, inside the untouched
  `ArtifactCard`). The new helper adds no lint findings.
- Note: the worktree used for this patch has no gitignored `data/` directory, which
  makes 2 `test_moltbook_selection_continuity` cases fail on `unable to open database
  file`. Confirmed environmental, not a regression: the same file is 6/6 green in the
  main checkout, and 916/916 pass in the worktree once an empty `data/` exists.

## Known limitations

- **Manual acceptance is still outstanding** and is the real proof; the automated
  checks above cover the backend contract and the helper's logic, not the rendered
  UI. Per the approved task: reload the page, switch conversations and back, and on
  mobile switch tabs away and back — the image must survive all three.
- No frontend test harness was built for this. That remains a separate, known
  backlog item, deliberately out of scope here.
- Cards are hydrated for any message row carrying a matching selection. In practice
  the backend only persists `tool_trace` on assistant messages, so no role filter
  was added — a filter would be dead code asserting a fact the data already holds.
- The card set is rebuilt from the trace on every fetch, so a message that streamed
  a card whose backing artifact was later deleted will still attempt the card;
  `ArtifactCard` degrades to rendering nothing when the preview fetch fails.
- `preview_url` is trusted as stored. That matches the streaming path exactly — the
  patch introduces no new trust in trace contents that the live path did not have.

## Follow-up work

- Frontend test harness (existing backlog item), at which point
  `artifactsFromToolTrace` is the natural first unit under test — the throwaway
  cases listed above port over directly.
- The pre-existing `react-hooks/set-state-in-effect` lint error in `ArtifactCard`
  is untouched and still worth a separate cleanup.
- If a second artifact `kind` ever renders a card, the `kind` check here and the one
  in the streaming branch must change together; worth collapsing into one shared
  predicate at that point rather than now.

## Project Anam alignment check

1. Did this assign the entity a name? No.
2. Did this call the entity Anam or Tír? No.
3. Personality instead of observed behavior? No — display-layer only.
4. Raw experience preserved? Yes. Nothing written, migrated, or mutated; this is a
   read path that reconstructs display state from an already-stored trace.
5. Derived artifacts traceable? Yes — strengthened. The card is now provably derived
   from the persisted `tool_trace` record, the same source the stream used, rather
   than existing only as ephemeral client state that vanished on reload.
6. Tool calls recorded? Unchanged; this consumes those records.
7. Created artifacts remembered? Yes — this is precisely the fix: an artifact the
   entity actually created stops vanishing from the conversation's visible history.
8. Context construction inspectable? Unchanged.
9. Autonomy more cumulative? Neutral.
10. Anam/entity distinction preserved? Yes.
11. Migration required? No. No schema change; `tool_trace` is an existing column.
12. Tests run? Listed above — full suite 916 passed, plus a mutation-checked contract test.
13. Core substrate behavior changed unnecessarily? No. Backend untouched; the one
    backend file added is a test.
14. New dependencies/services? None.
15. Workspace vs self-modification distinction preserved? Yes — unrelated.
16. Legacy package renaming avoided? Yes — no `tir/` rename.

Checked against `NORTH_STAR.md` before implementing: no conflict. Invariant 4
(provenance is sacred) is served rather than strained — the card is rendered only
from a provenanced tool record, never from model prose. Invariant 3 (minimal,
legible substrate) is respected: one pure function, no new mechanism, no new state.
