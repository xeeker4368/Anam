# CC Task: Phase 3 Step 1 — Skill Registry

## What this is

The skill registry discovers installed skills at startup, parses their SKILL.md files, registers their tools, and dispatches tool calls from the agent loop. This is the foundation for every capability the entity will have beyond conversation.

## Prerequisites

- Phase 2 complete (memory working)
- `pyyaml` and `jsonschema` installed (should be from requirements.txt, if not: `pip install pyyaml jsonschema`)

## Files to create

```
tir/
    tools/
        __init__.py    ← NEW (empty)
        registry.py    ← NEW
skills/
    active/            ← NEW (empty directory, create if not exists)
```

## New file: `tir/tools/__init__.py`

```python
```

(Empty file — package marker.)

## New file: `tir/tools/registry.py`

```python
"""
Tír Skill Registry

Discovers skills at startup, registers tools, dispatches tool calls.

A skill is a directory under skills/active/ containing a SKILL.md file.
Tools are Python functions decorated with @tool in that directory's
Python scripts.

The registry scans once at startup. No hot-reload — restart to change skills.

The entity doesn't see the registry. She sees tools listed in her context
and calls them by name. The registry handles the plumbing.
"""

import importlib
import importlib.util
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema
import yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# @tool decorator
# ---------------------------------------------------------------------------

def tool(
    name: str,
    description: str,
    args_schema: dict,
):
    """Decorator that marks a function as a tool.

    Args:
        name: Tool name the model uses to call it (e.g., "memory_search").
        description: What the tool does (shown to the model).
        args_schema: JSON Schema dict for the arguments. Example:
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }

    Usage:
        @tool(
            name="memory_search",
            description="Search your own memories",
            args_schema={...},
        )
        def memory_search(query: str, _context=None) -> str:
            ...
    """
    def decorator(func):
        func._tool_metadata = {
            "name": name,
            "description": description,
            "args_schema": args_schema,
        }
        return func
    return decorator


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ToolDefinition:
    """A registered tool — its metadata and callable."""
    name: str
    description: str
    args_schema: dict
    function: callable
    skill_name: str  # which skill owns this tool


@dataclass
class Skill:
    """A loaded skill — parsed from SKILL.md + discovered tools."""
    name: str
    description: str
    version: str
    body: str  # markdown body of SKILL.md (for progressive disclosure)
    tools: list[str] = field(default_factory=list)  # tool names owned by this skill
    capabilities: dict = field(default_factory=dict)
    fabrication_patterns: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# SKILL.md parsing
# ---------------------------------------------------------------------------

def _parse_skill_md(path: Path) -> tuple[dict, str]:
    """Parse a SKILL.md file into frontmatter dict and body string.

    SKILL.md format:
        ---
        name: web_search
        description: Search the web
        version: "1.0"
        ---
        # Usage instructions
        ...markdown body...

    Returns:
        (frontmatter_dict, body_string)

    Raises:
        ValueError if format is invalid.
    """
    text = path.read_text(encoding="utf-8")

    if not text.startswith("---"):
        raise ValueError(f"{path}: SKILL.md must start with '---' (YAML frontmatter)")

    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"{path}: SKILL.md must have opening and closing '---'")

    frontmatter_text = parts[1].strip()
    body = parts[2].strip()

    try:
        frontmatter = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as e:
        raise ValueError(f"{path}: Invalid YAML in frontmatter: {e}")

    if not isinstance(frontmatter, dict):
        raise ValueError(f"{path}: Frontmatter must be a YAML mapping")

    # Validate required fields
    for field_name in ("name", "description", "version"):
        if field_name not in frontmatter:
            raise ValueError(f"{path}: Missing required frontmatter field '{field_name}'")

    return frontmatter, body


# ---------------------------------------------------------------------------
# Skill Registry
# ---------------------------------------------------------------------------

class SkillRegistry:
    """Registry of skills and their tools.

    Constructed once at startup via from_directory(). Immutable after that.
    """

    def __init__(self):
        self._skills: dict[str, Skill] = {}
        self._tools: dict[str, ToolDefinition] = {}
        self._tool_to_skill: dict[str, str] = {}

    @classmethod
    def from_directory(cls, skills_dir: str | Path) -> "SkillRegistry":
        """Scan a directory for skills and build the registry.

        Each subdirectory with a SKILL.md is a skill. Python scripts
        in the directory are imported and scanned for @tool decorators.

        Args:
            skills_dir: Path to the active skills directory.

        Returns:
            Populated SkillRegistry.

        Raises:
            ValueError: On format errors (missing SKILL.md fields, etc.)
            ImportError: If a skill's Python scripts fail to import.
        """
        registry = cls()
        skills_path = Path(skills_dir)

        if not skills_path.exists():
            logger.info(f"Skills directory {skills_path} does not exist, no skills loaded")
            return registry

        for entry in sorted(skills_path.iterdir()):
            if not entry.is_dir():
                continue

            skill_md_path = entry / "SKILL.md"
            if not skill_md_path.exists():
                continue  # Not a skill directory, skip silently

            # Parse SKILL.md
            frontmatter, body = _parse_skill_md(skill_md_path)

            skill_name = frontmatter["name"]

            # Validate directory name matches skill name
            if entry.name != skill_name:
                raise ValueError(
                    f"Skill directory '{entry.name}' doesn't match "
                    f"SKILL.md name '{skill_name}'"
                )

            # Create Skill object
            skill = Skill(
                name=skill_name,
                description=frontmatter["description"],
                version=str(frontmatter["version"]),
                body=body,
                capabilities=frontmatter.get("capabilities", {}),
                fabrication_patterns=frontmatter.get("fabrication_patterns", []),
            )

            # Import Python scripts and find @tool functions
            for py_file in sorted(entry.glob("*.py")):
                if py_file.name.startswith("__"):
                    continue

                module_name = f"tir_skill_{skill_name}_{py_file.stem}"

                try:
                    spec = importlib.util.spec_from_file_location(
                        module_name, str(py_file)
                    )
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                except Exception as e:
                    raise ImportError(
                        f"Failed to import {py_file} from skill '{skill_name}': {e}"
                    ) from e

                # Scan for @tool decorated functions
                for attr_name in dir(module):
                    obj = getattr(module, attr_name)
                    if callable(obj) and hasattr(obj, "_tool_metadata"):
                        meta = obj._tool_metadata
                        tool_name = meta["name"]

                        # Check for duplicates
                        if tool_name in registry._tools:
                            existing = registry._tools[tool_name]
                            raise ValueError(
                                f"Duplicate tool name '{tool_name}' declared by "
                                f"skills '{existing.skill_name}' and '{skill_name}'"
                            )

                        tool_def = ToolDefinition(
                            name=tool_name,
                            description=meta["description"],
                            args_schema=meta["args_schema"],
                            function=obj,
                            skill_name=skill_name,
                        )

                        registry._tools[tool_name] = tool_def
                        registry._tool_to_skill[tool_name] = skill_name
                        skill.tools.append(tool_name)

                        logger.info(
                            f"Registered tool '{tool_name}' from skill '{skill_name}'"
                        )

            registry._skills[skill_name] = skill

        logger.info(
            f"Skill registry loaded: {len(registry._skills)} skills, "
            f"{len(registry._tools)} tools"
        )
        return registry

    # --- Query methods ---

    def list_tools(self) -> list[dict]:
        """Return tool definitions in Ollama's required format.

        Format:
            [{"type": "function", "function": {"name": ..., "description": ...,
              "parameters": ...}}, ...]
        """
        result = []
        for tool_def in self._tools.values():
            result.append({
                "type": "function",
                "function": {
                    "name": tool_def.name,
                    "description": tool_def.description,
                    "parameters": tool_def.args_schema,
                },
            })
        return result

    def list_tool_descriptions(self) -> str:
        """Return a formatted string of tool names and descriptions.

        Used by context construction to show the entity what tools
        are available. Not the full schema — just names and what they do.
        """
        if not self._tools:
            return ""

        lines = ["You have access to the following tools:"]
        for tool_def in self._tools.values():
            lines.append(f"- {tool_def.name}: {tool_def.description}")
        return "\n".join(lines)

    def get_skill(self, skill_name: str) -> Skill:
        """Get a skill by name. Raises KeyError if not found."""
        return self._skills[skill_name]

    def get_skill_for_tool(self, tool_name: str) -> Skill:
        """Get the skill that owns a tool. Raises KeyError if not found."""
        skill_name = self._tool_to_skill[tool_name]
        return self._skills[skill_name]

    def has_tools(self) -> bool:
        """Whether any tools are registered."""
        return len(self._tools) > 0

    # --- Dispatch ---

    def dispatch(
        self,
        tool_name: str,
        args: dict,
        _context=None,
    ) -> dict:
        """Invoke a tool. Returns {ok, value|error} envelope.

        Args:
            tool_name: Name of the tool to call.
            args: Arguments from the model's tool call.
            _context: ToolContext injected by the agent loop.
                Passed to tools that accept it.

        Returns:
            {"ok": True, "value": <result>} on success (including
                tool-returned errors).
            {"ok": False, "error": <message>} on crashes or unknown tools.
        """
        # Look up tool
        if tool_name not in self._tools:
            error_msg = (
                f"No tool named '{tool_name}'. "
                f"Available tools: {', '.join(self._tools.keys()) or 'none'}"
            )
            logger.warning(error_msg)
            return {"ok": False, "error": error_msg}

        tool_def = self._tools[tool_name]

        # Validate args against schema
        try:
            jsonschema.validate(instance=args, schema=tool_def.args_schema)
        except jsonschema.ValidationError as e:
            error_msg = f"Invalid arguments for '{tool_name}': {e.message}"
            logger.warning(error_msg)
            return {"ok": False, "error": error_msg}

        # Call the tool
        try:
            if _context is not None:
                try:
                    result = tool_def.function(**args, _context=_context)
                except TypeError as e:
                    if "_context" in str(e):
                        # Tool doesn't accept _context
                        result = tool_def.function(**args)
                    else:
                        raise
            else:
                result = tool_def.function(**args)

            return {"ok": True, "value": result}

        except Exception as e:
            error_msg = f"'{tool_name}' failed: {type(e).__name__}: {e}"
            logger.exception(error_msg)
            return {"ok": False, "error": error_msg}
```

## Create the skills directory

```bash
mkdir -p /path/to/Tir/skills/active
```

## Verify — registry loads with no skills

```bash
cd /path/to/Tir
python3 -c "
from tir.tools.registry import SkillRegistry

registry = SkillRegistry.from_directory('skills/active/')
print(f'Skills: {len(registry._skills)}')
print(f'Tools: {len(registry._tools)}')
print(f'Has tools: {registry.has_tools()}')
print(f'Tool list: {registry.list_tools()}')
print(f'Tool descriptions: {repr(registry.list_tool_descriptions())}')
print('PASS')
"
```

Expected: 0 skills, 0 tools, has_tools=False, empty lists/string. PASS.

## Verify — registry loads a test skill

```bash
cd /path/to/Tir

# Create a test skill
mkdir -p /tmp/test_skills/active/echo
cat > /tmp/test_skills/active/echo/SKILL.md << 'EOF'
---
name: echo
description: Echoes back the input
version: "1.0"
---
# Echo Tool
A simple test tool that returns its input.
EOF

cat > /tmp/test_skills/active/echo/echo.py << 'PYEOF'
from tir.tools.registry import tool

@tool(
    name="echo",
    description="Echoes back the input text",
    args_schema={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to echo"}
        },
        "required": ["text"],
    },
)
def echo(text: str) -> str:
    return f"Echo: {text}"
PYEOF

python3 -c "
from tir.tools.registry import SkillRegistry

registry = SkillRegistry.from_directory('/tmp/test_skills/active/')
print(f'Skills: {len(registry._skills)}')
print(f'Tools: {len(registry._tools)}')
print(f'Has tools: {registry.has_tools()}')

# Check tool list format
tools = registry.list_tools()
print(f'Tool list: {tools}')
assert tools[0]['type'] == 'function'
assert tools[0]['function']['name'] == 'echo'

# Check descriptions
desc = registry.list_tool_descriptions()
print(f'Descriptions: {desc}')

# Test dispatch — success
result = registry.dispatch('echo', {'text': 'hello'})
print(f'Dispatch result: {result}')
assert result['ok'] == True
assert result['value'] == 'Echo: hello'

# Test dispatch — unknown tool
result = registry.dispatch('nonexistent', {})
print(f'Unknown tool: {result}')
assert result['ok'] == False

# Test dispatch — bad args
result = registry.dispatch('echo', {'wrong_param': 'hello'})
print(f'Bad args: {result}')
assert result['ok'] == False

# Test SKILL.md body
skill = registry.get_skill('echo')
print(f'Skill body: {skill.body}')
assert 'simple test tool' in skill.body

# Test get_skill_for_tool
skill2 = registry.get_skill_for_tool('echo')
assert skill2.name == 'echo'

print('PASS')
"

# Cleanup
rm -rf /tmp/test_skills
```

Expected: 1 skill, 1 tool, dispatch works, bad args caught, unknown tool caught. PASS.

## Verify — duplicate tool name caught

```bash
cd /path/to/Tir

mkdir -p /tmp/test_skills/active/echo1
mkdir -p /tmp/test_skills/active/echo2

cat > /tmp/test_skills/active/echo1/SKILL.md << 'EOF'
---
name: echo1
description: First echo
version: "1.0"
---
Body
EOF

cat > /tmp/test_skills/active/echo1/echo1.py << 'PYEOF'
from tir.tools.registry import tool

@tool(name="echo", description="Echo 1", args_schema={"type": "object", "properties": {}})
def echo1() -> str:
    return "1"
PYEOF

cat > /tmp/test_skills/active/echo2/SKILL.md << 'EOF'
---
name: echo2
description: Second echo
version: "1.0"
---
Body
EOF

cat > /tmp/test_skills/active/echo2/echo2.py << 'PYEOF'
from tir.tools.registry import tool

@tool(name="echo", description="Echo 2", args_schema={"type": "object", "properties": {}})
def echo2() -> str:
    return "2"
PYEOF

python3 -c "
from tir.tools.registry import SkillRegistry
try:
    registry = SkillRegistry.from_directory('/tmp/test_skills/active/')
    print('FAIL — should have raised ValueError')
except ValueError as e:
    print(f'Caught duplicate: {e}')
    print('PASS')
"

rm -rf /tmp/test_skills
```

Expected: ValueError about duplicate tool name "echo". PASS.

## What NOT to do

- Do NOT modify any existing files — this spec only creates new files
- Do NOT import anything from `tir.tools.registry` in existing modules yet — integration comes in Step 4
- Do NOT add hot-reload logic — restart to change skills
- Do NOT make the registry a global singleton — the caller constructs it
- Do NOT add async dispatch — synchronous is correct for day-one
- Do NOT silently skip skills with errors — fail loudly at startup

## What comes next

After verifying the registry works:
- Step 2: Agent loop (uses the registry for tool dispatch and listing)
