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

When the user provides a public HTTP/HTTPS URL and asks what it says, asks for a summary, asks a question about the page contents, asks whether a claim about the page is accurate, or asks for details from the article/page, use `web_fetch` before answering.

Do not answer URL-content questions from the URL slug, search snippets, prior memory, or general model knowledge unless `web_fetch` fails.

If `web_fetch` fails, say the page could not be fetched, briefly explain the tool error, and only then offer to use `web_search` for related coverage if that would help.

If the user asks to find a source first, use `web_search` to identify candidate URLs, then use `web_fetch` on the selected likely source before making detailed claims about that page.
