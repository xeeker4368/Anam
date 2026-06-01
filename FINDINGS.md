# FINDINGS.md

## Critical

### CORS proxy-only LAN assumption
- Severity: critical/high
- Status: open
- Description: Backend CORS only allows localhost/127.0.0.1. LAN/iPhone access works through Vite proxy. Direct backend LAN access would fail.
- Current position: Prefer proxy-only; document/test or add configurable origins without exposing backend broadly.

### Scheduler `pre_live_or_live` hardcoded
- Severity: critical/high
- Status: open
- Description: Scheduler audit always records pre-live state.
- Current position: Must fix before go-live.

### Runtime files tracked
- Severity: high
- Status: open
- Description: `data/prod/*` runtime DB/log files are tracked and dirty-prone despite `.gitignore`.
- Current position: Needs explicit untracking plan.

## High

### Greeting detection duplicated
- Severity: high
- Status: open
- Description: `_is_greeting` / greeting patterns duplicated in API route and context code.
- Current position: Extract shared helper.

### Frontend App hook dependency warnings
- Severity: high
- Status: resolved
- Description: App refresh callbacks had hook dependency warnings.
- Resolution: `Frontend Hook Stability + Refresh Narrowing v1`.

### Broad refresh from chat completion
- Severity: high
- Status: resolved
- Description: Chat completion previously triggered conversations, health, artifacts, and open-loops refresh.
- Resolution: Chat completion now refreshes conversations only.

### App/Chat resume refresh overlap
- Severity: high
- Status: partially resolved
- Description: App and Chat both respond to visibility/focus/pageshow events. Coalesced and active-stream suppression added, but manual verification still needed.
- Current position: Avoid more patches unless testing shows continuing user-visible issue.

### Pending message merge by content
- Severity: high
- Status: open
- Description: Pending/optimistic messages may be matched by role+content; repeated identical messages can confuse merge/adoption.
- Current position: Plan before implementation.

### Missing frontend tests
- Severity: high
- Status: open
- Description: High-risk frontend merge/resume/localStorage behavior lacks automated tests.
- Current position: Add helper tests after cleanup.

### Full conversation history loaded each chat request
- Severity: high
- Status: open
- Description: Chat path loads full conversation history into model context.
- Current position: Plan context/window strategy later; do not rush before UI stable.

### Source/soul wording strength
- Severity: high/medium
- Status: open
- Description: Model strongly echoes `soul.md`, including “own time” and “decide.” Wording may overstate current capability.
- Current position: Review before go-live; do not casually edit.

## Medium

### Checkpoint embedding on response path
- Severity: medium
- Status: open
- Description: Conversation checkpointing can call Ollama embedding after each assistant turn.
- Current position: Plan moving off hot path or less frequent checkpointing.

### Registry refresh combines artifacts and open loops
- Severity: medium
- Status: partially resolved
- Description: Combined registry refresh was too broad.
- Resolution: `fetchArtifacts`, `fetchOpenLoops`, `fetchRegistries` split.
- Remaining: Verify all callers are scoped correctly.

### Media search scans recent artifacts only
- Severity: medium
- Status: open
- Description: `media_search` filters a recent slice in Python; older matches may be missed later.
- Current position: Not go-live blocker unless media volume grows.

### Artifact ingestion orphan files
- Severity: medium
- Status: open
- Description: File can be written before artifact/indexing fully succeeds.
- Current position: Cleanup-on-failure or pending artifact status later.

### Image preview MIME trust
- Severity: medium
- Status: open
- Description: Preview safety relies mostly on extension/MIME metadata.
- Current position: Add magic-byte check later.

### Image self-representation prompt guard
- Severity: medium
- Status: open/deferred
- Description: Tool enforces `intended_use`, but not prompt content.
- Current position: Be careful; avoid brittle blocklist unless clearly needed.

### `chat_debug.jsonl` unbounded growth
- Severity: medium
- Status: open
- Description: Debug trace file can grow indefinitely.
- Current position: Add rotation/size cap later.

### Startup dependency install
- Severity: medium
- Status: open
- Description: `start.sh` may install frontend dependencies if missing.
- Current position: Consider explicit `--install-deps` or clear setup error.

### CORS test missing
- Severity: medium
- Status: open
- Description: No test pins expected proxy-only LAN/CORS behavior.

### Scheduler heartbeat `action_count=0`
- Severity: medium/low
- Status: open
- Description: Heartbeat write records action_count 0, which may confuse operators.
- Current position: Optional clarity fix.

## Low

### `_safe_metadata_value` misleading name
- Severity: low
- Status: open
- Description: Function validates JSON serializability but returns original object.
- Current position: Rename or clarify.

### Silent no-persist assistant branch
- Severity: low
- Status: open
- Description: If no assistant content persists, branch is silent except upstream logs.
- Current position: Add warning log.

### Legacy comments with identity language
- Severity: low
- Status: open
- Description: Some comments say “She sees tools.”
- Current position: Clean later.

### Visual viewport update cost
- Severity: low/medium
- Status: open
- Description: iPhone keyboard handling writes multiple CSS vars repeatedly.
- Current position: Do not touch unless keyboard jank persists.

### Auto-scroll per token
- Severity: medium/low
- Status: open
- Description: Smooth scroll may fire on every token.
- Current position: Plan-only before changing.

### Debug log usefulness
- Severity: low
- Status: partially resolved
- Description: `tir.log` is mostly operational noise. Structured debug trace apparently exists but needs rotation.
