# Web Source Collection Design

## Status

Design only. No runtime code, CLI commands, tests, database schema, Chroma indexing, prompt runtime, scheduler, UI, web tool behavior, bounded research behavior, guidance files, or model configuration are changed by this document.

The next implementation target after this design should be a standalone web source preview command. Bounded research integration should come later, after source preview proves compaction, provenance, citation, robots/paywall handling, and failure behavior.

## Purpose

Project Anam already has manual research notes, open-loop planning, bounded open-loop research, Moltbook source traces, and explicit Moltbook support in bounded research. General web source collection is still intentionally deferred.

This design defines the smallest safe model for collecting, compacting, citing, storing, and reasoning over public web sources before runtime web source collection is added to bounded research.

## Core Principles

- Web sources are external context, not factual authority.
- Search results are leads, not evidence.
- Fetched pages are source material, not truth.
- Source text must be separated from the entity's interpretation.
- Absence of web results is not proof of absence.
- HTTP failures, timeouts, DNS failures, TLS failures, provider failures, and malformed provider responses are collection failures, not no-results.
- Current-state or stale-sensitive claims require `retrieved_at` and source timestamps when available.
- Raw web source traces should not be indexed into ChromaDB by default.
- Research notes may reference source trace paths and may be indexed only through explicit registration.
- No browser automation in v1.
- No JavaScript rendering in v1.
- No login, cookie, private-profile, private-network, or authenticated web access in v1.
- No paywall bypass.
- Respect `robots.txt` where practical.
- Keep collection bounded, explicit, and auditable.

## Current Web Tool Inventory

The active web skill is `skills/active/web_search`.

It provides:

- `web_search(query, max_results=5)`: searches the configured SearXNG endpoint and returns normalized search-result snippets.
- `web_fetch(url, max_chars=12000)`: fetches and extracts readable text from one public HTTP/HTTPS page.

SearXNG configuration exists through:

- `TIR_SEARXNG_URL`
- `ANAM_SEARXNG_URL`
- default `http://127.0.0.1:8080`

`web_search` currently uses SearXNG JSON search and returns compact normalized records with:

- title
- URL
- snippet
- source domain

`web_fetch` already rejects:

- non-HTTP(S) URLs
- localhost URLs
- private, local, loopback, link-local, reserved, multicast, and unspecified IP URLs
- URLs with embedded credentials
- non-text content types
- oversized responses

`web_fetch` also:

- does not execute JavaScript
- does not follow redirects
- caps response bytes
- uses `trafilatura` extraction with visible-text fallback
- returns extracted text, title, source domain, truncation status, and URL

The chat runtime also has deterministic URL prefetch for URL-content questions. That path is useful for chat answers but is not a provenance/source-trace system. Web source collection should not reuse chat prefetch as durable research evidence without a separate trace layer.

## Topic Discovery Versus Source Collection

Web topic discovery asks what questions or leads may be worth researching.

Web source collection asks what source material supports one specific research pass. It must preserve query parameters, selected URLs, fetched page metadata, excerpts, retrieval time, source labels, omission reasons, and uncertainty.

V1 should implement source collection before web topic discovery. Search-driven topic discovery can create noisy open questions if source trace and citation behavior are not settled first.

## Recommended V1 Runtime Shape

The first runtime implementation after this design should be a standalone preview command, not bounded research integration:

```bash
.pyanam/bin/python -m tir.admin web-source-preview \
  --query "bounded research loop termination criteria" \
  --limit 10
```

Optional selected fetch should be explicit:

```bash
.pyanam/bin/python -m tir.admin web-source-preview \
  --query "bounded research loop termination criteria" \
  --fetch-url "https://example.com/article" \
  --write-trace
```

Search-only preview should collect compact search-result leads. Selected fetch should fetch only the explicitly selected public URLs.

Do not add bounded research integration in the first runtime patch. Bounded integration should consume the same source trace model later.

## V1 Allowed Tools

Use existing tool registry dispatch only:

- `web_search` for SearXNG search.
- `web_fetch` for explicitly selected public URLs.

Do not call SearXNG or target URLs directly from bounded research code. Keep provider behavior behind tool wrappers and the source preview layer.

Do not use:

- browser automation
- JavaScript rendering
- cookies
- login sessions
- private-network access
- file downloads
- crawling
- sitemap expansion
- automatic recursive link following

## Limits

Recommended v1 defaults:

- search results: default 10, max 20
- selected fetch URLs: default 0, max 3
- per-page excerpt: 1000 chars
- total fetched text budget: 12000 chars
- retry count: 0
- timeout: inherit existing `WEB_SEARCH_TIMEOUT_SECONDS`
- response byte cap: inherit existing `web_fetch` cap
- allowed schemes: `http`, `https`

Search results should not be auto-fetched in v1. Fetching should require explicit selected URLs.

If a later patch allows selected fetch by search rank, it should still make the selected URL list explicit in the trace.

## Search Result Compaction

Search results are leads. They should be compacted before entering a prompt or durable trace.

Recommended compact search-result shape:

```json
{
  "source_kind": "web_search_result",
  "tool_name": "web_search",
  "query": "bounded research loop termination criteria",
  "result_rank": 1,
  "title": "...",
  "url": "https://example.com/article",
  "domain": "example.com",
  "snippet": "...",
  "published_at": null,
  "retrieved_at": "...",
  "engine": "searxng",
  "score": null,
  "source_class": "unknown"
}
```

Search-result snippets should not be represented as full evidence. A research note may cite them as search leads only if the page was not fetched.

## Fetched Page Compaction

Fetched pages are source material, not truth. The trace should preserve enough metadata for citation and audit without storing full raw page text by default.

Recommended compact fetched-page shape:

```json
{
  "source_kind": "web_page",
  "tool_name": "web_fetch",
  "url": "https://example.com/article",
  "canonical_url": "https://example.com/article",
  "domain": "example.com",
  "title": "...",
  "retrieved_at": "...",
  "published_at": null,
  "last_modified": null,
  "status_code": 200,
  "content_type": "text/html",
  "robots_allowed": true,
  "robots_status": "allowed",
  "paywall_or_auth_wall": false,
  "content_excerpt": "...",
  "content_hash": "sha256:...",
  "extractor": "web_fetch_trafilatura_v1",
  "source_class": "unknown"
}
```

Do not include full extracted page text in preview records by default. Store excerpts and hashes for traceability.

## Source Class Labels

Source class labels are metadata, not truth scores.

Recommended labels:

- `official_documentation`
- `standards_rfc`
- `academic_paper`
- `news_article`
- `blog_opinion`
- `forum_social`
- `commercial_marketing`
- `unknown`

V1 may start with `unknown` unless a simple, auditable classifier exists. Do not use source class as a reason to treat a claim as true.

## Provenance And Source Trace Model

Each source collection run should produce a source trace object.

Recommended trace shape:

```json
{
  "collection_version": "web_source_collection_v1",
  "mode": "preview",
  "retrieved_at": "...",
  "query": "bounded research loop termination criteria",
  "selected_urls": [],
  "limit": 10,
  "tool_calls": [],
  "results": [],
  "fetched_pages": [],
  "omitted_count": 0,
  "omitted_reasons": [],
  "collection_error": false,
  "error_type": null,
  "status_code": null,
  "no_usable_results": false,
  "no_result_note": null,
  "no_external_write_confirmed": true,
  "web_sources_are_metadata_not_truth": true
}
```

Tool call metadata must be sanitized. Do not include Authorization headers, cookies, API tokens, raw headers, raw provider payloads, or full raw page bodies.

## Failure And No-Result Semantics

Use Moltbook-style source collection semantics:

- Timeout: `collection_error=true`, `error_type=timeout`
- DNS failure: `collection_error=true`, `error_type=dns_error`
- TLS failure: `collection_error=true`, `error_type=tls_error`
- SearXNG HTTP 500 or other provider server error: `collection_error=true`, `error_type=http_error`
- malformed SearXNG JSON: `collection_error=true`, `error_type=provider_error`
- registry/tool crash: `collection_error=true`, `error_type=tool_error`
- zero successful search results: `no_usable_results=true`
- robots-disallowed selected page: omitted or fetch-unavailable, not evidence of absence
- paywalled/auth-required selected page: omitted or fetch-unavailable, not evidence of absence
- selected page HTTP error: preserve status code and record fetch failure

Do not set `no_usable_results=true` for timeouts, DNS failures, TLS failures, provider failures, malformed provider responses, or other collection failures.

Recommended no-result note:

```text
No usable web results were returned. This is not evidence that no relevant material exists.
```

Recommended collection failure note:

```text
This is not evidence that no relevant web material exists.
```

## Robots Policy

Robots Exclusion Protocol is a standard site mechanism for crawler access preferences. Web source collection should respect `robots.txt` where practical.

Recommended v1 policy:

- Check `robots.txt` before selected fetch when practical.
- Record `robots_status` as `allowed`, `disallowed`, `unavailable`, or `not_checked`.
- If disallowed, do not fetch the page body.
- Record an omitted reason such as `robots_disallowed`.
- Do not treat robots-disallowed pages as absent.

If robots checking fails because the policy file is unavailable or times out, record the status. The runtime patch should decide whether to skip or proceed conservatively; the safer default is to skip when the policy cannot be determined for a selected fetch.

## Paywall, Auth Wall, And Private Page Policy

V1 must not bypass access controls.

Do not:

- use login sessions
- use browser cookies
- use saved browser profiles
- submit forms
- access private or internal pages
- bypass paywalls
- scrape content hidden behind authentication

If a selected page appears paywalled, login-gated, or unavailable, record:

- URL
- status code when available
- `paywall_or_auth_wall=true` when detected
- omitted reason such as `auth_required`, `paywall_or_auth_wall`, or `page_unavailable`

This is not evidence that no relevant material exists.

## Freshness

Every trace and compact source record must include `retrieved_at`.

Use `published_at` or `last_modified` only when available from tool output or reliable page metadata. If a page lacks a source timestamp, preserve `null` rather than guessing.

Research notes using web context should state when current-state claims may be stale, especially for:

- laws and regulations
- prices
- schedules
- product specs
- company leadership
- software versions
- breaking news
- safety or medical claims

## Citation Format

Fetched page citation:

```markdown
- Web page: "<title>", <domain>, <url>, retrieved_at=<timestamp>
  Excerpt: "<compact excerpt>"
  Use in this note: source material for interpretation, not verified truth.
```

Search lead citation when not fetched:

```markdown
- Web search result: "<title>", <domain>, <url>, retrieved_at=<timestamp>
  Snippet: "<snippet>"
  Use in this note: search lead only; page was not fetched.
```

No-result citation:

```markdown
- Web query "<query>" returned no usable results at <timestamp>. This is not evidence that no relevant material exists.
```

Collection failure citation:

```markdown
- Web source collection failed: <error_type>. This is not evidence that no relevant web material exists.
```

Research notes should distinguish:

- source text
- the entity's interpretation
- provisional findings
- uncertainty
- open questions
- follow-up needs

## Storage And Indexing

Recommended sidecar storage path:

```text
workspace/research/source-traces/YYYY-MM-DD-<query-slug>-HHMMSS.web-sources.json
```

Raw web source traces should not be registered as artifacts or indexed into ChromaDB by default. They are audit/provenance material.

Research notes may reference the source trace path. If a research note is explicitly registered, only the research note should go through existing artifact/indexing behavior unless a later patch explicitly changes source trace indexing.

No database schema change is needed for v1.

## Future Bounded Research Integration

Future explicit command shape:

```bash
.pyanam/bin/python -m tir.admin research-open-loop-run \
  --open-loop-id <id> \
  --use-web \
  --web-query "bounded research loop termination criteria" \
  --write \
  --register-artifact
```

Run-next shape:

```bash
.pyanam/bin/python -m tir.admin research-open-loop-run-next \
  --use-web \
  --web-query "bounded research loop termination criteria" \
  --write \
  --register-artifact
```

Validation should require:

- `--use-web` for any web flags
- `--web-query` or explicit selected URLs when `--use-web` is active
- bounded limits for result count and selected fetch count

Write-mode bounded research should:

- collect a web source trace
- write the trace sidecar
- inject compact web context into the bounded prompt
- write the research note
- register/index the research note only when explicitly requested
- update metadata only after durable success

Do not integrate web collection into bounded research until a separate runtime patch is approved.

## Deferred

Defer:

- runtime implementation
- bounded research integration
- scheduler/autonomy
- autonomous crawling
- browser automation
- JavaScript rendering
- login/cookie/private web access
- paywall bypass
- automatic open-loop creation from web
- working theories
- review items
- UI
- DB schema changes
- raw trace indexing
- broad source trust scoring
- source promotion to truth, self-understanding, behavioral guidance, project decisions, or stable memory

## Risks

- Search snippets may be misleading without fetch.
- SearXNG availability may vary.
- Upstream search engines can omit, rank, or rewrite results unpredictably.
- `web_fetch` extraction quality depends on page structure and static HTML availability.
- Robots checking adds latency and failure states.
- Paywall/auth-wall detection is heuristic.
- Source class labels can look like authority scores unless clearly documented as metadata.
- Current web tools are chat-oriented and need a source trace layer before research use.

## Implementation Phases

Recommended sequence:

1. Add this design document.
2. Implement standalone `web-source-preview` with search-only compact traces.
3. Add optional selected URL fetch with robots and unavailable-page handling.
4. Add optional `--write-trace` sidecar writing.
5. Add explicit bounded research `--use-web` integration.
6. Consider topic discovery after source collection is stable.
7. Consider scheduler/autonomy only after manual bounded behavior is reliable.

