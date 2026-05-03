---
name: web_search
description: Search and fetch public web information.
version: "1.0"
---

# Web Search and Fetch

Use `web_search` for current outside-world information, changing facts, URLs or public resources that need lookup, and public information that is not available in memory.

Do not use it for internal Project Anam facts when surfaced memory, current context, or `memory_search` is sufficient.

This is search only, not page fetching. Search snippets are leads, not full verification. If results are weak, stale, contradictory, or only snippet-level, state uncertainty.

Use `web_fetch` to read one selected public HTTP/HTTPS page after `web_search` returns a candidate URL or when the user gives a specific public URL.

`web_fetch` is not a crawler, browser, file downloader, or automation tool. It fetches one URL, extracts readable text when possible, and does not execute scripts. Do not use it for localhost, private-network, or internal Project Anam resources.
