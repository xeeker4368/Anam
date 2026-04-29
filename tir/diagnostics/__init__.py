"""Internal diagnostic issue registry helpers."""

from tir.diagnostics.service import (
    ALLOWED_DIAGNOSTIC_CATEGORIES,
    ALLOWED_DIAGNOSTIC_SEVERITIES,
    ALLOWED_DIAGNOSTIC_STATUSES,
    DiagnosticValidationError,
    create_diagnostic_issue,
    diagnostic_issue_to_dict,
    get_diagnostic_issue,
    list_diagnostic_issues,
    update_diagnostic_status,
)

__all__ = [
    "ALLOWED_DIAGNOSTIC_CATEGORIES",
    "ALLOWED_DIAGNOSTIC_SEVERITIES",
    "ALLOWED_DIAGNOSTIC_STATUSES",
    "DiagnosticValidationError",
    "create_diagnostic_issue",
    "diagnostic_issue_to_dict",
    "get_diagnostic_issue",
    "list_diagnostic_issues",
    "update_diagnostic_status",
]
