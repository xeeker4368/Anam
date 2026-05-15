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
        return "No indexed prior records found for that query."

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
