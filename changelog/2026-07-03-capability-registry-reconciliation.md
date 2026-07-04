# 2026-07-03 — Capability registry reconciliation (built vs enabled)

## Summary

`tir/ops/capabilities.py` declared `self_modification`, `review_queue`, and
`autonomous_research` as `implemented: False` while plumbing for the first two
exists (self-mod has been exercised in prod). The `implemented` field means
"enabled as a live capability in the current safety posture," not "exists in the
codebase" — an ambiguity that caused the operator to lose track of what was built.
This fixes the semantics so the registry can no longer be misread, **reporting
accuracy only** — no enforcement, flag, or capability changes. The registry stays a
safety-posture declaration; built-state truth lives in `FEATURE_INVENTORY.md`.
Implements `PLAN-2026-07-03-capability-registry-reconciliation.md` (approved, route
b, with the snapshot-location amendment). No commit.

## Route taken (requirement 1): keep `implemented`, add doc block + `built`

Renaming `implemented` was rejected: the frontend System panel groups cards on
`capability.implemented` (`SystemPanel.jsx:89,102`), and it is in the API contract
+ both test suites — renaming would ripple through the frontend and change a field
consumers rely on (violating requirement 3). Instead:
- Added a **FIELD SEMANTICS doc block** atop `_CAPABILITY_DEFINITIONS` stating what
  `implemented` means (enabled/safety-posture) and does not mean (tree existence),
  and defining the new `built` field.
- Added a **reporting-only `built` boolean** to all 16 definitions. `_base_runtime_state`
  still reads only `implemented`, so **runtime status logic is unchanged**; `built`
  flows into the API output additively (existing values untouched). No frontend change.

## The three corrected entries (enablement untouched)

- **self_modification** → `built: True` (staged propose→review→apply pipeline exists
  and has run in prod); `implemented` stays `False`, `mode` stays `staged_only`,
  `status` stays `staged_only`.
- **review_queue** → `built: True` (`tir/review/service.py`; operational reflection
  writes items); `implemented` stays `False`, `status` stays `not_implemented`.
- **autonomous_research** → **stays `built: False`** — *autonomous* research is not
  built — but its note now makes the distinction legible: bounded, human-approved
  research plumbing exists and is gated off (`tir/research/bounded.py`); do not read
  this as "no research capability exists." (bounded ≠ autonomous, per requirement 2.)

`built: True` for the 8 already-live capabilities + `reflection_journal`;
`built: False` for `code_sandbox`/`speech`/`vision`/`write_actions`. Values verified
against the archived 2026-06-28 code+prod-data snapshot.

## Inventory-doc consolidation (requirement 4 + amendment)

- **`FEATURE_INVENTORY.md` is now the single canonical built-state doc**, with a job
  header: "what exists in the tree and its run evidence — enablement truth lives in
  `capabilities.py` / the System panel." Added a "Registry reconciliation" note under
  Identity/governance stating the corrected built-state for self-mod (built +
  exercised, staged/dormant enablement), review_queue (built, not enabled), and
  bounded ≠ autonomous — so it no longer disagrees with the registry/snapshot.
- **`FEATURE_MAP_2026-06-28.md` moved to `docs/archive/`** (per the amendment: frozen
  dated docs live in `docs/archive/`) with a "FROZEN DATED SNAPSHOT — superseded by
  FEATURE_INVENTORY.md" header. Kept for provenance (run-evidence tied to that date).
- Reciprocal pointers added between the two.

## Files changed

- `tir/ops/capabilities.py` — doc block + `built` on all 16 definitions + corrected
  notes for the 3 entries. No status-logic change.
- `tests/test_capabilities.py` — `built` in `REQUIRED_FIELDS` + type check; new
  `test_built_field_reflects_tree_existence` asserting the explicit 11 built / 5
  not-built key lists; new `test_reconciled_entries_keep_enablement_unchanged`
  (built moved, enablement did not).
- `tests/test_system_status_api.py` — asserts `built` is present in the
  `/api/system/capabilities` payload and that pre-existing consumer fields/values
  are unchanged (additive-only contract).
- `FEATURE_INVENTORY.md` — canonical job header, snapshot pointer, registry
  reconciliation note.
- `docs/archive/FEATURE_MAP_2026-06-28.md` — moved here + frozen-snapshot header.

## Behavior changed

- `/api/system/capabilities` (and `list_capability_definitions`) gain a `built`
  field per capability. **No existing field value changes** — `implemented`, `mode`,
  `enabled`, `available`, `status` are identical to before. Runtime enforcement and
  the safety posture are unchanged.

## Tests / checks run

- `tests/test_capabilities.py` + `tests/test_system_status_api.py` → 23 passed.
- Full suite → **908 passed**.
- Verified no code/test references the moved doc path.

## Operator device test (before commit)

1. Load the System panel on :8000 — confirm it renders **identically** to before
   (grouping unchanged; the panel ignores the new `built` field).
2. `curl -s localhost:8000/api/system/capabilities | jq '.capabilities.self_modification, .capabilities.review_queue, .capabilities.autonomous_research'`
   — confirm `built: true / true / false` alongside unchanged `implemented`/`mode`/
   `status`.

## Known limitations / follow-ups

- The frontend does not yet display `built` (deliberately out of scope; additive
  field is ignored until a future UI task chooses to surface it).
- FEATURE_INVENTORY reconciliation is targeted (governance/built-state note + header);
  the archived snapshot remains the fullest run-evidence record.

## Project Anam alignment check

- Reporting accuracy / legibility only; preserved debug instrumentation. No name,
  personality, persona, or `soul.md` change.
- No enablement/flag/enforcement change; the registry stays a safety-posture
  declaration (decision not relitigated). No schema/migration. No new dependency.
- Additive API field; consumer-relied values held stable (asserted in tests).
