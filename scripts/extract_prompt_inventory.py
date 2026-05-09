#!/usr/bin/env python3
"""Extract a reviewable inventory of backend prompt-like strings.

This script uses AST/source inspection only. It does not import runtime modules
and does not execute Project Anam code.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass, field
from pathlib import Path


CATEGORIES = (
    "Runtime context / identity",
    "Chat / agent loop",
    "Tool-use prompts",
    "Retrieval / memory framing",
    "Artifact / source framing",
    "Behavioral guidance review",
    "Reflection / journal",
    "Research / future automation",
    "Admin / review commands",
    "Other prompt-like strings",
)

AUDIT_NOTE_OPTIONS = (
    "keep",
    "loosen",
    "move to OPERATIONAL_GUIDANCE.md",
    "behavioral guidance candidate",
    "remove",
    "needs discussion",
)

RISK_FLAGS = (
    "assistant",
    "chatbot",
    "agent",
    "persona",
    "personality",
    "unnamed AI entity",
    "Project Anam",
    "do not",
    "must",
    "always",
    "never",
    "you are",
    "your purpose",
    "self-modification",
    "feelings",
    "emotion",
    "fabricate",
    "truth",
    "authority",
    "source_material",
)

PROMPT_NAME_MARKERS = (
    "prompt",
    "system",
    "user_prompt",
    "message",
    "messages",
    "guidance",
    "context",
    "description",
    "instructions",
)

MODEL_CALL_NAMES = {
    "chat_completion_json",
    "chat_completion_text",
    "chat_completion_stream_with_tools",
    "build_system_prompt",
    "build_system_prompt_with_debug",
}

PROMPT_ADJACENT_CALLS = {"append", "extend"}

PROMPT_MODULE_HINTS = (
    "tir/engine/context.py",
    "tir/engine/agent_loop.py",
    "tir/engine/artifact_context.py",
    "tir/engine/tool_trace_context.py",
    "tir/reflection/journal.py",
    "tir/behavioral_guidance/review.py",
    "tir/memory/chunking.py",
    "tir/memory/retrieval.py",
    "tir/tools/registry.py",
)


@dataclass
class InventoryEntry:
    path: str
    line: int
    function: str | None
    name: str
    category: str
    excerpt: str
    flags: list[str] = field(default_factory=list)


class PromptInventoryVisitor(ast.NodeVisitor):
    def __init__(self, path: Path, rel_path: str, source: str):
        self.path = path
        self.rel_path = rel_path
        self.source = source
        self.entries: list[InventoryEntry] = []
        self.function_stack: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.visit_FunctionDef(node)

    def visit_Assign(self, node: ast.Assign):
        target_names = [self._target_name(target) for target in node.targets]
        name = next((item for item in target_names if item), None)
        if name and _name_is_prompt_like(name):
            self._add_string_value(node.value, name=name, reason="assignment")
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        name = self._target_name(node.target)
        if name and node.value is not None and _name_is_prompt_like(name):
            self._add_string_value(node.value, name=name, reason="assignment")
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict):
        pairs = {}
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                pairs[key.value] = value
        role_value = _literal_string(pairs.get("role"))
        if role_value in {"system", "user"} and "content" in pairs:
            self._add_string_value(
                pairs["content"],
                name=f"{role_value}_message_content",
                reason="role_content_dict",
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        call_name = _call_name(node.func)
        if call_name in MODEL_CALL_NAMES:
            for arg in node.args:
                self._add_string_value(arg, name=f"{call_name}_arg", reason="model_call")
            for keyword in node.keywords:
                if keyword.arg and _name_is_prompt_like(keyword.arg):
                    self._add_string_value(
                        keyword.value,
                        name=f"{call_name}_{keyword.arg}",
                        reason="model_call_keyword",
                    )
        elif self._is_prompt_module() and call_name in PROMPT_ADJACENT_CALLS:
            for arg in node.args:
                self._add_string_value(arg, name=f"{call_name}_arg", reason="prompt_adjacent_call")
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return):
        if self._is_prompt_module() and node.value is not None:
            self._add_string_value(node.value, name="return_value", reason="prompt_module_return")
        self.generic_visit(node)

    def _target_name(self, target: ast.AST) -> str | None:
        if isinstance(target, ast.Name):
            return target.id
        if isinstance(target, ast.Attribute):
            return target.attr
        return None

    def _add_string_value(self, node: ast.AST, *, name: str, reason: str) -> None:
        excerpt = _source_or_literal(self.source, node)
        if not excerpt or not _looks_prompt_like_text(excerpt, self.rel_path, name):
            return
        self.entries.append(
            InventoryEntry(
                path=self.rel_path,
                line=getattr(node, "lineno", 1),
                function=self.function_stack[-1] if self.function_stack else None,
                name=name,
                category=classify_category(self.rel_path, excerpt, name),
                excerpt=normalize_excerpt(excerpt),
                flags=risk_flags_for(excerpt),
            )
        )

    def _is_prompt_module(self) -> bool:
        return any(marker in self.rel_path for marker in PROMPT_MODULE_HINTS)


def _literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                parts.append("{...}")
        return "".join(parts)
    return None


def _source_or_literal(source: str, node: ast.AST) -> str | None:
    literal = _literal_string(node)
    if literal is not None:
        return literal
    segment = ast.get_source_segment(source, node)
    if segment and isinstance(node, ast.JoinedStr):
        return segment
    return None


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _name_is_prompt_like(name: str) -> bool:
    lowered = name.lower()
    return any(marker in lowered for marker in PROMPT_NAME_MARKERS)


def _looks_prompt_like_text(text: str, rel_path: str, name: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 20:
        return False
    if "\n" in stripped:
        return True
    lowered = stripped.lower()
    if any(flag.lower() in lowered for flag in RISK_FLAGS):
        return True
    if any(marker in rel_path for marker in PROMPT_MODULE_HINTS):
        return True
    return _name_is_prompt_like(name)


def normalize_excerpt(text: str, max_chars: int = 1200) -> str:
    stripped = text.strip()
    if len(stripped) <= max_chars:
        return stripped
    return stripped[:max_chars].rstrip() + "\n...[truncated]"


def risk_flags_for(text: str) -> list[str]:
    lowered = text.lower()
    return [flag for flag in RISK_FLAGS if flag.lower() in lowered]


def classify_category(path: str, text: str, name: str) -> str:
    lowered = f"{path} {name} {text}".lower()
    if "behavioral_guidance/review.py" in path:
        return "Behavioral guidance review"
    if "reflection/journal.py" in path:
        return "Reflection / journal"
    if "engine/context.py" in path:
        return "Runtime context / identity"
    if "agent_loop.py" in path or "ollama.py" in path:
        return "Chat / agent loop"
    if "tools/" in path or "tool" in lowered:
        return "Tool-use prompts"
    if "retrieval" in lowered or "memory" in lowered or "chunk" in lowered:
        return "Retrieval / memory framing"
    if "artifact" in lowered or "source" in lowered:
        return "Artifact / source framing"
    if "research" in lowered or "autonomous" in lowered:
        return "Research / future automation"
    if "admin" in lowered or "review" in lowered:
        return "Admin / review commands"
    return "Other prompt-like strings"


def collect_inventory(root: Path) -> list[InventoryEntry]:
    entries: list[InventoryEntry] = []
    root = root.resolve()
    cwd = Path.cwd().resolve()
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        resolved = path.resolve()
        try:
            rel_path = resolved.relative_to(cwd).as_posix()
        except ValueError:
            rel_path = resolved.as_posix()
        visitor = PromptInventoryVisitor(path, rel_path, source)
        visitor.visit(tree)
        entries.extend(visitor.entries)
    return dedupe_entries(entries)


def dedupe_entries(entries: list[InventoryEntry]) -> list[InventoryEntry]:
    seen = set()
    deduped = []
    for entry in entries:
        key = (entry.path, entry.line, entry.name, entry.excerpt)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped


def render_markdown(entries: list[InventoryEntry]) -> str:
    lines = [
        "# Prompt Inventory",
        "",
        "This generated inventory lists backend prompt-like strings found in `tir/**/*.py`.",
        "It is an audit aid only and does not change runtime behavior.",
        "",
        "Audit note options: " + ", ".join(f"`{item}`" for item in AUDIT_NOTE_OPTIONS) + ".",
        "",
        "Risk flags searched: " + ", ".join(f"`{flag}`" for flag in RISK_FLAGS) + ".",
        "",
    ]

    for category in CATEGORIES:
        category_entries = [entry for entry in entries if entry.category == category]
        lines.extend([f"## {category}", ""])
        if not category_entries:
            lines.extend(["No prompt-like strings found.", ""])
            continue
        for index, entry in enumerate(category_entries, start=1):
            function = f" — `{entry.function}`" if entry.function else ""
            flags = ", ".join(f"`{flag}`" for flag in entry.flags) if entry.flags else "none"
            lines.extend(
                [
                    f"### {index}. `{entry.path}:{entry.line}`{function}",
                    "",
                    f"- Name: `{entry.name}`",
                    f"- Category: {entry.category}",
                    f"- Risk flags: {flags}",
                    "- Audit note: `needs discussion`",
                    "",
                    "Excerpt:",
                    "",
                    "```text",
                    entry.excerpt,
                    "```",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract backend prompt inventory")
    parser.add_argument("--root", type=Path, default=Path("tir"), help="Root to scan")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/PROMPT_INVENTORY.md"),
        help="Markdown report path",
    )
    args = parser.parse_args()

    entries = collect_inventory(args.root)
    report = render_markdown(entries)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"Wrote {args.output} with {len(entries)} prompt-like entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
