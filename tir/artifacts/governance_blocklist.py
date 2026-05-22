"""Governance/runtime filename blocklist for normal artifact ingestion."""

from pathlib import PurePosixPath


GOVERNANCE_FILE_NAMES = frozenset({
    "soul.md",
    "OPERATIONAL_GUIDANCE.md",
    "BEHAVIORAL_GUIDANCE.md",
})

GOVERNANCE_FILE_REJECTION_MESSAGE = (
    "This file is a governance/runtime file and cannot be ingested as normal artifact memory."
)

SOURCE_TRACE_FILE_SUFFIXES = (
    ".moltbook-sources.json",
    ".web-sources.json",
    ".source-trace.json",
)

SOURCE_TRACE_REJECTION_MESSAGE = (
    "Source traces are provenance/audit files and are not ingestible artifacts."
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


def is_source_trace_path(path: str | PurePosixPath) -> bool:
    """Return True for source-trace sidecar paths or known source-trace basenames."""
    normalized = str(path or "").replace("\\", "/")
    folded = normalized.casefold()
    basename = PurePosixPath(normalized).name.casefold()
    if basename.endswith(SOURCE_TRACE_FILE_SUFFIXES):
        return True

    parts = [part for part in folded.split("/") if part and part != "."]
    return any(
        parts[index : index + 2] == ["research", "source-traces"]
        for index in range(max(len(parts) - 1, 0))
    )
