"""Primary reflection journal context for date-specific journal questions."""

import json
import re
from datetime import date, datetime
from pathlib import Path

from tir.config import WORKSPACE_DIR
from tir.memory.db import get_connection
from tir.workspace.service import resolve_workspace_path


PRIMARY_JOURNAL_CONTEXT_CHAR_BUDGET = 8000
PRIMARY_JOURNAL_CONTEXT_TRUNCATION_MARKER = "\n\n[primary journal context truncated]"

_JOURNAL_TERM_RE = re.compile(r"\b(?:reflection\s+journal|journal\s+entry|journal)\b", re.I)
_ISO_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
_MONTH_DATE_RE = re.compile(
    r"\b("
    + "|".join(sorted(_MONTHS, key=len, reverse=True))
    + r")\.?\s+(\d{1,2})(?:,\s*|\s+)?(\d{4})?\b",
    re.I,
)


def _now_year(now=None) -> int:
    if now is None:
        return datetime.now().astimezone().year
    if isinstance(now, datetime):
        return now.astimezone().year if now.tzinfo else now.year
    if isinstance(now, date):
        return now.year
    return datetime.now().astimezone().year


def _parse_iso_date(text: str) -> tuple[str | None, str | None]:
    match = _ISO_DATE_RE.search(text or "")
    if not match:
        return None, None
    raw = match.group(1)
    try:
        return date.fromisoformat(raw).isoformat(), raw
    except ValueError:
        return None, raw


def _parse_month_date(text: str, *, now=None) -> tuple[str | None, str | None, bool]:
    match = _MONTH_DATE_RE.search(text or "")
    if not match:
        return None, None, False
    month = _MONTHS[match.group(1).lower().rstrip(".")]
    day = int(match.group(2))
    year_text = match.group(3)
    year_inferred = year_text is None
    year = int(year_text) if year_text else _now_year(now)
    try:
        return date(year, month, day).isoformat(), match.group(0), year_inferred
    except ValueError:
        return None, match.group(0), year_inferred


def detect_journal_date_intent(text: str, *, now=None) -> dict:
    """Detect explicit reflection-journal date intent in a user prompt."""
    raw_text = text or ""
    if not _JOURNAL_TERM_RE.search(raw_text):
        return {
            "matched": False,
            "journal_date": None,
            "date_text": None,
            "year_inferred": False,
            "reason": "missing_journal_term",
        }

    iso_date, iso_text = _parse_iso_date(raw_text)
    if iso_date:
        return {
            "matched": True,
            "journal_date": iso_date,
            "date_text": iso_text,
            "year_inferred": False,
            "reason": "iso_journal_date",
        }

    month_date, month_text, year_inferred = _parse_month_date(raw_text, now=now)
    if month_date:
        return {
            "matched": True,
            "journal_date": month_date,
            "date_text": month_text,
            "year_inferred": year_inferred,
            "reason": "month_day_journal_date",
        }

    return {
        "matched": False,
        "journal_date": None,
        "date_text": None,
        "year_inferred": False,
        "reason": "missing_date",
    }


def _empty_meta(intent: dict, *, reason: str) -> dict:
    return {
        "included": False,
        "journal_date": intent.get("journal_date"),
        "artifact_id": None,
        "path": None,
        "chars": 0,
        "truncated": False,
        "budget_chars": PRIMARY_JOURNAL_CONTEXT_CHAR_BUDGET,
        "reason": reason,
        "year_inferred": bool(intent.get("year_inferred")),
        "duplicate_count": 0,
        "date_detected": bool(intent.get("matched")),
    }


def _journal_artifacts_for_date(journal_date: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM main.artifacts
               WHERE artifact_type = 'journal'
               ORDER BY
                 CASE WHEN status = 'active' THEN 0 ELSE 1 END,
                 updated_at DESC""",
        ).fetchall()
    matches = []
    for row in rows:
        artifact = dict(row)
        try:
            metadata = json.loads(artifact.get("metadata_json") or "{}")
        except json.JSONDecodeError:
            metadata = {}
        if metadata.get("journal_date") == journal_date:
            artifact["metadata"] = metadata
            matches.append(artifact)
    return matches


def _cap_context(text: str, *, prefix_chars: int = 0) -> tuple[str, bool]:
    available_chars = PRIMARY_JOURNAL_CONTEXT_CHAR_BUDGET - prefix_chars
    if available_chars <= 0:
        return PRIMARY_JOURNAL_CONTEXT_TRUNCATION_MARKER.strip(), True
    if len(text) <= available_chars:
        return text, False
    max_body = available_chars - len(PRIMARY_JOURNAL_CONTEXT_TRUNCATION_MARKER)
    if max_body <= 0:
        return PRIMARY_JOURNAL_CONTEXT_TRUNCATION_MARKER.strip(), True
    return text[:max_body].rstrip() + PRIMARY_JOURNAL_CONTEXT_TRUNCATION_MARKER, True


def build_primary_journal_context(
    text: str,
    *,
    now=None,
    workspace_root: Path = WORKSPACE_DIR,
) -> tuple[str | None, dict]:
    """Build a bounded primary journal context block for date-specific queries."""
    intent = detect_journal_date_intent(text, now=now)
    if not intent.get("matched"):
        return None, _empty_meta(intent, reason=intent.get("reason") or "no_journal_date_intent")

    journal_date = intent["journal_date"]
    artifacts = _journal_artifacts_for_date(journal_date)
    if not artifacts:
        return None, _empty_meta(intent, reason="journal_artifact_not_found")

    artifact = artifacts[0]
    relative_path = artifact.get("path")
    if not relative_path:
        meta = _empty_meta(intent, reason="journal_file_not_found")
        meta["artifact_id"] = artifact.get("artifact_id")
        meta["duplicate_count"] = len(artifacts)
        return None, meta

    try:
        journal_path = resolve_workspace_path(relative_path, workspace_root)
    except Exception:
        meta = _empty_meta(intent, reason="journal_file_not_found")
        meta["artifact_id"] = artifact.get("artifact_id")
        meta["path"] = relative_path
        meta["duplicate_count"] = len(artifacts)
        return None, meta
    if not journal_path.exists():
        meta = _empty_meta(intent, reason="journal_file_not_found")
        meta["artifact_id"] = artifact.get("artifact_id")
        meta["path"] = relative_path
        meta["duplicate_count"] = len(artifacts)
        return None, meta

    try:
        content = journal_path.read_text(encoding="utf-8")
    except OSError:
        meta = _empty_meta(intent, reason="journal_file_read_error")
        meta["artifact_id"] = artifact.get("artifact_id")
        meta["path"] = relative_path
        meta["duplicate_count"] = len(artifacts)
        return None, meta

    prefix = (
        f"[Primary reflection journal source — {journal_date}]\n\n"
        "This is the journal entry for the requested date. Treat it as the primary source "
        "for questions about that journal. Distinguish what the journal states from later interpretation.\n\n"
    )
    capped, truncated = _cap_context(content, prefix_chars=len(prefix))
    context = f"{prefix}{capped}"
    return context, {
        "included": True,
        "journal_date": journal_date,
        "artifact_id": artifact.get("artifact_id"),
        "path": relative_path,
        "chars": len(context),
        "truncated": truncated,
        "budget_chars": PRIMARY_JOURNAL_CONTEXT_CHAR_BUDGET,
        "reason": None,
        "year_inferred": bool(intent.get("year_inferred")),
        "duplicate_count": len(artifacts),
        "date_detected": True,
    }
