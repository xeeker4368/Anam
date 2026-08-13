# PLAN — Capability Registry Reconciliation. PLAN ONLY.

**Date:** 2026-07-03 · **Mode:** plan only. **No code, no commit.** For review before implementation.

## NORTH_STAR check
Reporting-accuracy fix to the safety-posture registry: legibility / inspectability, preserving debug instrumentation. No enforcement, flag, or capability change. Aligned; no invariant touched. (The decision that the registry stays a safety-posture declaration, not a build inventory, is settled and not relitigated here.)

---

## Requirement 1 — chosen route: **keep `implemented`, add a doc block + a new `built` field** (route b)

**Ripple analysis of renaming `implemented` (route a) — rejected as too wide and it violates requirement 3:**
- `tir/ops/capabilities.py:243` — `_base_runtime_state` reads `capability["implemented"]` (drives `available`/`configured`/`enabled`/`status`).
- **Frontend `frontend/src/components/SystemPanel.jsx:89,102`** reads `capability.implemented` to *group* cards ("not implemented" vs "active"). Renaming the field breaks the System panel — and requirement 3 forbids changing existing fields consumers rely on.
- `tests/test_capabilities.py` — `implemented` is in `REQUIRED_FIELDS` (`:34`), type-checked (`:91`), and asserted per-capability (`:103,118`). `tests/test_system_status_api.py` likewise.
- The API output (`/api/system/capabilities`) carries `implemented` (via `deepcopy` of the definition), which the frontend consumes.
→ Renaming ripples through status logic + frontend + two test files + the API contract. Rejected.

**Route b (minimal, additive, reporting-only) — chosen:**
- (a) Add a **comment/doc block at the top of `_CAPABILITY_DEFINITIONS`** stating precisely what `implemented` means and does not mean.
- (b) Add a new **`built` boolean per capability** = tree-existence truth, reporting-only. `_base_runtime_state` continues to read only `implemented`, so **runtime status logic is unchanged**; `built` flows into the API output automatically (both `_base_runtime_state` and `list_capability_definitions` already `deepcopy` the definition), an **additive** field. Existing field *values* are untouched → requirement 3 satisfied; the frontend ignores the unknown field until/unless a future (out-of-scope) UI change surfaces it.

**Ripple of route b (contained):** `capabilities.py` (defs + doc block), `tests/test_capabilities.py` and `tests/test_system_status_api.py` (add `built` to the field set + assert values). **No frontend change required.**

Proposed doc block (wording for sign-off):
```
# FIELD SEMANTICS — READ BEFORE EDITING
# This registry is a SAFETY-POSTURE declaration: "what is this system ALLOWED to
# do right now." It is NOT a build inventory. Built/tested truth lives in
# FEATURE_INVENTORY.md.
#
#   implemented — whether this capability is ENABLED as a live capability in the
#                 current safety posture. It drives available/configured/enabled/
#                 status. It does NOT mean "code exists in the tree." A capability
#                 whose plumbing is fully built but gated off is implemented: False.
#   built       — reporting-only: whether the plumbing for this capability EXISTS
#                 in the tree today. Does NOT affect runtime status. built != enabled.
#                 (For research, see the autonomous_research note: bounded != autonomous.)
```

---

## Requirement 2 — exact per-capability changes

Add `built` to **all 16** definitions (so every capability reports it; required for the test's `REQUIRED_FIELDS` check). **No `implemented`, `mode`, or any enablement value changes.** Notes corrected only where they currently mislead. `built` values verified against `FEATURE_MAP_2026-06-28.md` (code + prod-data grounded) and the tree.

| key | implemented (unchanged) | mode (unchanged) | **built (new)** | notes change |
|---|---|---|---|---|
| memory_search | True | read_only | **True** | — |
| web_search | True | read_only | **True** | — |
| web_fetch | True | read_only | **True** | — |
| moltbook_read_only | True | read_only | **True** | — |
| backups | True | manual | **True** | — |
| memory_maintenance | True | manual | **True** | — |
| file_uploads | True | manual | **True** | — |
| image_generation | True | manual | **True** | — |
| reflection_journal | True | manual | **True** | — |
| code_sandbox | False | disabled | **False** | — (accurate) |
| speech | False | disabled | **False** | — (accurate) |
| vision | False | disabled | **False** | — (accurate) |
| write_actions | False | disabled | **False** | — (accurate) |
| **self_modification** | **False (unchanged)** | staged_only | **True** | Rewrite "Not implemented"→style note to: *"Staged propose→review→apply pipeline is BUILT and has been exercised in prod (tir/behavioral_guidance/{service,review,apply}.py; applied guidance feeds the live prompt). Remains staged_only and human-approved — not autonomously enabled. built=True; implemented=False = not a live autonomous capability."* |
| **review_queue** | **False (unchanged)** | disabled | **True** | Replace "Not implemented" with: *"Review-queue plumbing is BUILT (tir/review/service.py; create/list/update review items; operational reflection writes items). Not surfaced as a live capability. built=True; implemented=False."* |
| **autonomous_research** | **False (unchanged)** | disabled | **False** | Replace "Not implemented" with: *"Fully autonomous, self-directed research is NOT built (built=False). BOUNDED, human-approved research plumbing DOES exist and is gated off (tir/research/bounded.py, nightly bounded open-loop) — a distinct, constrained capability. Do not read this entry as 'no research capability exists.'"* |

**The three "lying" entries, made truthful:**
- **self_modification** and **review_queue** flip `built` → **True** (plumbing exists), enablement (`implemented=False`) unchanged.
- **autonomous_research** keeps `built=False` — because *autonomous* research is genuinely not built — but its note is corrected so a reader can no longer conclude "no research capability exists." This is the requirement-2 mandate: **bounded ≠ autonomous, made legible** without flipping a false "built" the other way. (Consistent with `FEATURE_MAP` Tier 5, which classifies autonomous research as not-built-but-bounded-exists.)

Plumbing existence verified in the tree: `tir/review/service.py`, `tir/behavioral_guidance/{service,review,apply}.py`, `tir/research/bounded.py` all present.

---

## Requirement 4 — inventory-doc consolidation

**State of the two docs:**
- `FEATURE_MAP_2026-06-28.md` (Jul 2 mtime, 121 ln) — rigorous, **code + prod-data grounded** built-state map (Built/Tested/Live-wired/Enabled/Run-evidence tiers) + a "CRITICAL DISCREPANCIES (registry vs reality)" section that *is* the source of this task. It is a **dated point-in-time measurement** ("Generated 2026-06-28 from the tree + prod store").
- `FEATURE_INVENTORY.md` (May 31, 255 ln) — broader "capability view + pre/post-go-live plan": project goal, security posture, what-to-build-before/after, relationships to GO_LIVE_CHECKLIST/ROADMAP/FINDINGS. **Older** — predates the discoveries in FEATURE_MAP, so its "built" claims are the ones at risk of disagreeing (e.g. listing as "to build" things FEATURE_MAP proves are built: self-mod pipeline, review queue, bounded research, journal, open loops, nightly loop).

They **partially overlap** on built-state but each has unique content, so this is a *reconcile-and-designate-canonical*, not a pure delete.

**Proposal — one canonical living built-state doc = `FEATURE_INVENTORY.md`:**
1. **`FEATURE_INVENTORY.md` survives** as the single canonical, living built-state doc (non-dated name = the durable one). Fold in FEATURE_MAP's rigorous built/tested/run-evidence findings and the registry-vs-reality reconciliation; **correct every stale "to build" claim** that FEATURE_MAP proves already built (diff the two docs' built-claims; code+data wins).
2. **`FEATURE_MAP_2026-06-28.md` is demoted to a frozen dated snapshot** — add a header line: *"Point-in-time snapshot (2026-06-28). Superseded as the living inventory by FEATURE_INVENTORY.md; kept for provenance (run-evidence tied to that date's prod store)."* Not deleted — the project's provenance ethos favors keeping the dated measurement; but it stops being a competing living doc.
3. Add a reciprocal one-line pointer at the top of `FEATURE_INVENTORY.md`: *"Canonical built-state view. The 2026-06-28 snapshot (FEATURE_MAP_2026-06-28.md) is the frozen measurement this was reconciled from."*
Result: one living canonical doc, one frozen dated snapshot, no disagreement.

(If the reviewer prefers a hard collapse to a single file, the fallback is to append FEATURE_MAP's tables/discrepancy section into FEATURE_INVENTORY and delete FEATURE_MAP — but I recommend keeping the dated snapshot for provenance.)

---

## Requirement 5 — tests

`tests/test_capabilities.py`:
- Add `"built"` to `REQUIRED_FIELDS` and to the per-capability type checks (`assert isinstance(capability["built"], bool)`).
- **New assertion listing plumbing-built capabilities explicitly** and asserting `built is True` for each:
  `{"memory_search","web_search","web_fetch","moltbook_read_only","backups","memory_maintenance","file_uploads","image_generation","reflection_journal","review_queue","self_modification"}`.
- Assert `built is False` for the genuinely-unbuilt set: `{"autonomous_research","code_sandbox","speech","vision","write_actions"}` (locks in the bounded≠autonomous distinction).
- Assert the enablement contract is **unchanged** for the three corrected entries: `self_modification` and `review_queue` and `autonomous_research` still report `implemented is False` / same `mode` / same `status` — i.e. `built` moved, enablement did not.
- (If any existing test asserts the literal "Not implemented" notes text for these three, update it to the corrected note.)

`tests/test_system_status_api.py`:
- Add `built` to the expected field set for the `/api/system/capabilities` payload; assert the pre-existing fields/values the frontend relies on (`implemented`, `mode`, `enabled`, `available`, `status`) are unchanged (additive-only contract).

---

## Out of scope (confirmed — none included)
- No flag flips, enablement changes, or enforcement hooks.
- No editable-config UI (backlogged).
- No change to which capabilities exist (no keys added/removed).
- No frontend change (the new `built` field is ignored until a future, separate UI task chooses to display it).

## Files to change (on approval)
`tir/ops/capabilities.py` (doc block + `built` on 16 defs + 3 corrected notes), `tests/test_capabilities.py`, `tests/test_system_status_api.py`, `FEATURE_INVENTORY.md` (reconcile + canonical header), `FEATURE_MAP_2026-06-28.md` (snapshot header). Plus a changelog entry on implementation.

## Open items for reviewer
1. Confirm route b (keep `implemented` + add `built`) over renaming — recommended.
2. Confirm `autonomous_research` stays `built=False` with a legibility note (vs. flipping it `built=True`) — recommended, per bounded≠autonomous.
3. Confirm the doc plan: `FEATURE_INVENTORY.md` canonical + `FEATURE_MAP_2026-06-28.md` frozen snapshot (vs. hard-collapse to one file).

*Plan only. No code, no commit.*
