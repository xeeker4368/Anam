# Project Tír — Document Ingestion Design

*Design doc v1, April 2026. How external content (URLs, files, raw text) gets pulled into the entity's retrievable memory. Covers the `document_ingest` tool's behavior, content-extraction strategy, document chunking (distinct from conversation chunking), storage in the `documents` table, and retrieval framing.*

---

## Purpose

The entity reads articles. She'll eventually read books, emails, forum threads, peer-AI messages. Everything external she reads should be retrievable — "what did I learn about emergence?" should surface the article she read last week alongside the conversations where she discussed it.

Document ingestion is the pipeline that makes external content retrievable. It's one of the nine day-one tools (`document_ingest` in Tool Framework v1).

Responsibilities:

- Accept content from three sources: URL, local file, raw text.
- Extract clean text (especially from HTML).
- Store the document in working.db's `documents` table — metadata for the rebuild safety net.
- Chunk the document appropriately (character-based with overlap — different from conversation chunking).
- Write chunks to ChromaDB and chunks_fts.
- Return a useful result to the entity: document ID, chunk count, title as extracted.

Non-goals:

- PDF extraction. Day-one is plain text + HTML. PDF is its own beast (library choice, figure/table handling, scan-image OCR); deferred.
- Image ingestion. Text-only v1.
- Audio/video. Same.
- Automatic content summarization during ingestion. The documents table has a `summary` field and a `summarized` flag; overnight processes may populate those. Day-one ingest doesn't summarize.
- Recursive web crawling. One URL = one document. If she wants to follow links, that's another `document_ingest` call.
- Active-content rendering. No JavaScript execution, no waiting-for-SPA-to-hydrate. Static HTML only.

---

## Summary of decisions

1. **Three input modes.** `document_ingest` accepts exactly one of: `url` (HTTP fetch), `path` (local file read), or `content` (raw text provided by the caller, usually her own writings).
2. **Content extraction via `trafilatura` for HTML.** The standard Python tool for main-content extraction; produces clean text (or Markdown) from most articles.
3. **Plain-text files pass through unchanged.** File extension or MIME suggests format; `.md`, `.txt`, `.rst`, `.py`, etc., are read as-is.
4. **Chunking: 3000-character chunks with 300-character overlap.** Matches Aion's proven values. Paragraph boundaries respected where possible — don't cut mid-paragraph unless a paragraph is already longer than the chunk budget.
5. **No deduplication by URL.** Each ingestion creates a new document row. The content at a URL changes over time; each ingestion is a snapshot of what she saw at that moment. If this proves noisy in practice, revisit.
6. **Source type from the caller.** `document_ingest` takes an optional `source_type` argument defaulting to `"article"`. Allowed types are open-ended — the system doesn't enumerate.
7. **Source trust from the caller, defaulting to `thirdhand`.** External content is thirdhand by default; caller can override (e.g., when she ingests her own writing as `firsthand`).
8. **Documents table is metadata only — no content column.** ChromaDB holds the chunks. The documents table stores title, URL, source_type, chunk_count, and processing flags. The URL is preserved so the original source can be re-fetched if re-ingestion is ever needed. Storing extracted text alongside the chunks would be redundant writes for a re-chunking scenario that can be handled by re-fetching.
9. **Title extraction is best-effort.** If caller provides a title, use it. Otherwise, extract from HTML `<title>`, the first heading, the filename, or fall back to a timestamped generic title.
10. **Result is structured.** `ToolResult` rendered text tells her what she ingested (title, source, chunk count); the structured field carries document_id and chunk_ids for programmatic access.

---

## Tool shape

From the entity's perspective, `document_ingest` is one day-one tool. Its SKILL.md frontmatter arguments:

```yaml
arguments:
  type: object
  properties:
    url:
      type: string
      description: A URL to fetch and ingest. Use when ingesting web content.
    path:
      type: string
      description: A filesystem path to read and ingest. Must be within her workspace.
    content:
      type: string
      description: Raw text content to ingest directly. Use for her own writings.
    title:
      type: string
      description: Title for the ingested document. Optional; auto-extracted if not provided.
    source_type:
      type: string
      description: What kind of thing this is. Examples: article, paper, journal, note.
      default: article
    source_trust:
      type: string
      description: Trust level. One of firsthand, secondhand, thirdhand.
      default: thirdhand
    note:
      type: string
      description: Optional note about why she's ingesting this. Stored as document metadata.
  oneOf:
    - required: [url]
    - required: [path]
    - required: [content]
```

(The `oneOf` constraint is a hint; validation at the dispatcher level checks exactly one of url/path/content is present.)

---

## Ingestion pipeline

### Step 1: Fetch content

Based on which input was provided:

- **`url` provided:** HTTP GET via `urllib` (matching the minimal-dependency posture of the codebase). Timeout 60 seconds. Follow up to 5 redirects. User-agent string identifying the entity (`Tir-Entity/1.0`). Accept text/* and application/xhtml+xml; other content types rejected with an error result.
- **`path` provided:** Resolve the path against the entity's workspace root. Must not escape the workspace (reject any path containing `..` or starting with `/`). Read as UTF-8 text.
- **`content` provided:** Use as-is. No I/O.

Failures return a `ToolResult(success=False, rendered="...")` describing what went wrong. The entity sees it, reasons about it.

### Step 2: Extract clean text

- **HTML input** (URL fetch with `text/html` content-type, or file with `.html`/`.htm` extension): run through `trafilatura.extract(html, include_comments=False, include_tables=True, output_format='markdown')`. This produces clean text, preserving paragraph structure and tables, stripping navigation, ads, and footers.
- **Plain text input** (everything else, or `content` mode): use as-is.
- **If extraction fails** (trafilatura returns None — can happen on very-JS-heavy pages with no meaningful static content), fall back to the raw HTML-stripped text (BeautifulSoup's `.get_text()`). Log a warning. The ingestion still succeeds but the entity may get a noisier version.

### Step 3: Extract or accept title

- If `title` argument provided, use it.
- **URL + HTML:** look for `<title>` in the parsed HTML. If trafilatura has already stripped that, use its metadata output (`trafilatura.extract_metadata`).
- **Path:** use the filename without extension, with `_` and `-` converted to spaces and title-cased.
- **Content only (no title):** use `f"Ingested text ({iso_date})"`.

Always non-empty. Long titles are truncated to 200 characters with an ellipsis.

### Step 4: Persist the document

```sql
INSERT INTO documents (
    id, title, url, source_type, source_trust,
    chunk_count, created_at
) VALUES (?, ?, ?, ?, ?, 0, ?);
```

`id` is a fresh UUID. `url` is null for path/content ingests. `chunk_count` is 0 for now — updated after chunking. No content column — the documents table is metadata only; ChromaDB holds the actual content as chunks.

Note field from the caller is persisted as metadata — adding a `note TEXT` column to the documents table (schema v1.4 addition, or handled in the same schema update that adds `web_sessions`).

### Step 5: Chunk the document

Call `chunk_document(extracted_text, chunk_size=3000, overlap=300)`. Returns a list of chunk-text strings.

Algorithm (described below in detail): split on paragraph boundaries where possible, pack into ~3000-char chunks with 300-char overlap between adjacent chunks.

### Step 6: Write chunks to ChromaDB and chunks_fts

For each chunk (index 0, 1, 2…):

1. Compute `chunk_id = f"{document_id}_chunk_{chunk_index}"`.
2. Build metadata:
   ```python
   {
       "document_id": document_id,
       "chunk_index": chunk_index,
       "source_type": source_type,
       "source_trust": source_trust,
       "created_at": iso_now(),
   }
   ```
   Note: no `conversation_id`, no `user_id` (document chunks have neither). Metadata lacking these keys is fine — schema is open-ended.
3. Call `chroma.write_chunk(chromadb_path, chunk_id, chunk_text, metadata, ollama_host)`.
4. Call `chunks_fts.write_chunk_fts(working_path, chunk_id, chunk_text, metadata)`.

Same ordering (ChromaDB first, then FTS5) and same failure handling (log + continue) as other chunk writes.

### Step 7: Update document row

```sql
UPDATE documents SET chunk_count = ? WHERE id = ?;
```

Updates `chunk_count` to the actual number of chunks written.

### Step 8: Return

```python
ToolResult(
    success=True,
    rendered=(
        f"Ingested '{title}' ({len(chunks)} chunks). "
        f"Source: {source_description}."
    ),
    structured={
        "document_id": document_id,
        "title": title,
        "chunk_count": len(chunks),
        "source_type": source_type,
        "source_trust": source_trust,
    },
)
```

`source_description` is `"URL: <url>"`, `"file: <path>"`, or `"provided text"` depending on input mode.

---

## Chunking algorithm

### Target: 3000 characters per chunk, 300-character overlap

3000-char chunks embed well (within nomic-embed-text's context), are semantically meaty (several paragraphs typically), and aren't so long that retrieval returns sprawling context. 300-char overlap is enough to span a paragraph boundary without bloating storage.

### Paragraph-aware packing

Algorithm:

1. Split the input text on paragraph boundaries (`\n\n` or similar). Keep the delimiter as part of each paragraph so reassembly is exact.
2. Pack paragraphs into chunks sequentially. Start a new chunk when adding the next paragraph would exceed 3000 characters — unless the current chunk is empty, in which case the single (oversized) paragraph becomes its own chunk.
3. For overlap: when starting chunk N+1, include the last 300 characters of chunk N as the opening of chunk N+1. The overlap is character-level, not paragraph-level — acceptable because the overlap is a search-aid, not meant to be readable prose.

Edge cases:

- **Empty input:** no chunks. Return `[]`. The caller (document_ingest pipeline) still creates a document row with chunk_count=0; the document exists as a zero-chunk record.
- **Input shorter than 3000 characters:** one chunk, no overlap needed.
- **A single paragraph longer than 3000 characters:** it becomes its own chunk (oversized). Overlap with the next chunk happens normally at the tail.

### Alternative considered: pure character-count splitting with paragraph awareness only as a tie-breaker

Simpler algorithm: split every 3000 chars with 300-char overlap, but try to back up to the nearest paragraph boundary (up to some slack like 500 chars) if the raw split falls mid-paragraph.

Both work. Paragraph-aware packing is easier to read and debug; pure character splitting with paragraph-pullback is slightly more uniform in chunk size. Either is fine. Implementation chooses; no practical difference in retrieval quality.

---

## Chunk text format

**No framing header added at chunk creation time.** Unlike conversation and autonomous-session chunks, document chunks don't have a "Task:" preamble or timestamp header. The chunk text is just the document's content.

Why: document content reads as prose. Adding `[Article titled "..."]\n\n{text}` to every chunk duplicates context that's already in metadata. CC v1.1's rendering adds the framing header (`[External source you read: {title}, ingested {date}]`) at context-construction time; the raw chunk text stays clean.

This diverges from conversation and autonomous chunks (which embed the user-name / task-title in the text to survive renames/deletions). Documents have a different provenance — the title and URL live in the documents table and don't mutate the same way. If a document's title is edited later, retrieved chunks won't reflect it, but that's acceptable because documents are typically not renamed.

**If that's wrong and document titles do change, embed title in chunk text.** Flag as open question.

---

## Metadata per chunk

```python
{
    "document_id": document_id,
    "chunk_index": chunk_index,
    "source_type": source_type,        # "article", "paper", "journal", etc.
    "source_trust": source_trust,      # default "thirdhand"
    "created_at": iso_now(),
}
```

Absent: `conversation_id`, `user_id`, `task_id`, `message_count`. Schema is open; missing keys are fine.

chunks_fts row gets: `chunk_id`, `text`, `conversation_id=NULL`, `user_id=NULL`, `source_type`, `source_trust`, `created_at`.

---

## Duplicate ingestion

If the same URL (or same file) is ingested twice, each gets a new `document_id`, a new set of chunks with new IDs, new ChromaDB entries, new chunks_fts rows.

**This is intentional.** The content at a URL can change; a re-ingest captures "what it looked like this time." Each ingestion is a snapshot. Retrieval may surface multiple versions of the same article — that's fine; the entity reads them and sees that she's looked at this source multiple times.

**Cost:** storage grows linearly with re-ingests. For a personal project, bounded and cheap.

**If it becomes noisy:** add a `superseded_by` column to documents or similar mechanism for the entity to mark older versions. Not needed day-one.

---

## Retrieval framing for document chunks

Per Context Construction v1.1:

```
article chunks:
[External source you read: {title}, ingested {date}]
{raw chunk text}
```

The title and date come from document row metadata at context-construction time (via a join using `document_id` from chunk metadata). This is a per-retrieval lookup. Acceptable cost for document chunks (tens of retrievals per turn, one join each).

**Alternative: embed title in chunk text.** Would eliminate the join. Tradeoff is the title-mutability concern above. Day-one keeps the join; revisit if it matters.

For other source types (journal, research — if they ever go through document_ingest rather than a dedicated journal tool), CC v1.1 already has per-source framings.

---

## The entity's experience

She calls `document_ingest(url="https://example.com/article")`. Ten seconds later, the tool result comes back: `"Ingested 'Foo et al. 2024: Collective identity in cooperative agents' (12 chunks). Source: URL: https://example.com/article."`

She can reference it immediately: `memory_search(query="collective identity")` will now return chunks from the article alongside her conversation history. The retrieval is unified.

She may choose to call `document_ingest` with `content="..."` on her own reflections — "I want to preserve this thought." That's firsthand ingestion; framed as journal or research depending on source_type. This path is how journals get created day-one (no separate `journal_write` tool until we see one earn its keep).

---

## Workspace-file ingestion

The `path` mode is sandboxed to the workspace root (`config.workspace_path`). Paths escaping the workspace (via `..`, absolute paths, symlinks leading out) are rejected.

Why the sandbox: so a misbehaving agent loop can't pull /etc/passwd into memory. Defense-in-depth even though the system isn't internet-exposed.

Resolving paths:

```python
resolved = os.path.realpath(os.path.join(workspace_root, path))
if not resolved.startswith(workspace_root + os.sep):
    return ToolResult(success=False, rendered=f"Path '{path}' is outside the workspace.")
```

This pattern handles `..`, absolute paths, and symlinks via `realpath`. The sep-suffix check prevents prefix-matching false positives (`/workspace-evil` starting with `/workspace`).

---

## Error modes

Each step can fail. Each should return a `ToolResult(success=False, rendered="...")` with a clear message. Specific cases:

- **URL returns non-2xx status.** `"Fetching {url} returned status {code}. Try a different URL."`
- **URL times out.** `"Fetching {url} timed out after 60 seconds."`
- **URL returns non-text content.** `"The content at {url} is {mime_type}, which I can't ingest as text."`
- **File not found.** `"No file at {path} in my workspace."`
- **File too large (say, >10 MB).** `"The file at {path} is too large ({size} bytes) to ingest."`
- **Extraction failure AND fallback failure.** `"I couldn't extract readable text from that source."`
- **Chunking failure (shouldn't happen; defensive).** `"Something went wrong chunking that content: {error}."`
- **ChromaDB or chunks_fts write failure.** Document row exists but chunks are missing. Log error, return partial success with warning. The document is recoverable via a re-chunk utility.

Every failure message is informational, not instructive ("try a different URL" is descriptive, not a directive to her). She reads, reasons, tries again or moves on.

---

## Configuration

- `chunk_size = 3000` — tunable.
- `chunk_overlap = 300` — tunable.
- `fetch_timeout_seconds = 60` — tunable.
- `max_file_bytes = 10_000_000` (10 MB) — tunable.
- `workspace_path = "./data/workspace/"` — from EngineConfig.
- `user_agent = "Tir-Entity/1.0"` — configurable.
- `trafilatura` extraction options: `include_comments=False, include_tables=True, output_format='markdown'` — configurable if behavior shows issues.

---

## What this design does NOT decide

- **Journal-specific ingestion flow.** Could be a dedicated `journal_write` tool that writes + ingests in one step, with special source_type and maybe different chunk parameters. Deferred — `document_ingest(content=..., source_type="journal", source_trust="firsthand")` covers it for now.
- **PDF/image/audio ingestion.** Text only v1. PDF via `pypdf` or similar is a plausible phase-2 addition.
- **Automatic summarization at ingest time.** The documents table supports a `summary` and `summarized` flag; an overnight process may populate them for UI display. Not part of the ingestion tool's work.
- **Ingestion from peer AIs (Moltbook).** Future source type. Covered by `source_type="peer_message"` when that capability lands. The ingestion pipeline doesn't need to know — it's just another ingestion.
- **Automatic re-ingestion / freshness checks.** If a URL's content changes, the entity won't know unless she re-ingests. Day-one has no polling or scheduled re-fetch.
- **De-duplication by content hash.** Could detect "this text is identical to content I already ingested" and skip. Not day-one.
- **Related-documents surfacing at ingest time.** "Here are three articles you've read that cover similar material." Nice to have, not day-one.

---

## Settled questions

**Requirement 28 (original content preserved alongside chunks).** For URL ingestion, the extracted text lives in ChromaDB as chunks and the source URL is preserved in the documents table for re-fetching. For path-based ingestion, the caller retains the source file. For content-based ingestion, the caller provided the text directly. In all cases, the combination of chunks + source reference satisfies the requirement's intent without storing redundant full text in working.db.

---

## Open questions

**a. Should document titles be embedded in chunk text?** Day-one keeps title in the documents table, joined at context-construction time. If documents get renamed (admin action, or a tool that edits metadata), existing chunks reflect the new title on next retrieval — arguably what you want. Conversation/autonomous chunks embed names because deletions and renames happen on changing substrate. Document titles are more stable. Keep the join; revisit if behavior warrants.

**b. `note` field in the documents table — schema impact.** Adding `note TEXT` to the documents table is a small schema change. Bundle with other schema additions (web_sessions, tasks table) into schema v1.4 rather than piecemeal.

**c. Deduplication policy.** Re-ingesting a URL creates a new document by default. If noise in retrieval becomes a problem, we'll need a policy — dedupe on URL identity, on content hash, or manual supersede. Flag.

**d. Trafilatura fallback strategy.** Day-one fallback to BeautifulSoup's raw text. If the site is JS-heavy and both fail, ingestion produces noise. Consider: headless browser for ingestion as a fallback. Not day-one; expensive.

**e. Chunk size for very short documents.** A tweet-length "document" is 200 characters; becomes one chunk. Retrievable, but BM25 on tiny chunks behaves oddly (every term matches). May want a minimum chunk size or minimum document size. Flag.

**f. Content-type detection.** `application/pdf` is excluded day-one with a "can't ingest" message. Verify that the content-type string variants ("application/pdf; charset=binary", etc.) are all caught by a startswith check.

**g. Character encoding on file reads.** UTF-8 default. Files with other encodings (BOM, Latin-1, etc.) either decode with errors or fail. Day-one: best-effort UTF-8 with `errors='replace'`. If specific encoding issues appear, add detection via `chardet` or similar.

---

## Cross-references

- **Schema Design v1.4** — the `documents` table this ingestion populates. Chunk metadata fields (document_id, chunk_index) come from here.
- **Chunking Strategy v1.1** — the conversation counterpart. This doc's chunking is deliberately different (char-based with overlap vs. turn-based no overlap).
- **Retrieval Design v1** — retrieves document chunks alongside everything else via the unified vector + BM25 path.
- **Context Construction v1.1** — frames retrieved document chunks as `[External source you read: {title}, ingested {date}]`.
- **Tool Framework v1** — `document_ingest` is one of nine day-one tools.
- **Skill Registry & Dispatch v1** — the tool's SKILL.md and entry point follow that pattern.
- **Autonomous Chunking Design v1** — mentions that autonomous session outputs (files she writes) go through document ingestion, not autonomous chunking.
- **Guiding Principles v1.1** — Principle 3 (store experiences; extracted articles are honest experience-representations, not summaries), Principle 7 (retrieval determines intelligence; ingest well to retrieve well), Principle 9 (the entity experiences calling the ingest tool — she sees what she ingested, chunk count, title).

---

*Project Tír Document Ingestion Design · v1 · April 2026*
