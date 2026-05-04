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
import inspect
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema
import yaml

from tir.tools.http_declarative import load_declarative_http_tools

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# @tool decorator
# ---------------------------------------------------------------------------

def tool(
    name: str,
    description: str,
    args_schema: dict,
    *,
    freshness: dict | None = None,
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
            "freshness": _validate_freshness_metadata(freshness),
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
    freshness: dict | None = None
    accepts_context: bool | None = None

    def __post_init__(self):
        if self.accepts_context is None:
            self.accepts_context = _accepts_context(self.function)
        self.freshness = _validate_freshness_metadata(self.freshness)


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

def _accepts_context(func: callable) -> bool:
    """Return whether a tool callable can accept the injected _context arg."""
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return False

    for parameter in signature.parameters.values():
        if parameter.name == "_context":
            return True
        if parameter.kind == inspect.Parameter.VAR_KEYWORD:
            return True

    return False


def _validate_freshness_metadata(freshness: dict | None) -> dict | None:
    """Validate optional tool freshness metadata."""
    if freshness is None:
        return None
    if not isinstance(freshness, dict):
        raise ValueError("freshness must be a mapping")

    allowed_keys = {
        "mode",
        "source_of_truth",
        "memory_may_inform_but_not_replace",
    }
    unknown_keys = set(freshness) - allowed_keys
    if unknown_keys:
        keys = ", ".join(sorted(unknown_keys))
        raise ValueError(f"freshness contains unknown keys: {keys}")

    mode = freshness.get("mode")
    if mode is not None and mode != "real_time":
        raise ValueError("freshness.mode must be 'real_time'")

    source_of_truth = freshness.get("source_of_truth", False)
    if not isinstance(source_of_truth, bool):
        raise ValueError("freshness.source_of_truth must be a boolean")

    memory_note = freshness.get("memory_may_inform_but_not_replace", False)
    if not isinstance(memory_note, bool):
        raise ValueError(
            "freshness.memory_may_inform_but_not_replace must be a boolean"
        )

    normalized = {
        "source_of_truth": source_of_truth,
        "memory_may_inform_but_not_replace": memory_note,
    }
    if mode is not None:
        normalized["mode"] = mode

    return normalized


def _freshness_marker(tool_def: ToolDefinition) -> str:
    """Return a compact human-readable freshness marker for tool prompts."""
    freshness = tool_def.freshness or {}
    if freshness.get("mode") != "real_time":
        return ""

    parts = ["real-time"]
    if freshness.get("source_of_truth"):
        parts.append("source-of-truth")
    if freshness.get("memory_may_inform_but_not_replace"):
        parts.append("memory may inform but not replace")

    return f" [{'; '.join(parts)}]"


def _normalize_args(tool_name: str, args) -> tuple[dict | None, str | None]:
    """Normalize model-supplied tool arguments into a JSON object/dict."""
    if isinstance(args, dict):
        return args, None

    if isinstance(args, str):
        try:
            parsed = json.loads(args)
        except json.JSONDecodeError as e:
            return (
                None,
                f"Invalid arguments for '{tool_name}': arguments must be a JSON "
                f"object; failed to parse JSON string: {e.msg}",
            )

        if not isinstance(parsed, dict):
            return (
                None,
                f"Invalid arguments for '{tool_name}': arguments must be a JSON "
                f"object, got {type(parsed).__name__}",
            )

        return parsed, None

    return (
        None,
        f"Invalid arguments for '{tool_name}': arguments must be a JSON object, "
        f"got {type(args).__name__}",
    )


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
                            freshness=meta.get("freshness"),
                        )

                        registry._tools[tool_name] = tool_def
                        registry._tool_to_skill[tool_name] = skill_name
                        skill.tools.append(tool_name)

                        logger.info(
                            f"Registered tool '{tool_name}' from skill '{skill_name}'"
                        )

            skill_yaml_path = entry / "skill.yaml"
            if skill_yaml_path.exists():
                for declarative_tool in load_declarative_http_tools(skill_yaml_path):
                    tool_name = declarative_tool.name

                    if tool_name in registry._tools:
                        existing = registry._tools[tool_name]
                        raise ValueError(
                            f"Duplicate tool name '{tool_name}' declared by "
                            f"skills '{existing.skill_name}' and '{skill_name}'"
                        )

                    tool_def = ToolDefinition(
                        name=tool_name,
                        description=declarative_tool.description,
                        args_schema=declarative_tool.args_schema,
                        function=declarative_tool.function,
                        skill_name=skill_name,
                        freshness=declarative_tool.freshness,
                        accepts_context=False,
                    )

                    registry._tools[tool_name] = tool_def
                    registry._tool_to_skill[tool_name] = skill_name
                    skill.tools.append(tool_name)

                    logger.info(
                        f"Registered declarative HTTP tool '{tool_name}' "
                        f"from skill '{skill_name}'"
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
            marker = _freshness_marker(tool_def)
            lines.append(f"- {tool_def.name}{marker}: {tool_def.description}")
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
        normalized_args, arg_error = _normalize_args(tool_name, args)
        if arg_error is not None:
            logger.warning(arg_error)
            return {"ok": False, "error": arg_error}

        # Validate args against schema
        try:
            jsonschema.validate(instance=normalized_args, schema=tool_def.args_schema)
        except jsonschema.ValidationError as e:
            error_msg = f"Invalid arguments for '{tool_name}': {e.message}"
            logger.warning(error_msg)
            return {"ok": False, "error": error_msg}

        # Call the tool
        try:
            if _context is not None and tool_def.accepts_context:
                result = tool_def.function(**normalized_args, _context=_context)
            else:
                result = tool_def.function(**normalized_args)

            return {"ok": True, "value": result, "normalized_args": normalized_args}

        except Exception as e:
            error_msg = f"'{tool_name}' failed: {type(e).__name__}: {e}"
            logger.exception(error_msg)
            return {"ok": False, "error": error_msg}
