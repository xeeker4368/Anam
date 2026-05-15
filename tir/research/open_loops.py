"""Research open-loop preview and creation helpers.

Research open loops are source-linked unresolved questions from registered
research artifacts. They are not memory chunks, review items, working theories,
guidance, project decisions, or autonomous tasks.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from tir.artifacts.service import get_artifact
from tir.config import WORKSPACE_DIR
from tir.open_loops.service import create_open_loop, list_open_loops
from tir.workspace.service import resolve_workspace_path


RESEARCH_OPEN_LOOP_GENERATION_METHOD = "research_open_loop_v1"
RESEARCH_OPEN_LOOP_DAILY_ITERATION_LIMIT = 1
RESEARCH_OPEN_LOOP_SECTIONS = (
    "Open Questions",
    "New Open Questions",
    "Possible Follow-Ups",
)
LOW_SIGNAL_ENTRIES = {
    "none",
    "no open questions",
    "no new open questions",
    "no suggested followups",
    "no followups",
    "no follow ups",
    "nothing useful",
    "nothing meaningful",
    "n/a",
    "na",
}


class ResearchOpenLoopError(ValueError):
    """Raised when research open-loop preview/create cannot proceed."""


@dataclass(frozen=True)
class ResearchOpenLoopCandidate:
    title: str
    question: str
    source_section: str
    reason_it_matters: str
    next_action: str
    original_text: str
    normalized_key: str
    skipped_duplicate: bool = False

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "question": self.question,
            "source_section": self.source_section,
            "reason_it_matters": self.reason_it_matters,
            "next_action": self.next_action,
            "original_text": self.original_text,
            "normalized_key": self.normalized_key,
            "skipped_duplicate": self.skipped_duplicate,
        }


def _require_metadata(metadata: dict, artifact_id: str, field: str):
    if field not in metadata or metadata.get(field) in (None, ""):
        raise ResearchOpenLoopError(f"Research artifact is missing required metadata: {field}")
    return metadata[field]


def load_research_open_loop_source(
    artifact_id: str,
    *,
    workspace_root: Path = WORKSPACE_DIR,
) -> dict:
    """Load an active registered research artifact for open-loop extraction."""
    artifact = get_artifact(artifact_id)
    if artifact is None:
        raise ResearchOpenLoopError(f"Research artifact not found: {artifact_id}")
    if artifact.get("artifact_type") != "research_note":
        raise ResearchOpenLoopError(f"Artifact is not a research note: {artifact_id}")
    if artifact.get("status") != "active":
        raise ResearchOpenLoopError(f"Research artifact is not active: {artifact_id}")

    metadata = artifact.get("metadata") or {}
    for field, expected in (
        ("source_type", "research"),
        ("source_role", "research_reference"),
        ("origin", "manual_research"),
    ):
        value = _require_metadata(metadata, artifact_id, field)
        if value != expected:
            raise ResearchOpenLoopError(f"Research artifact is missing required metadata: {field}")
    if metadata.get("provisional") is not True:
        raise ResearchOpenLoopError("Research artifact is missing required metadata: provisional")
    for field in ("research_title", "research_date", "research_version"):
        _require_metadata(metadata, artifact_id, field)

    path = artifact.get("path")
    if not path:
        raise ResearchOpenLoopError("Research artifact is missing required metadata: path")
    target = resolve_workspace_path(path, Path(workspace_root))
    if not target.exists() or not target.is_file():
        raise ResearchOpenLoopError(f"Research artifact file not found: {path}")
    content = target.read_text(encoding="utf-8")

    return {
        "artifact": artifact,
        "metadata": metadata,
        "path": path,
        "content": content,
    }


def _section_pattern() -> re.Pattern:
    section_names = "|".join(re.escape(name) for name in RESEARCH_OPEN_LOOP_SECTIONS)
    return re.compile(
        rf"^##\s+({section_names})\s*$([\s\S]*?)(?=^##\s+|\Z)",
        re.MULTILINE,
    )


def _clean_candidate_text(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^\s*[-*+]\s+", "", cleaned)
    cleaned = re.sub(r"^\s*\d+[.)]\s+", "", cleaned)
    cleaned = re.sub(r"^\s*\[[ xX]\]\s+", "", cleaned)
    cleaned = cleaned.strip()
    return cleaned


def _normalize_candidate_key(text: str) -> str:
    normalized = text.strip().lower()
    normalized = re.sub(r"[^\w\s]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _is_low_signal(text: str) -> bool:
    normalized = _normalize_candidate_key(text)
    if not normalized:
        return True
    if normalized in LOW_SIGNAL_ENTRIES:
        return True
    return normalized.startswith("no useful") or normalized.startswith("nothing to")


def _extract_section_items(section_body: str) -> list[str]:
    lines = section_body.splitlines()
    bullet_items = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^([-*+]|\d+[.)])\s+", stripped) or re.match(r"^\[[ xX]\]\s+", stripped):
            bullet_items.append(_clean_candidate_text(stripped))

    if bullet_items:
        return [item for item in bullet_items if item]

    paragraphs = [
        re.sub(r"\s+", " ", block).strip()
        for block in re.split(r"\n\s*\n", section_body.strip())
    ]
    return [item for item in paragraphs if item]


def _candidate_from_item(item: str, source_section: str, research_title: str) -> ResearchOpenLoopCandidate | None:
    cleaned = _clean_candidate_text(item)
    if _is_low_signal(cleaned):
        return None

    title = cleaned[:120].rstrip()
    question = cleaned
    reason = f"Raised in {source_section} of research note: {research_title}."
    if source_section in {"Open Questions", "New Open Questions"}:
        next_action = f"Investigate: {question}"
    else:
        next_action = question
    return ResearchOpenLoopCandidate(
        title=title,
        question=question,
        source_section=source_section,
        reason_it_matters=reason,
        next_action=next_action,
        original_text=item,
        normalized_key=_normalize_candidate_key(question),
    )


def extract_research_open_loop_candidates(markdown: str, artifact: dict) -> list[dict]:
    """Extract deterministic open-loop candidates from research note Markdown."""
    metadata = artifact.get("metadata") or {}
    research_title = metadata.get("research_title") or artifact.get("title") or "research note"
    candidates = []
    seen = set()
    for match in _section_pattern().finditer(markdown or ""):
        source_section = match.group(1)
        body = match.group(2)
        for item in _extract_section_items(body):
            candidate = _candidate_from_item(item, source_section, research_title)
            if candidate is None or candidate.normalized_key in seen:
                continue
            seen.add(candidate.normalized_key)
            candidates.append(candidate.to_dict())
    return candidates


def _existing_duplicate_keys(artifact_id: str) -> set[str]:
    keys = set()
    for loop in list_open_loops(related_artifact_id=artifact_id, limit=500):
        if loop.get("status") not in {"open", "in_progress", "blocked"}:
            continue
        metadata = loop.get("metadata") or {}
        if metadata.get("generation_method") != RESEARCH_OPEN_LOOP_GENERATION_METHOD:
            continue
        question = metadata.get("question") or loop.get("title") or ""
        key = _normalize_candidate_key(question)
        if key:
            keys.add(key)
    return keys


def _candidate_metadata(candidate: dict, source: dict) -> dict:
    artifact = source["artifact"]
    metadata = source["metadata"]
    return {
        "generation_method": RESEARCH_OPEN_LOOP_GENERATION_METHOD,
        "source_type": "research",
        "source_artifact_id": artifact["artifact_id"],
        "source_research_version": metadata["research_version"],
        "source_research_title": metadata["research_title"],
        "source_research_date": metadata["research_date"],
        "source_research_path": source["path"],
        "source_section": candidate["source_section"],
        "question": candidate["question"],
        "reason_it_matters": candidate["reason_it_matters"],
        "original_text": candidate["original_text"],
        "provisional": True,
        "daily_iteration_limit": RESEARCH_OPEN_LOOP_DAILY_ITERATION_LIMIT,
        "daily_iteration_count": 0,
        "daily_iteration_local_date": None,
        "global_daily_cap_class": "research",
        "last_researched_at": None,
        "ready_for_synthesis": False,
        "diminishing_returns_note": None,
    }


def preview_research_open_loops(
    artifact_id: str,
    *,
    workspace_root: Path = WORKSPACE_DIR,
) -> dict:
    """Preview research open-loop candidates without creating records."""
    source = load_research_open_loop_source(artifact_id, workspace_root=workspace_root)
    artifact = source["artifact"]
    candidates = extract_research_open_loop_candidates(source["content"], artifact)
    duplicate_keys = _existing_duplicate_keys(artifact["artifact_id"])
    preview_candidates = []
    skipped_duplicates = []
    for candidate in candidates:
        candidate = dict(candidate)
        is_duplicate = candidate["normalized_key"] in duplicate_keys
        candidate["skipped_duplicate"] = is_duplicate
        candidate["metadata"] = _candidate_metadata(candidate, source)
        if is_duplicate:
            skipped_duplicates.append(candidate)
        preview_candidates.append(candidate)

    return {
        "artifact": artifact,
        "source_path": source["path"],
        "candidates": preview_candidates,
        "skipped_duplicates": skipped_duplicates,
        "candidate_count": len(preview_candidates),
        "skipped_duplicate_count": len(skipped_duplicates),
    }


def create_research_open_loops(
    artifact_id: str,
    *,
    workspace_root: Path = WORKSPACE_DIR,
) -> dict:
    """Create research open loops for non-duplicate candidates."""
    preview = preview_research_open_loops(artifact_id, workspace_root=workspace_root)
    artifact = preview["artifact"]
    created = []
    skipped_duplicates = []
    for candidate in preview["candidates"]:
        if candidate.get("skipped_duplicate"):
            skipped_duplicates.append(candidate)
            continue
        loop = create_open_loop(
            title=candidate["title"],
            description=(
                f"Research open loop from {candidate['source_section']} "
                f"in {artifact['metadata']['research_title']}."
            ),
            status="open",
            loop_type="unresolved_question",
            priority="normal",
            related_artifact_id=artifact["artifact_id"],
            source="manual_research",
            next_action=candidate["next_action"],
            metadata=candidate["metadata"],
        )
        created.append(loop)

    return {
        "artifact": artifact,
        "source_path": preview["source_path"],
        "candidates": preview["candidates"],
        "created": created,
        "skipped_duplicates": skipped_duplicates,
        "candidate_count": preview["candidate_count"],
        "created_count": len(created),
        "skipped_duplicate_count": len(skipped_duplicates),
    }
