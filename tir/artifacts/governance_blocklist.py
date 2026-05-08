"""Governance/runtime filename blocklist for normal artifact ingestion."""

from pathlib import PurePosixPath


GOVERNANCE_FILE_NAMES = frozenset({
    "soul.md",
    "OPERATIONAL_GUIDANCE.md",
    "BEHAVIORAL_GUIDANCE.md",
    "PROJECT_STATE.md",
    "DECISIONS.md",
    "ROADMAP.md",
    "ACTIVE_TASK.md",
    "CODING_ASSISTANT_RULES.md",
    "DESIGN_RATIONALE.md",
    "Project_Anam_Phase_3_Governance_Reflection_Roadmap.md",
})

GOVERNANCE_FILE_REJECTION_MESSAGE = (
    "This file is a governance/runtime file and cannot be ingested as normal artifact memory."
)

_NORMALIZED_GOVERNANCE_FILE_NAMES = {
    name.casefold()
    for name in GOVERNANCE_FILE_NAMES
}


def governance_file_basename(filename: str) -> str:
    """Return the normalized basename used for governance filename checks."""
    normalized = (filename or "").replace("\\", "/")
    return PurePosixPath(normalized).name


def is_governance_file_name(filename: str) -> bool:
    """Return True for exact, case-insensitive governance/runtime basenames."""
    basename = governance_file_basename(filename)
    return basename.casefold() in _NORMALIZED_GOVERNANCE_FILE_NAMES
