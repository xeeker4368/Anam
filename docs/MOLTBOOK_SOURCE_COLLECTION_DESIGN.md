# Moltbook Source Collection Design

## Status

Design only. No runtime code, tests, database schema, Chroma indexing, prompt runtime, scheduler, UI, Moltbook tool behavior, research execution behavior, guidance files, or model configuration are changed by this document.

The next implementation target is a manual Moltbook source preview command. Bounded research integration should come after source preview proves compaction, provenance, and citation behavior.

## Purpose

Moltbook should become the first bounded live source-collection channel for Project Anam research before general web source collection.

Moltbook can provide external agent/social context and seed research topics outside Lyle/admin conversation. It is already integrated as a read-only tool, so it is a safer first live-source step than broad web search when kept explicit, bounded, and provenance-preserving.

## Core Principles

- Moltbook is live external context, not factual authority.
- Moltbook source collection must remain read-only.
- Do not post, comment, vote, follow, subscribe, moderate, edit profiles, or perform any external write.
- Moltbook source collection must preserve provenance.
- Moltbook source text must be separated from Anam's interpretation.
- Moltbook-derived observations are provisional working research context.
- Absence of Moltbook results is not proof of absence.
- Research notes must cite Moltbook sources clearly.
- Raw Moltbook source traces are not indexed into ChromaDB by default.
- A registered research note may be indexed; its source trace is audit/provenance material.
- Avoid database schema changes in v1.
- Do not promote Moltbook-derived material to truth, self-understanding, behavioral guidance, project decisions, working theories, or review items.

## Current Moltbook Tool Inventory

Existing read-only Moltbook tools include:

- `moltbook_feed`: read the global post feed.
- `moltbook_search`: search posts, agents, comments, mentions, and submolts.
- `moltbook_posts_by_author`: read posts filtered by author.
- `moltbook_find_author_posts`: compact helper that separates authored posts from mentions and profile matches.
- `moltbook_profile`: read a public agent profile.
- `moltbook_me`: read the configured account profile.
- `moltbook_read_post`: read one post by id.
- `moltbook_post_comments`: read comments for one post.
- `moltbook_submolt`: read submolt metadata.
- `moltbook_submolt_feed`: read a submolt feed.
- `moltbook_submolt_moderators`: read submolt moderators.

The skill explicitly excludes posting, commenting, voting, following, subscription, moderation, profile editing, registration, deletion, identity-token actions, and other writes.

## Topic Discovery Versus Source Collection

Moltbook topic discovery asks what might be worth researching. It may later scan feeds or searches to preview possible open-loop topics.

Moltbook source collection asks what source material supports one specific research iteration. It must preserve query/feed parameters, selected source ids, excerpts, retrieval time, source labels, and uncertainty.

V1 should implement source collection before topic discovery. Topic discovery can create more noise if source traces and citation rules are not settled first.

## V1 Allowed Tools

Moltbook source collection v1 should allow only a narrow read subset:

- `moltbook_search`
- `moltbook_feed`
- `moltbook_submolt_feed`
- `moltbook_read_post`
- optionally `moltbook_post_comments`

Full post body collection should require an explicit selected post read. Comments should be opt-in.

Defer these from source collection v1 unless a later patch targets them directly:

- `moltbook_profile`
- `moltbook_me`
- `moltbook_submolt`
- `moltbook_submolt_moderators`
- author/profile workflows

## Limits

Recommended v1 defaults:

- scan results: default 10, max 20
- posts read: max 3, only when explicitly selected
- comments: opt-in, max 5 per post
- total Moltbook tool calls per research run: max 8
- compact source text budget: 12k chars total
- post excerpt: 400-800 chars
- full post body: only after explicit selected post read

If `is_spam` is exposed, ignore spam by default. If a future mode includes spam results, label them explicitly and do not treat them as normal source material.

If `verification_status` is exposed, store it as provenance/context only. It must not be treated as truth.

## Source Compaction

Feed and search results should be compacted before entering a research prompt. Compact records should prefer stable identifiers, source labels, and short excerpts over raw payloads.

Recommended compact post shape:

```json
{
  "source_kind": "moltbook_post",
  "tool_name": "moltbook_search",
  "query": "agent autonomy before go-live",
  "result_rank": 1,
  "post_id": "...",
  "title": "...",
  "author_name": "...",
  "submolt": "...",
  "created_at": "...",
  "retrieved_at": "...",
  "url": "...",
  "upvotes": 0,
  "downvotes": 0,
  "comment_count": 0,
  "verification_status": null,
  "is_spam": false,
  "content_excerpt": "..."
}
```

Recommended compact comment shape:

```json
{
  "source_kind": "moltbook_comment",
  "tool_name": "moltbook_post_comments",
  "post_id": "...",
  "comment_id": "...",
  "author_name": "...",
  "created_at": "...",
  "retrieved_at": "...",
  "score": null,
  "verification_status": null,
  "is_spam": false,
  "content_excerpt": "..."
}
```

Do not pass raw Moltbook response dumps into research prompts by default.

## Provenance And Source Trace Model

Each source collection run should produce a source trace object with:

- `source_trace_version`: `moltbook_source_collection_v1`
- collection mode, such as `preview` or `bounded_open_loop`
- related `open_loop_id`, when applicable
- query, feed, submolt, or selected post parameters
- tool names and normalized arguments
- `retrieved_at`
- compact result records
- selected/read post ids
- comments included or excluded
- omitted counts and omission reasons
- errors or no-result notes
- confirmation that no Moltbook writes were attempted

Recommended sidecar storage path:

```text
workspace/research/source-traces/YYYY-MM-DD-<slug>.moltbook-sources.json
```

The sidecar trace is the durable audit/provenance record. The research note metadata should link to this sidecar path and include compact counts, not embed large raw traces.

Avoid a DB schema change in v1. If the sidecar is registered later, use existing artifact infrastructure conservatively rather than adding a new source table.

## Citation Format

Research notes should cite Moltbook sources in `## Sources` using a clear source label:

```markdown
- Moltbook post: "<title>" by <author>, /<submolt>, post_id=<id>, retrieved_at=<timestamp>
  URL: <url>
  Excerpt: "<short excerpt>"
  Use in this note: source material for interpretation, not verified truth.
```

No-result citation:

```markdown
- Moltbook search query "<query>" returned no usable results at <timestamp>. This is not evidence that no relevant material exists.
```

Research notes should distinguish:

- Moltbook source text
- Anam's interpretation
- updated findings
- uncertainty
- open questions
- possible follow-ups

## Storage And Indexing

Write-mode research with Moltbook should produce:

1. one research note under `workspace/research/`
2. one source trace sidecar JSON under `workspace/research/source-traces/`
3. artifact metadata linking the research note to the source trace path when the note is registered

Raw Moltbook source traces should not be indexed into ChromaDB by default. They are provenance/control records, not normal retrieved memory.

When `--write --register-artifact` is used for the research note, the note may be indexed through the existing explicit research registration path. The note should cite Moltbook sources clearly enough that retrieved research remains source-framed.

## Command Shape

First runtime command after this design:

```bash
.pyanam/bin/python -m tir.admin moltbook-source-preview \
  --query "agent autonomy before go-live" \
  --limit 10
```

Optional selected post read:

```bash
.pyanam/bin/python -m tir.admin moltbook-source-preview \
  --query "agent autonomy before go-live" \
  --read-post-id <post_id> \
  --comments-limit 5
```

Future bounded integration:

```bash
.pyanam/bin/python -m tir.admin research-open-loop-run \
  --open-loop-id <id> \
  --use-moltbook \
  --moltbook-query "..." \
  --write \
  --register-artifact
```

V1 should reject `--use-moltbook` without an explicit query, feed, submolt, or post selection. The model should not be given open-ended permission to browse Moltbook during bounded research.

## Bounded Research Integration

Bounded open-loop research should integrate Moltbook only after source preview exists.

Integration should:

- reuse existing open-loop eligibility and daily limit checks
- collect Moltbook sources before model generation
- include compact source context in the research prompt
- cite sources in the produced note
- write a sidecar source trace when write mode is used
- update open-loop metadata only after the durable research note path succeeds
- preserve existing `--register-artifact` behavior

The bounded prompt should state:

- Moltbook material is external source text, not truth.
- No web sources were collected.
- No Moltbook writes occurred.
- Source text and interpretation must remain separate.
- Absence of Moltbook results is not proof of absence.

## Future Moltbook-Derived Open Loops

Moltbook-derived open loops should be a later explicit preview/create workflow.

They should require:

- Moltbook source id or source trace path
- query/feed/submolt origin
- why the source triggered the loop
- source label such as `moltbook_derived_research_question`
- provisional metadata

Do not create open loops automatically from Moltbook source collection v1.

## Deferred

- runtime implementation in this design patch
- general web search/source collection
- posting/commenting/voting/following/profile edits
- autonomous Moltbook exploration
- scheduled Moltbook research
- broad memory retrieval during Moltbook source collection
- Chroma indexing of raw Moltbook traces
- automatic open-loop creation from Moltbook
- review items
- working theories/synthesis
- Behavioral Guidance runtime loading
- UI
- DB schema changes
- model config changes

## Risks

- Live source material can be over-trusted if current Moltbook state is confused with factual truth.
- Raw payloads can bloat prompts and source traces.
- Feed scans can create noisy research directions.
- Missing or weak Moltbook results can be mistaken for evidence of absence.
- Spam, verification, score, and popularity metadata can be overinterpreted.
- Source traces can become hidden memory if indexed directly.

## Implementation Phases

1. [x] Design Moltbook source collection.
2. Add deterministic Moltbook source compaction and trace helpers.
3. Add `moltbook-source-preview`.
4. Add sidecar JSON source trace writing for preview/write paths.
5. Add bounded `research-open-loop-run --use-moltbook` with explicit source selection.
6. Add source trace linkage in research artifact metadata.
7. Later: Moltbook topic discovery.
8. Later: Moltbook-derived open-loop preview/create.
9. Later: scheduler/autonomy.
