"""Minimal shared-secret API protection for local-network use."""

import hmac
import os


API_SECRET_HEADER = "x-anam-secret"
PUBLIC_API_PATHS = {
    "/api/health",
    "/api/system/health",
    "/api/system/capabilities",
}


def _configured_secret() -> str | None:
    secret = os.getenv("ANAM_API_SECRET")
    if secret is None:
        return None
    normalized = secret.strip()
    return normalized or None


def is_api_secret_configured() -> bool:
    """Return True when API shared-secret protection is enabled."""
    return _configured_secret() is not None


def is_public_api_path(path: str) -> bool:
    """Return True for public API paths allowed without the shared secret."""
    return path in PUBLIC_API_PATHS


def verify_api_secret(provided: str | None) -> bool:
    """Verify a provided API secret using constant-time comparison."""
    configured = _configured_secret()
    if configured is None:
        return True
    if provided is None:
        return False
    return hmac.compare_digest(provided, configured)
