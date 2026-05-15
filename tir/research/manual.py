"""Manual, user-triggered research note generation.

This module only produces provisional Markdown research notes. It does not
use web search, create review/open-loop records, or promote conclusions into
guidance, self-understanding, or project decisions. Artifact registration and
indexing only happen when explicitly requested by the admin command.
"""

import re
from datetime import datetime, timezone
from pathlib import Path

from tir.artifacts.service import create_artifact, get_artifact, list_artifacts
from tir.config import CHAT_MODEL, OLLAMA_HOST, WORKSPACE_DIR
from tir.engine.ollama import chat_completion_text
from tir.memory.research_indexing import index_manual_research_note, research_chunks_exist
from tir.workspace.service import ensure_workspace, resolve_workspace_path, write_workspace_file


MANUAL_RESEARCH_VERSION = "manual_research_v1"
MANUAL_RESEARCH_CONTINUATION_VERSION = "manual_research_continuation_v1"
RESEARCH_DIR = "research"
REQUIRED_BODY_HEADINGS = (
    "## Purpose",
    "## Summary",
    "## Findings",
    "## Uncertainty",
    "## Sources",
    "## Open Questions",
    "## Possible Follow-Ups",
    "## Suggested Review Items",
    "## Working Notes",
)
CONTINUATION_BODY_HEADINGS = (
    "## Purpose",
    "## Prior Research Considered",
    "## What Changed / What Is Being Extended",
    "## Updated Findings",
    "## Superseded Or Weakened Prior Claims",
    "## Remaining Uncertainty",
    "## Sources",
    "## New Open Questions",
    "## Possible Follow-Ups",
    "## Suggested Review Items",
    "## Working Notes",
)
PRIOR_RESEARCH_CONTEXT_HEADER = """[Prior provisional research note]

This prior research note is working research context, not truth, project decision, behavioral guidance, or self-understanding. Use it to continue the investigation, identify what still holds, what is uncertain, and what may need revision."""


class ManualResearchError(ValueError):
    """Raised when a manual research note cannot be generated or written."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_text(value: str | None, field: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ManualResearchError(f"{field} is required")
    return normalized


def derive_research_title(question: str) -> str:
    """Derive a concise title from the research question."""
    normalized = re.sub(r"\s+", " ", question).strip().strip("\"'")
    normalized = normalized.rstrip("?.!").strip()
    if not normalized:
        return "Research Note"
    if len(normalized) > 80:
        normalized = normalized[:80].rsplit(" ", 1)[0].strip() or normalized[:80].strip()
    return normalized


def slugify_title(title: str) -> str:
    """Return a deterministic filesystem-safe slug for a research title."""
    lowered = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    if not slug:
        return "research-note"
    return slug[:80].rstrip("-") or "research-note"


def research_relative_path(created_at: str, title: str) -> str:
    """Return the workspace-relative research note path."""
    date_text = datetime.fromisoformat(created_at).date().isoformat()
    return f"{RESEARCH_DIR}/{date_text}-{slugify_title(title)}.md"


def _display_continued_from(continuation: dict) -> str:
    parts = []
    title = continuation.get("title")
    path = continuation.get("path")
    artifact_id = continuation.get("artifact_id")
    research_date = continuation.get("research_date")
    if title:
        parts.append(str(title))
    if path:
        parts.append(str(path))
    if artifact_id:
        parts.append(f"artifact {artifact_id}")
    if research_date:
        parts.append(str(research_date))
    if not continuation.get("registered", True):
        parts.append("file-only/unregistered")
    return " / ".join(parts) or "prior provisional research note"


def _normalize_continue_file_path(path: str | Path) -> str:
    raw_path = Path(path)
    if raw_path.is_absolute():
        raise ManualResearchError("--continue-file must be under workspace/research/")
    parts = raw_path.parts
    if parts and parts[0] == "workspace":
        raw_path = Path(*parts[1:])
    if not raw_path.parts or raw_path.parts[0] != RESEARCH_DIR:
        raise ManualResearchError("--continue-file must be under workspace/research/")
    if ".." in raw_path.parts:
        raise ManualResearchError("--continue-file must be under workspace/research/")
    if raw_path.suffix.lower() != ".md":
        raise ManualResearchError("--continue-file must point to a Markdown file")
    return raw_path.as_posix()


def _require_research_metadata(metadata: dict, artifact_id: str, field: str):
    if field not in metadata or metadata.get(field) in (None, ""):
        raise ManualResearchError(f"Research artifact is missing required metadata: {field}")
    return metadata[field]


def load_research_continuation_artifact(
    artifact_id: str,
    *,
    workspace_root: Path = WORKSPACE_DIR,
) -> dict:
    """Load a registered research note as continuation context."""
    artifact = get_artifact(artifact_id)
    if artifact is None:
        raise ManualResearchError(f"Research artifact not found: {artifact_id}")
    if artifact.get("artifact_type") != "research_note":
        raise ManualResearchError(f"Artifact is not a research note: {artifact_id}")
    if artifact.get("status") != "active":
        raise ManualResearchError(f"Research artifact is not active: {artifact_id}")

    metadata = artifact.get("metadata") or {}
    for field, expected in (
        ("source_type", "research"),
        ("source_role", "research_reference"),
        ("origin", "manual_research"),
    ):
        value = _require_research_metadata(metadata, artifact_id, field)
        if value != expected:
            raise ManualResearchError(f"Research artifact is missing required metadata: {field}")
    if metadata.get("provisional") is not True:
        raise ManualResearchError("Research artifact is missing required metadata: provisional")

    path = artifact.get("path")
    if not path:
        raise ManualResearchError("Research artifact is missing required metadata: path")
    target = resolve_workspace_path(path, Path(workspace_root))
    if not target.exists() or not target.is_file():
        raise ManualResearchError(f"Prior research note file not found: {path}")
    content = target.read_text(encoding="utf-8")
    research_title = metadata.get("research_title") or artifact.get("title")
    research_date = metadata.get("research_date") or artifact.get("created_at")
    return {
        "source": "artifact",
        "registered": True,
        "artifact_id": artifact["artifact_id"],
        "artifact": artifact,
        "path": path,
        "title": research_title,
        "research_date": research_date,
        "content": content,
        "metadata": metadata,
        "continued_from": _display_continued_from(
            {
                "title": research_title,
                "path": path,
                "artifact_id": artifact["artifact_id"],
                "research_date": research_date,
                "registered": True,
            }
        ),
    }


def load_research_continuation_file(
    path: str | Path,
    *,
    workspace_root: Path = WORKSPACE_DIR,
) -> dict:
    """Load a workspace research file as continuation context."""
    root = Path(workspace_root)
    relative_path = _normalize_continue_file_path(path)
    target = resolve_workspace_path(relative_path, root)
    if not target.exists() or not target.is_file():
        raise ManualResearchError(f"Prior research note file not found: {relative_path}")

    matches = list_artifacts(path=relative_path, workspace_root=root, limit=2)
    if matches:
        artifact = matches[0]
        artifact_id = artifact.get("artifact_id")
        if artifact.get("artifact_type") != "research_note":
            raise ManualResearchError(f"Artifact is not a research note: {artifact_id}")
        if artifact.get("status") != "active":
            raise ManualResearchError(f"Research artifact is not active: {artifact_id}")
        metadata = artifact.get("metadata") or {}
        for field, expected in (
            ("source_type", "research"),
            ("source_role", "research_reference"),
            ("origin", "manual_research"),
        ):
            value = _require_research_metadata(metadata, artifact_id, field)
            if value != expected:
                raise ManualResearchError(f"Research artifact is missing required metadata: {field}")
        if metadata.get("provisional") is not True:
            raise ManualResearchError("Research artifact is missing required metadata: provisional")
        research_title = metadata.get("research_title") or artifact.get("title")
        research_date = metadata.get("research_date") or artifact.get("created_at")
        registered = True
    else:
        artifact = None
        metadata = {}
        research_title = target.stem
        research_date = None
        registered = False
        artifact_id = None

    continuation = {
        "source": "file",
        "registered": registered,
        "artifact_id": artifact_id,
        "artifact": artifact,
        "path": relative_path,
        "title": research_title,
        "research_date": research_date,
        "content": target.read_text(encoding="utf-8"),
        "metadata": metadata,
    }
    continuation["continued_from"] = _display_continued_from(continuation)
    return continuation


def build_manual_research_messages(*, title: str, question: str, scope: str) -> list[dict]:
    """Build model messages for a provisional manual research note."""
    system = (
        "Produce a structured provisional research note. "
        "Use only the supplied question and scope. "
        "Do not claim external sources were collected. "
        "Do not create behavioral guidance, self-understanding, project decisions, "
        "review items, open loops, or runtime instructions."
    )
    user = f"""Title: {title}
Question: {question}
Scope: {scope}

Return Markdown body sections only, using exactly these headings:

## Purpose
## Summary
## Findings
## Uncertainty
## Sources
## Open Questions
## Possible Follow-Ups
## Suggested Review Items
## Working Notes

Frame findings as provisional working notes. It is valid to report no useful findings, no open questions, no suggested follow-ups, or no suggested review items when that is the honest result. For Sources, state that this is a model-only draft and no external sources were collected."""
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_manual_research_continuation_messages(
    *,
    title: str,
    question: str,
    scope: str,
    continuation: dict,
) -> list[dict]:
    """Build model messages for a provisional research continuation note."""
    system = (
        "Produce a structured provisional research continuation note. "
        "Use only the supplied question, scope, and prior provisional research note. "
        "Do not treat prior research as truth or authority. "
        "Do not claim external sources were collected. "
        "Do not create behavioral guidance, self-understanding, project decisions, "
        "review items, open loops, or runtime instructions."
    )
    registration_note = (
        "The prior source is registered as a research artifact."
        if continuation.get("registered")
        else "The prior source is file-only/unregistered."
    )
    user = f"""Title: {title}
Question: {question}
Scope: {scope}
Continued from: {continuation['continued_from']}
{registration_note}

{PRIOR_RESEARCH_CONTEXT_HEADER}

{continuation['content']}

Return Markdown body sections only, using exactly these headings:

## Purpose
## Prior Research Considered
## What Changed / What Is Being Extended
## Updated Findings
## Superseded Or Weakened Prior Claims
## Remaining Uncertainty
## Sources
## New Open Questions
## Possible Follow-Ups
## Suggested Review Items
## Working Notes

Frame findings as provisional working notes. Distinguish what the prior note said from updated findings. It is valid to report no useful updated findings, no new open questions, no suggested follow-ups, or no suggested review items when that is the honest result. For Sources, state that this is a model-only draft plus prior provisional research note and no external sources were collected."""
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _validate_body(body: str, required_headings: tuple[str, ...] = REQUIRED_BODY_HEADINGS) -> str:
    normalized = (body or "").strip()
    if not normalized:
        raise ManualResearchError("Model returned an empty research note")
    missing = [heading for heading in required_headings if heading not in normalized]
    if missing:
        raise ManualResearchError(
            "Model research note is missing required heading: " + missing[0]
        )
    return normalized


def build_research_document(
    *,
    title: str,
    question: str,
    scope: str,
    created_at: str,
    body: str,
) -> str:
    """Wrap the model body in deterministic research-note metadata."""
    header = f"""# Research Note — {title}

- Question: {question}
- Scope: {scope}
- Created: {created_at}
- Research mode: {MANUAL_RESEARCH_VERSION}
- Sources used: Model-only draft; no external sources collected.
- Provisional: true

"""
    return header + _validate_body(body).rstrip() + "\n"


def build_research_continuation_document(
    *,
    title: str,
    question: str,
    scope: str,
    created_at: str,
    body: str,
    continuation: dict,
) -> str:
    """Wrap a continuation model body in deterministic research-note metadata."""
    header = f"""# Research Note — {title}

- Question: {question}
- Scope: {scope}
- Created: {created_at}
- Research mode: {MANUAL_RESEARCH_CONTINUATION_VERSION}
- Continued from: {continuation['continued_from']}
- Sources used: Model-only draft plus prior provisional research note; no external sources collected.
- Provisional: true

"""
    return header + _validate_body(body, CONTINUATION_BODY_HEADINGS).rstrip() + "\n"


def generate_manual_research_note(
    *,
    question: str,
    scope: str,
    title: str | None = None,
    model: str | None = None,
    ollama_host: str = OLLAMA_HOST,
) -> dict:
    """Generate a dry-run manual research note."""
    normalized_question = _require_text(question, "question")
    normalized_scope = _require_text(scope, "scope")
    normalized_title = _require_text(
        title or derive_research_title(normalized_question),
        "title",
    )
    created_at = _now()
    messages = build_manual_research_messages(
        title=normalized_title,
        question=normalized_question,
        scope=normalized_scope,
    )
    raw = chat_completion_text(
        messages,
        model=model or CHAT_MODEL,
        ollama_host=ollama_host,
        role="default",
    )
    document = build_research_document(
        title=normalized_title,
        question=normalized_question,
        scope=normalized_scope,
        created_at=created_at,
        body=raw,
    )
    return {
        "ok": True,
        "mode": "dry-run",
        "research_version": MANUAL_RESEARCH_VERSION,
        "title": normalized_title,
        "question": normalized_question,
        "scope": normalized_scope,
        "created_at": created_at,
        "relative_path": research_relative_path(created_at, normalized_title),
        "document": document,
    }


def generate_manual_research_continuation_note(
    *,
    question: str,
    scope: str,
    continuation: dict,
    title: str | None = None,
    model: str | None = None,
    ollama_host: str = OLLAMA_HOST,
) -> dict:
    """Generate a dry-run manual research continuation note."""
    normalized_question = _require_text(question, "question")
    normalized_scope = _require_text(scope, "scope")
    normalized_title = _require_text(
        title or derive_research_title(normalized_question),
        "title",
    )
    created_at = _now()
    messages = build_manual_research_continuation_messages(
        title=normalized_title,
        question=normalized_question,
        scope=normalized_scope,
        continuation=continuation,
    )
    raw = chat_completion_text(
        messages,
        model=model or CHAT_MODEL,
        ollama_host=ollama_host,
        role="default",
    )
    document = build_research_continuation_document(
        title=normalized_title,
        question=normalized_question,
        scope=normalized_scope,
        created_at=created_at,
        body=raw,
        continuation=continuation,
    )
    return {
        "ok": True,
        "mode": "dry-run",
        "research_version": MANUAL_RESEARCH_CONTINUATION_VERSION,
        "title": normalized_title,
        "question": normalized_question,
        "scope": normalized_scope,
        "created_at": created_at,
        "relative_path": research_relative_path(created_at, normalized_title),
        "document": document,
        "continuation": continuation,
    }


def write_manual_research_note(result: dict, *, workspace_root: Path = WORKSPACE_DIR) -> dict:
    """Write a generated research note to the workspace without registration/indexing."""
    workspace_root = ensure_workspace(Path(workspace_root))
    relative_path = result["relative_path"]
    target = resolve_workspace_path(relative_path, workspace_root)
    if target.exists():
        raise ManualResearchError(f"Research note already exists: {relative_path}")
    write_result = write_workspace_file(
        relative_path,
        result["document"],
        root=workspace_root,
    )
    return write_result


def _research_date(created_at: str) -> str:
    return datetime.fromisoformat(created_at).date().isoformat()


def manual_research_metadata(result: dict) -> dict:
    """Return deterministic artifact metadata for a manual research note."""
    metadata = {
        "source_type": "research",
        "source_role": "research_reference",
        "origin": "manual_research",
        "research_question": result["question"],
        "research_title": result["title"],
        "research_date": _research_date(result["created_at"]),
        "created_by": "admin_cli",
        "research_version": result.get("research_version", MANUAL_RESEARCH_VERSION),
        "provisional": True,
    }
    continuation = result.get("continuation")
    if continuation:
        metadata.update(
            {
                "artifact_type": "research_note",
                "continuation_mode": "manual",
                "continuation_of_path": continuation.get("path"),
                "continuation_of_title": continuation.get("title"),
                "continuation_of_research_date": continuation.get("research_date"),
                "continuation_source_registered": bool(continuation.get("registered")),
            }
        )
        if continuation.get("artifact_id"):
            metadata["continuation_of_artifact_id"] = continuation["artifact_id"]
    return metadata


def register_manual_research_artifact(
    result: dict,
    *,
    workspace_root: Path = WORKSPACE_DIR,
) -> dict:
    """Register and index a written manual research note as research memory."""
    root = ensure_workspace(Path(workspace_root))
    relative_path = result["relative_path"]
    target = resolve_workspace_path(relative_path, root)
    if not target.exists():
        raise ManualResearchError(f"Manual research note file not found: {relative_path}")
    if list_artifacts(path=relative_path, workspace_root=root):
        raise ManualResearchError(f"Manual research note already registered: {relative_path}")
    if research_chunks_exist(relative_path):
        raise ManualResearchError(f"Manual research chunks already exist for {relative_path}")

    metadata = manual_research_metadata(result)
    title = f"Research Note — {result['title']}"
    content = target.read_text(encoding="utf-8")
    artifact = create_artifact(
        artifact_type="research_note",
        title=title,
        path=relative_path,
        status="active",
        source="manual_research",
        metadata=metadata,
        workspace_root=root,
    )
    indexing = index_manual_research_note(
        artifact_id=artifact["artifact_id"],
        title=title,
        path=relative_path,
        text=content,
        metadata=metadata,
    )
    if indexing["status"] == "failed":
        raise ManualResearchError(f"Manual research indexing failed: {indexing['reason']}")
    return {
        "artifact": artifact,
        "indexing": indexing,
        "path": relative_path,
    }


def run_manual_research(
    *,
    question: str,
    scope: str,
    title: str | None = None,
    write: bool = False,
    register_artifact: bool = False,
    continue_artifact: str | None = None,
    continue_file: str | None = None,
    model: str | None = None,
    workspace_root: Path = WORKSPACE_DIR,
) -> dict:
    """Generate, and optionally write, a manual research note."""
    if register_artifact and not write:
        raise ManualResearchError("--register-artifact requires --write")
    if continue_artifact and continue_file:
        raise ManualResearchError("--continue-artifact and --continue-file are mutually exclusive")

    if continue_artifact:
        continuation = load_research_continuation_artifact(
            continue_artifact,
            workspace_root=workspace_root,
        )
        result = generate_manual_research_continuation_note(
            question=question,
            scope=scope,
            title=title,
            continuation=continuation,
            model=model,
        )
    elif continue_file:
        continuation = load_research_continuation_file(
            continue_file,
            workspace_root=workspace_root,
        )
        result = generate_manual_research_continuation_note(
            question=question,
            scope=scope,
            title=title,
            continuation=continuation,
            model=model,
        )
    else:
        result = generate_manual_research_note(
            question=question,
            scope=scope,
            title=title,
            model=model,
        )
    result["mode"] = "write" if write else "dry-run"
    if write:
        result["write_result"] = write_manual_research_note(
            result,
            workspace_root=workspace_root,
        )
        if register_artifact:
            result["artifact_result"] = register_manual_research_artifact(
                result,
                workspace_root=workspace_root,
            )
    return result
