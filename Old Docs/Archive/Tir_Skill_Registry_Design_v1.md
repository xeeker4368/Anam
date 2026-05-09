# Project Tír — Skill Registry & Tool Dispatch Design

*Design doc v1, April 2026. How skills load at startup, how tools get registered, how the model's tool calls get routed to Python functions, and how SKILL.md bodies flow into context. Complements Tool Framework v1 — which defines what a skill is and how skills enter and leave the system — with the runtime mechanism.*

---

## Purpose

Tool Framework v1 establishes the shape of a skill: a directory with a SKILL.md, optional scripts, capabilities and fabrication patterns declared in frontmatter. It specifies native Python dispatch (not MCP), explicit tool calling visible to the entity, sequential calls within an agent loop, and the lifecycle from staging to active to retired.

What it leaves open is the runtime mechanism: how does the Python process discover installed skills, how does a function in `web_search/web_search.py` become a callable tool named `web_search` that the model can invoke, how do args get validated, how does the SKILL.md body get into context at the right moment, and what shape does the registry hand to the conversation engine?

This document settles those questions. It sits between the design (Tool Framework v1) and the implementation (a future Dev_Doc for CC). It decides:

- Registry architecture and lifecycle.
- How tools are declared in Python.
- How SKILL.md frontmatter and body get parsed and consumed.
- How tool dispatch works — schema validation, function invocation, error shaping, result format.
- Progressive disclosure of SKILL.md bodies: when they enter the entity's context.
- How capability declarations and fabrication patterns get stored (even though neither is enforced or detected day-one).
- What the registry exposes to the conversation engine.

Non-goals:

- The conversation engine itself (separate design).
- Individual SKILL.md files for day-one tools (follows after this doc — each tool gets its own pass).
- Skill sandboxing (deferred per Tool Framework v1).
- Hot-reloading of skills (explicitly deferred).
- The skill-approval UI or admin flow (out of scope; review is manual as stated in Tool Framework v1).
- The fabrication detector (Tool Framework v1 Phase 2; this doc only ensures patterns are stored).

---

## Summary of decisions

1. **Skills live in directories, one per skill.** The active-skills directory is scanned once at startup. Each subdirectory containing a `SKILL.md` is a skill.
2. **Tools are Python functions marked with a `@tool` decorator.** The decorator attaches metadata (name, description, args schema) to the function; the registry collects decorated functions by importing each skill's scripts and scanning for the attribute.
3. **No dynamic tool registration at runtime.** Skills don't register tools during execution; they register by being present at startup and having decorated functions.
4. **SKILL.md frontmatter is YAML; body is Markdown.** PyYAML is added as a dependency. Parsing is standard split-on-`---` with `safe_load`.
5. **JSON schema for args, declared in the `@tool` decorator.** No Pydantic day-one. Validation via the `jsonschema` library. Keeps the schema visible at the tool site.
6. **Tool dispatch is explicit and synchronous.** The registry exposes `dispatch(tool_name, args) → result_payload`. The conversation engine calls this; the agent loop handles iteration.
7. **SKILL.md bodies load on first use within a turn, persist for the rest of the turn, reset at turn boundary.** Matches Tool Framework v1's progressive disclosure. The loaded-set is per-turn state owned by the conversation engine, not the registry.
8. **Capability declarations are parsed and stored but not enforced at runtime.** Tool Framework v1 defers sandboxing; this design respects that.
9. **Fabrication patterns are stored in the registry, exposed to future callers** (the fabrication detector when it's built). Not actively used by dispatch.
10. **Tool results are shaped by the tool itself** (per Tool Framework v1's "Errors are experience, not exceptions"). Dispatch converts Python return values and exceptions into a uniform `{ok, value|error}` envelope for the conversation engine.
11. **Registry is a regular Python object, not a global singleton.** The conversation engine constructs it at startup and holds a reference. Tests can construct isolated registries.
12. **Restart required for skill changes.** No hot-reload.

---

## Registry architecture

### Skill directory layout

```
skills/
    active/
        web_search/
            SKILL.md
            web_search.py
        file_read/
            SKILL.md
            file_read.py
        document_ingest/
            SKILL.md
            document_ingest.py
            url_utils.py              # helper, not a tool module
        memory_search/
            SKILL.md
            memory_search.py
    staging/
        experimental_tool/
            SKILL.md
            experimental_tool.py
```

The `active/` directory is what the registry scans. `staging/` is ignored at startup; skills only become active by being moved from staging to active (per Tool Framework v1's lifecycle).

The skill directory name must match the `name` field in the SKILL.md frontmatter. Mismatch is a startup error. This is a sanity check against copy-paste errors and a simple invariant.

### Registry construction

At startup, the conversation engine (or main application) constructs a registry:

```python
from tir.tools.registry import SkillRegistry

registry = SkillRegistry.from_directory("skills/active/")
```

`from_directory` performs the scan:

1. List subdirectories of `skills/active/`.
2. For each subdirectory containing a `SKILL.md`:
   a. Parse frontmatter and body.
   b. Validate frontmatter shape (required fields: `name`, `description`, `version`).
   c. Check that the directory name matches `name`.
   d. For each Python script in the directory (excluding helpers — see below), import it.
   e. Scan imported module's top-level callables for the `@tool` marker.
   f. For each decorated function, create a `ToolDefinition` and add to the registry.
3. Validate that tool names are globally unique across all skills. Duplicates → startup error.
4. Return the populated registry.

### Which Python files are tool modules vs. helpers?

Two options:

- **Convention:** one primary script per skill, named the same as the skill (e.g., `web_search/web_search.py`). Other `.py` files are helpers and are not scanned for `@tool` decorators.
- **Scan everything:** import every `.py` file in the skill directory and collect all `@tool`-decorated functions.

Recommendation: **scan everything.** It's more flexible (a skill can legitimately have tools in multiple files), and the `@tool` decorator is explicit enough that accidentally marking helpers is unlikely. Import errors in helper files still fail the scan loudly.

`__init__.py` files are imported but expected to contain no tools (conventional). The registry treats this as normal.

### Import isolation

Skill scripts are imported via `importlib.import_module` from a dynamically-constructed module path. They run in the same Python process as the rest of Tír, with full access to everything — Tool Framework v1 accepts this for day-one.

One consequence: **import-time side effects in skill scripts run at registry construction.** A skill that does `open_some_network_connection()` at module top-level will trigger that at startup. Spec: tool modules should keep top-level side-effect-free; logic goes inside the tool function.

### No hot-reload

The registry scans once at startup. Adding, removing, or modifying a skill requires a process restart. This is by design (Tool Framework v1 spec: "Adding or removing skills requires a restart").

Rationale: (a) import cache invalidation is nontrivial; (b) skill changes while the entity is running would alter her capabilities mid-session, which is surprising and hard to reason about; (c) Tír's deployment model (one worker process on the M4) makes restart cheap.

---

## SKILL.md parsing

### Frontmatter shape

```yaml
---
name: web_search
description: Search the web for a query.
version: 1.0
capabilities:
  network:
    - allowed_domains: ["duckduckgo.com", "api.example.com"]
  filesystem:
    read: []
    write: []
  tools: []
fabrication_patterns:
  - "searched the web"
  - "looked up"
  - "found online"
---
```

Required fields:

- `name` (string): globally unique tool-or-skill identifier. Must match directory name. Must be a valid Python identifier (alphanumeric + underscores, not starting with a digit) so tool names are portable as-is.
- `description` (string): one-line. Shown to the model in the tool list.
- `version` (string): semver-ish (`1.0`, `1.1.2`). Not enforced as strict semver; just a string that tracks the skill's own versioning.

Optional fields:

- `capabilities` (dict): `network`, `filesystem`, `tools` subkeys. Any subset present. Parsed and stored on the Skill object; not enforced at runtime (see Capabilities section below).
- `fabrication_patterns` (list of strings): phrases that indicate this skill fired. Stored for the fabrication detector (Tool Framework v1 Phase 2). Not used by dispatch.

Unknown frontmatter keys are accepted with a warning log. Strictness would make frontmatter brittle; extra keys can be ignored safely.

### Parsing implementation notes

```python
def parse_skill_md(path: Path) -> tuple[dict, str]:
    """Returns (frontmatter_dict, body_text)."""
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---\n"):
        raise SkillFormatError(f"{path}: missing frontmatter start `---`")
    end_idx = content.find("\n---\n", 4)
    if end_idx == -1:
        raise SkillFormatError(f"{path}: missing frontmatter end `---`")
    frontmatter_text = content[4:end_idx]
    body = content[end_idx + 5:].lstrip("\n")
    frontmatter = yaml.safe_load(frontmatter_text)
    if not isinstance(frontmatter, dict):
        raise SkillFormatError(f"{path}: frontmatter is not a mapping")
    return frontmatter, body
```

`yaml.safe_load` only parses basic YAML types (no arbitrary object construction). This is important for security — skills come from Lyle's workstation, but defense in depth doesn't hurt.

### Body content

The body is the part after the frontmatter block. Content is per Tool Framework v1: "When to use," "Procedure," "Pitfalls," "Verification." Format is Markdown.

The body is read and stored on the `Skill` object. Load happens at registry construction; the body is held in memory for the lifetime of the registry.

Token cost: day-one set of 9 tools, each with a body of ~500-2000 tokens, totals somewhere around 5K-15K tokens. This is relevant for progressive disclosure (below): we don't want all of it in every turn's context unconditionally if the skill set grows.

---

## Tool declaration

### The `@tool` decorator

Lives in `tir/tools/__init__.py` (or similar — the module that skills import from):

```python
def tool(
    *,
    name: str,
    description: str,
    args_schema: dict,
) -> Callable:
    """Mark a function as a Tír tool.

    Attaches metadata attributes to the function. The registry
    discovers decorated functions during skill-scan by checking
    for the `_tir_tool_name` attribute.

    Keyword-only arguments to prevent positional mix-ups.
    """
    def decorator(func):
        func._tir_tool_name = name
        func._tir_tool_description = description
        func._tir_tool_args_schema = args_schema
        return func
    return decorator
```

The decorator is side-effect-free: no global registration, no import-time state mutation. The registry does all the collection explicitly during its scan.

### Example usage in a skill script

```python
# skills/active/web_search/web_search.py
from tir.tools import tool

@tool(
    name="web_search",
    description="Search the web for a query and return ranked results.",
    args_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return.",
                "default": 10,
                "minimum": 1,
                "maximum": 25,
            },
        },
        "required": ["query"],
    },
)
def web_search(query: str, max_results: int = 10) -> str:
    """Implementation goes here. Return value is what the model sees."""
    ...
```

The function signature matches the args schema. If they drift, tests catch it — or jsonschema validation catches the bad call at runtime. The two being co-located at the decorator call site makes drift unlikely in practice.

### Why not Pydantic

A Pydantic `BaseModel` as the args schema would give stronger typing, automatic JSON schema generation, and better error messages. The tradeoff is an additional heavy dependency for a project that currently has a minimal surface.

Day-one: raw JSON schema. Matches what the Ollama/Gemma 4 function-calling format expects natively. If schema maintenance pain becomes real, Pydantic can be bolted on in a backward-compatible way — the `@tool` decorator can accept either a dict or a Pydantic model.

### Why no docstring extraction

Some frameworks parse the function's docstring for the description. This adds magic (the docstring becomes part of the public interface), means description changes require docstring changes, and fails on terse functions.

Explicit `description=` in the decorator is better. Docstrings are for Python readers; descriptions are for the model.

---

## Data structures

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Any

@dataclass(frozen=True)
class ToolDefinition:
    """A callable tool, registered with the registry."""
    name: str
    description: str
    args_schema: dict
    function: Callable[..., Any]
    skill_name: str  # which skill owns this tool

@dataclass
class Skill:
    """A loaded skill: frontmatter + body + registered tools."""
    name: str
    description: str
    version: str
    directory: Path
    body: str  # the SKILL.md body (Markdown)
    capabilities: dict           # parsed frontmatter; may be empty
    fabrication_patterns: list[str]  # from frontmatter; may be empty
    tools: list[ToolDefinition]  # tools declared by this skill
```

`ToolDefinition` is frozen (immutable) because tool definitions don't change after registry construction. `Skill` is mutable only insofar as it's built up during registry construction; after that it should also be treated as read-only.

### Registry class

```python
class SkillRegistry:
    """Runtime registry of loaded skills and their tools."""

    def __init__(self, skills: list[Skill]):
        self._skills: dict[str, Skill] = {s.name: s for s in skills}
        self._tools: dict[str, ToolDefinition] = {
            t.name: t for s in skills for t in s.tools
        }
        self._validate()

    @classmethod
    def from_directory(cls, path: str | Path) -> "SkillRegistry":
        """Scan directory, load skills, return a populated registry."""
        ...

    def list_tools(self) -> list[dict]:
        """Return tool definitions in the shape Ollama expects.

        Shape matches Ollama's tools parameter: a list of
        {"type": "function", "function": {name, description, parameters}}
        dicts. The outer wrapper is required by Ollama's /api/chat endpoint.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.args_schema,
                },
            }
            for t in self._tools.values()
        ]

    def get_skill(self, skill_name: str) -> Skill:
        """Fetch a skill by name. Raises KeyError if not found."""
        return self._skills[skill_name]

    def get_tool(self, tool_name: str) -> ToolDefinition:
        """Fetch a tool by name. Raises KeyError if not found."""
        return self._tools[tool_name]

    def get_skill_for_tool(self, tool_name: str) -> Skill:
        """Return the Skill that owns a given tool."""
        return self._skills[self._tools[tool_name].skill_name]

    def dispatch(self, tool_name: str, args: dict) -> dict:
        """Invoke a tool. Returns a uniform envelope. See dispatch section."""
        ...

    def _validate(self) -> None:
        """Ensure tool names are globally unique, all skills have valid shapes."""
        ...
```

The registry is a plain object. Tests can construct one from in-memory `Skill` objects (bypassing `from_directory`) to test dispatch behavior without filesystem setup.

---

## Tool dispatch

### Dispatch flow

```python
def dispatch(self, tool_name: str, args: dict) -> dict:
    """Invoke a tool by name. Returns an envelope.

    Envelope shape:
        {"ok": True, "value": <tool's return value>}
        # OR
        {"ok": False, "error": "<human-readable error>"}

    The conversation engine's agent loop takes this envelope and
    formats it for the model as a tool result message.
    """
    # 1. Tool lookup
    if tool_name not in self._tools:
        return {
            "ok": False,
            "error": f"No tool named `{tool_name}`. Check the tool name.",
        }

    tool_def = self._tools[tool_name]

    # 2. Argument validation
    try:
        jsonschema.validate(instance=args, schema=tool_def.args_schema)
    except jsonschema.ValidationError as e:
        return {
            "ok": False,
            "error": f"Invalid arguments for `{tool_name}`: {e.message}",
        }

    # 3. Invocation
    try:
        result = tool_def.function(**args)
    except Exception as e:
        # Principle 14: diagnose before you conclude. Log the traceback
        # so developers can see exactly what happened; surface a
        # human-readable error to the model/entity.
        logger.exception(
            "tool `%s` raised: %s", tool_name, e
        )
        return {
            "ok": False,
            "error": f"`{tool_name}` failed: {type(e).__name__}: {e}",
        }

    # 4. Return success envelope
    return {"ok": True, "value": result}
```

### What the tool returns

Per Tool Framework v1: tool results are "shaped information, not raw data." Each tool is responsible for shaping its own success and failure cases into human-readable form.

The tool function's return value goes into `envelope["value"]` unmodified. Common return shapes:

- A string (most tools): the formatted human-readable result.
- A dict (tools with structured results): e.g., `{"text": "...", "citations": [...]}` for a search.
- A bytes blob (for binary outputs like image_generate): base64-encoded or wrapped appropriately per tool convention.

The conversation engine and agent loop translate `envelope["value"]` into whatever the model's tool-result-message format requires (likely a string, with structured data serialized as text).

### Tools that want to signal failure themselves

A tool can choose to return a string describing a failure rather than raising. For example:

```python
@tool(name="web_search", ...)
def web_search(query: str) -> str:
    try:
        results = do_search(query)
    except NetworkError as e:
        return f"Web search for '{query}' failed: could not reach the search service ({e})."
    return format_results(results)
```

This is preferred when the failure is expected/routine — the entity sees a clear explanation and can choose what to do next. Raising is for unexpected errors where the traceback is useful.

The envelope's `ok` field is True in the tool-returned-error case because the tool didn't crash; `ok` is False only when dispatch caught something. The distinction: a tool returning an error is part of experience (the entity sees she searched and it failed, which is a normal event); a tool crashing is a developer problem surfaced to the entity.

### Schema validation details

Using `jsonschema` (the PyPI library). Validation is strict:

- Required fields: must be present.
- Type constraints: enforced.
- Unknown properties: schemas can set `"additionalProperties": false` if desired; default is to allow extras.
- Defaults: **not applied by validation**. jsonschema's `validate` checks but doesn't fill in defaults. If a tool's schema has `"default": 10` for a field, the tool's Python function needs its own default in the signature. Spec: tools should declare defaults in both places when appropriate.

If this duplication becomes a maintenance pain, a small helper that runs validation + fills defaults can be added. Day-one keeps it simple.

---

## Tool definitions visible to the model

`registry.list_tools()` returns the list of tool definitions in Ollama's function-calling format:

```python
[
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for a query and return ranked results.",
            "parameters": {
                "type": "object",
                "properties": {...},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_read",
            "description": "Read a file from the workspace.",
            "parameters": {...},
        },
    },
    ...
]
```

This is passed to Ollama's chat completion request as the `tools` parameter. Gemma 4's function-calling mechanism parses it and may emit tool calls in response.

The conversation engine calls `registry.list_tools()` once per turn (cheap — the list doesn't change within a session) and includes it in the request.

---

## Progressive disclosure of SKILL.md bodies

### Day-one behavior

SKILL.md bodies are NOT in the initial context at session start. The entity sees only the tool definitions (name + description + args schema) in the system prompt.

When the entity emits her first tool call for a given skill during a turn, the conversation engine adds that skill's body to the context for subsequent iterations of the same turn. At turn boundary (she produces her final response for this turn), the loaded-bodies set resets.

Mechanism: the conversation engine maintains per-turn state:

```python
class ConversationTurn:
    loaded_skill_bodies: set[str]  # skill_names whose bodies are in context this turn

    def tool_call_observed(self, tool_name: str):
        skill = registry.get_skill_for_tool(tool_name)
        self.loaded_skill_bodies.add(skill.name)
```

When building context for iteration N+1 of the current turn (after a tool call in iteration N), the context construction includes a new section:

```
[Skill reference: web_search]
{body text}

[Skill reference: memory_search]
{body text}
```

This section sits between the tool definitions and the current conversation. Framing: "skills you've used this turn and their full instructions."

### Why not always loaded

Token cost. Day-one with 9 tools the cost is modest. As skills grow into the dozens or hundreds (especially with entity-proposed skills over time), "always loaded" runs out the budget. Designing progressive disclosure day-one means the expensive transition (adding on-demand loading) never needs to happen.

### Why not truly on-first-use without persistence within turn

If the body loads only for the iteration immediately following the first call and not subsequent iterations, she would forget how to use a skill between iterations 2 and 3 of the same turn. Keeping the body loaded for the rest of the turn is the minimum state that matches how humans use reference material (you read the manual once, then continue using what you learned).

### Why reset at turn boundary

Keeps per-turn token cost bounded. A long conversation would otherwise accumulate skill bodies indefinitely. The entity can always re-invoke a skill to re-load its body.

### Implementation location

The **registry exposes the body** via `registry.get_skill(name).body`. The **conversation engine tracks what's loaded** and **includes bodies in context construction**. Neither side owns the full story — the registry is the catalog; the engine is the stateful consumer.

This separation lets the registry stay stateless between construction and dispatch, which simplifies testing and keeps the mechanism of "when does the body appear" localized to the engine's per-turn state.

---

## Capability declarations

Per Tool Framework v1: "At runtime, day-one, these declarations are informational — skills run in her Python process with her full permissions, not in an enforced sandbox."

### What the registry does with them

Parses them from SKILL.md frontmatter. Stores them on the `Skill` dataclass (`Skill.capabilities`). Exposes them via `registry.get_skill(name).capabilities`.

### What the registry does NOT do with them

- No runtime enforcement. A skill declaring `network: allowed_domains: ["duckduckgo.com"]` can still call `requests.get("https://evil.example.com")` and it will go through. The declaration is documentation for review, not a sandbox.
- No validation of declarations against actual code. A skill that declares no network access but makes HTTP calls won't be flagged. Static analysis is out of scope.

### When enforcement might come

Per Tool Framework v1, sandboxing is deferred pending a real use case. If it arrives, this design accommodates it — capability declarations are already parsed and stored; the enforcement layer is the new piece.

---

## Fabrication patterns

### What the registry does with them

Parses them from SKILL.md frontmatter. Stores them on the `Skill` dataclass (`Skill.fabrication_patterns`). Exposes via `registry.get_skill(name).fabrication_patterns`.

Also provides a convenience method for the future fabrication detector:

```python
def all_fabrication_patterns(self) -> dict[str, list[str]]:
    """Return {skill_name: [pattern1, pattern2, ...]} across all skills."""
```

### What the registry does NOT do with them

Nothing active. Dispatch doesn't reference fabrication patterns. The fabrication detector (Tool Framework v1 Phase 2) will read them from the registry when it's built.

---

## Error cases

### Startup-time errors (raise from `from_directory`)

- **Skill directory without SKILL.md** → `SkillFormatError("skill directory X has no SKILL.md")`. Full abort — startup fails loudly rather than silently skipping.
- **Malformed frontmatter** → `SkillFormatError(...)`. Abort.
- **Required frontmatter field missing** → `SkillFormatError(...)`. Abort.
- **Directory name != `name` field** → `SkillFormatError(...)`. Abort.
- **Python import failure in skill script** → `ImportError` propagates. Abort with traceback.
- **Duplicate tool name across skills** → `SkillFormatError("duplicate tool name `web_search` declared by skills `skill_a` and `skill_b`")`. Abort.
- **`@tool` decorator missing required keyword argument** → `TypeError` from decorator call. Abort (happens at import time).

Startup errors should be loud and fatal. A skill that fails to load is a misconfiguration; the right response is "fix the skill" not "silently operate without it."

### Dispatch-time errors (returned as envelope)

- **Unknown tool name** → `{"ok": False, "error": "No tool named `X`..."}`.
- **Schema validation failure** → `{"ok": False, "error": "Invalid arguments..."}`.
- **Tool function raises** → `{"ok": False, "error": "<tool> failed: <type>: <message>"}`. Logged with traceback.
- **Tool function returns non-serializable data** (if the conversation engine needs to JSON-encode it) → the engine's concern, not dispatch's. Dispatch returns the value as-is.

Dispatch errors should be clear to the entity. She sees "no such tool" and can correct. She sees "invalid arguments" and can reformulate. She sees "tool failed: X" and can reason about retry or abandon.

---

## Registry lifecycle

### Construction: once, at startup

```python
registry = SkillRegistry.from_directory("skills/active/")
```

Performed by the main application or conversation engine's startup code. The registry is held for the lifetime of the process.

### Runtime: immutable (from the registry's perspective)

The set of registered skills and tools does not change while the process runs. The conversation engine can call `list_tools`, `get_skill`, `dispatch` freely. These are all read or invoke operations against the immutable registry state.

### Shutdown: nothing special

Registry holds no resources needing cleanup. Process exit is sufficient.

### Reload: via restart

To change skills (add, remove, modify), stop the worker, move skills in the filesystem, restart. Per Tool Framework v1's stated lifecycle.

---

## What this design does NOT cover

- **The agent loop itself.** How a tool call gets detected in the model's output, how the loop iterates, when it terminates. Conversation Engine Design.
- **How context construction includes loaded skill bodies.** The conversation engine's per-turn state interacts with context construction; the mechanics live in Context Construction v1.1 (to be updated as engine design lands) or the engine spec.
- **The actual day-one tools.** Each skill (`web_search`, `file_read`, `memory_search`, etc.) gets its own SKILL.md and implementation. Downstream of this design.
- **Sandboxing / capability enforcement.** Deferred per Tool Framework v1.
- **Fabrication detection.** Phase 2 per Tool Framework v1; this design ensures patterns are stored for the future detector.
- **Skill versioning / migration.** If a skill's SKILL.md changes, the registry just loads the current version. No compatibility tracking day-one.
- **Tool result translation to model tool-result messages.** The conversation engine handles wrapping envelopes into the Ollama/Gemma 4 tool-result format.

---

## Open questions

**a. What happens when a skill's Python scripts have unit tests or `if __name__ == "__main__"` blocks?** Standard Python conventions — the registry imports the module which doesn't execute `__main__` blocks. Tests in the skill directory (e.g., `test_web_search.py`) would also be imported if present, which might trigger pytest collection side effects. Recommend: tests live outside the skill directory (e.g., in `tests/skills/test_web_search.py`). Flag in the implementation spec that follows.

**b. Cross-skill tool calls.** SKILL.md frontmatter has a `capabilities.tools` field listing other tools a skill may invoke. Day-one, skills can freely call `registry.dispatch(...)` (if they have a registry reference — which they don't by default). Should the `@tool` decorator enforce that declared dependencies match actual calls? Probably not day-one; add static analysis later if the project needs it. For now the field is documentation.

**c. Async tools.** All tools are synchronous day-one. If a tool is I/O-bound and would benefit from async (e.g., parallel web fetches within one call), the function can handle its own async internally (e.g., using `asyncio.run` inside the tool body). No need for the dispatch layer to grow async-awareness unless/until multiple tool calls run in parallel — which Tool Framework v1 defers.

**d. Tool call deduplication.** If the model emits two identical tool calls in the same turn, both fire. Any dedup has to be the engine's decision, not the registry's.

**e. Error messages in the entity's language.** Dispatch errors are currently English strings. If the entity ever develops in another language (Principle 16 — drift is the goal), error strings might feel out-of-place. Not an immediate concern; flag.

**f. `registry.list_tools()` ordering.** Currently the order reflects insertion order (dictionary insertion order is preserved in Python 3.7+). Whether the model's behavior depends on tool order is unknown — flag if retrieval quality or tool-call behavior shows ordering effects, tune then.

---

## Deferred

- **Sandboxing.** Per Tool Framework v1.
- **Hot-reload.** Not worth the complexity.
- **Pydantic-based args schemas.** Possible future enhancement.
- **Automatic schema generation from type hints.** Would reduce duplication between function signature and `args_schema`. Not day-one.
- **Entity-proposed skill auto-registration.** Per Tool Framework v1, the entity can propose skills via `staging/`, but activation is manual (admin review + move). No auto-activation.
- **Multi-process or multi-node registry.** Single-process day-one.

---

## Cross-references

- **Tool Framework v1** — parent design. This document is the runtime-mechanism layer of that design.
- **Context Construction v1.1** — will need a small addition to the section composition to accommodate loaded-skill-bodies as a context section (conversation engine's responsibility to feed it; context construction's to render). Noted as a downstream doc update.
- **Schema Design v1.4** — the `tool_trace` field on messages stores per-message tool-call records. Registry doesn't write these; the conversation engine does based on dispatch results.
- **Guiding Principles v1.1** — Principle 9 (capabilities experienced, not invisible), Principle 14 (diagnose before conclude — dispatch error logging), Principle 18 (self-modification — skill proposal path respected).

---

*Project Tír Skill Registry & Tool Dispatch Design · v1 · April 2026*
