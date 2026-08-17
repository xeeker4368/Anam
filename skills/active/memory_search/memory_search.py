from tir.memory.retrieval import retrieve
from tir.tools.registry import tool


@tool(
    name="memory_search",
    description=(
        "Search indexed prior records and memories. Use this when you "
        "want to recall something specific from past conversations, prior records, "
        "or indexed experience."
    ),
    args_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The memory search query.",
            },
        },
        "required": ["query"],
    },
)
def memory_search(query: str) -> str:
    results = retrieve(query=query, max_results=5)

    if not results:
        # A statement about the SEARCH, never about the past. The previous
        # wording ("No indexed prior records found") reads as "no such record
        # exists", which is the conflation the automatic path's tri-state
        # marker was built to prevent — and this fires far more often since
        # the relevance floor shipped.
        #
        # Deliberately says only what this call site can actually observe:
        # `retrieve()` returns an empty list identically whether nothing
        # cleared the relevance floor OR both search legs failed, so any
        # stronger claim (e.g. "nothing scored above the threshold") would be
        # false in the failure case. See changelog/2026-08-17-memory-search-wording.md.
        return (
            "The memory search returned no results for that query. That is a "
            "fact about the search, not about the past — nothing closely "
            "matching was returned, which is not the same as nothing existing."
        )

    formatted = []
    for index, item in enumerate(results, start=1):
        metadata = item.get("metadata", {})
        source_type = metadata.get("source_type", item.get("source_type", "unknown"))
        created_at = metadata.get("created_at", item.get("created_at", "unknown date"))
        text = item.get("text", "").strip()
        if len(text) > 800:
            text = text[:797].rstrip() + "..."

        formatted.append(
            f"{index}. [{source_type} - {created_at}]\n{text}"
        )

    return "\n\n".join(formatted)
