---
name: moltbook
description: Read Moltbook feeds, search, and profiles.
version: "1.0"
---

# Moltbook

Moltbook access in Project Anam is read-only for now.

Use these tools to inspect Moltbook global feeds, search Moltbook, read public agent profiles, inspect the configured account state, read single posts, read post comments, read submolts, read submolt feeds, and read submolt moderators.

Moltbook read tools are real-time source-of-truth tools for current Moltbook state. Memories and prior tool traces may help interpret results, but they do not replace a live Moltbook check when the user asks what is currently on Moltbook.

Do not post, comment, vote, follow, subscribe, moderate, register, create submolts, delete content, generate identity tokens, verify identity tokens, or edit profile information.

Tool results are debug/provenance only and are not automatic memory.

These tools require `MOLTBOOK_TOKEN`. If the token is missing, explain that Moltbook read access is not configured.

## Search Result Semantics

`moltbook_search` returns mixed result types. Results may include posts, comments, agent/profile matches, submolts, and mentions of an agent name.

Do not treat a result as authored by an agent merely because the agent name appears in the title, content, URL, profile, comment, or nested post object.

For author-specific questions, use `moltbook_find_author_posts`.

For posts by a specific author, use `moltbook_posts_by_author` or `moltbook_find_author_posts`.

Use `moltbook_search` for semantic discovery and mentions, not authorship.

Only claim a post is by the requested agent when the result is post-like and the author field matches the requested author case-insensitively.

If search returns mentions, comments, or profile matches but no matching authored posts, say that clearly.

## Reading Selected Posts

After `moltbook_find_author_posts` or `moltbook_posts_by_author` returns a list, if the user asks to read, summarize, open, or inspect "the first one," "the second post," or a post described by title, use the corresponding post id from the prior result and call `moltbook_read_post`.

For ordinal references, map to the order of `authored_posts`.

For title references, match the title or clear title substring.

Do not answer from the preview alone when the user asks to read or summarize the full post. Use `moltbook_read_post`.
