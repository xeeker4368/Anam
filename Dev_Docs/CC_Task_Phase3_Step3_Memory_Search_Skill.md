# CC Task: Phase 3 Step 3 — Memory Search Skill

## What this is

The memory search skill is the entity's first tool. It lets her deliberately search her own memories mid-response — a conscious "let me look that up" action she takes during the agent loop.

This is different from automatic retrieval (which already works in `context.py`). Automatic retrieval injects relevant memories into her context before she starts generating. Memory search is an explicit action she takes when she decides she needs to find something specific.

The skill is a thin wrapper around the existing `retrieve()` function.

## Prerequisites

- Phase 3 Step 2 complete (Agent Loop)
- Phase 2 complete (retrieval pipeline working)
- Test data still in databases (the "dark purple" and "woodworking" conversations from Phase 2 verification)

## Read before writing

- `tir/memory/retrieval.py` — the `retrieve()` function this wraps
- `tir/tools/registry.py` — the `@tool` decorator and SKILL.md format

## Files to create

```
skills/
    active/
        memory_search/
            SKILL.md           ← NEW
            memory_search.py   ← NEW
```

No test file — the skill is too thin to test in isolation. Validation happens in the Step 4 smoke test.

---

## New file: `skills/active/memory_search/SKILL.md`

```markdown
---
name: memory_search
description: Search your own memories and past experiences. Use this when you want to recall something specific from past conversations, research, or other experiences.
version: "1.0"
capabilities:
  network: []
  filesystem:
    read: []
    write: []
  tools: []
fabrication_patterns:
  - "searched my memory"
  - "searched my memories"
  - "looked through my memories"
  - "checked my memories"
---
# Memory Search

## When to use

Use this tool when you want to deliberately search your own experiences
and memories for something specific. This is useful when:

- Someone asks about a past conversation
- You want to recall details about a topic you've discussed before
- You need to check what you know about a person or subject

## How it works

You provide a search query — a natural language description of what
you're looking for. The search checks both the meaning of your
experiences (semantic search) and the specific words used (lexical
search), then combines the results.

## Tips

- Use specific queries: "conversation about woodworking" works better
  than just "woodworking"
- Your regular memories (from conversations) are automatically included
  in your context when relevant. Use this tool when you want to search
  for something that wasn't automatically surfaced.
```

---

## New file: `skills/active/memory_search/memory_search.py`

```python
"""Memory search tool — explicit search of the entity's own substrate."""

from tir.tools.registry import tool
from tir.memory.retrieval import retrieve


@tool(
    name="memory_search",
    description="Search your own memories and past experiences. Use this when you want to recall something specific from past conversations, research, or other experiences.",
    args_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to search for in your memories",
            },
        },
        "required": ["query"],
    },
)
def memory_search(query: str) -> str:
    """Search memories and return formatted results.

    Calls the existing retrieve() pipeline (hybrid vector + BM25,
    RRF fusion, trust weighting). Formats the results as readable
    text that the model can reason about.

    Does not filter by active conversation — explicit search should
    find everything. Automatic retrieval (in context.py) handles
    active-conversation exclusion separately.
    """
    results = retrieve(query=query)

    if not results:
        return f"No memories found for: {query}"

    lines = [f"Found {len(results)} memories matching '{query}':\n"]

    for i, chunk in enumerate(results, 1):
        source_type = chunk.get("metadata", {}).get("source_type", "unknown")
        created_at = chunk.get("metadata", {}).get("created_at", "unknown date")
        text = chunk.get("text", "")

        # Truncate long chunks for readability
        if len(text) > 800:
            text = text[:800] + "..."

        lines.append(f"--- Memory {i} ({source_type}, {created_at}) ---")
        lines.append(text)
        lines.append("")

    return "\n".join(lines)
```

---

## Verify — registry loads the skill

```bash
cd /Users/localadmin/Tir
python3 -c "
from tir.tools.registry import SkillRegistry

registry = SkillRegistry.from_directory('skills/active/')
print(f'Skills: {len(registry._skills)}')
print(f'Tools: {len(registry._tools)}')
print(f'Has tools: {registry.has_tools()}')

tools = registry.list_tools()
print(f'Tool list: {tools}')
assert tools[0]['function']['name'] == 'memory_search'

desc = registry.list_tool_descriptions()
print(f'Descriptions:\\n{desc}')

print('PASS')
"
```

Expected: 1 skill, 1 tool, memory_search registered. PASS.

## Verify — skill returns results from existing test data

```bash
cd /Users/localadmin/Tir
python3 -c "
from tir.memory.db import init_databases
init_databases()

from skills.active.memory_search.memory_search import memory_search
result = memory_search(query='woodworking')
print(result[:500])
print('---')
print(f'Length: {len(result)} chars')
assert 'No memories found' not in result, 'Expected results but got none'
print('PASS')
"
```

Expected: Returns formatted memories about woodworking from the test data. PASS.

If the test data has been wiped, the second verify will show "No memories found" — that's OK, it means the skill works but there's nothing to find. The Step 4 smoke test with real Ollama is the definitive test.

## What NOT to do

- Do NOT modify `retrieval.py` — the skill calls it as-is
- Do NOT modify `context.py` — automatic retrieval stays unchanged
- Do NOT modify `routes.py` or `agent_loop.py` — integration is Step 4
- Do NOT add `active_conversation_id` filtering — explicit search finds everything

## What comes next

Step 4: Integration — wire the agent loop and registry into `routes.py` so she actually uses tools through the web UI.
