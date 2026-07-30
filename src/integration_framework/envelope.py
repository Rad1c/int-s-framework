"""
Standard client-to-server response envelope:

    {"success": 0|1, "payload": {...}, "error_message": "..."}

where success == 0 means OK and success == 1 means error.
"""

from typing import Any


def ok(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"success": 0, "payload": payload or {}, "error_message": ""}


def error(message: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"success": 1, "payload": payload or {}, "error_message": message}


def envelope(success: bool, payload: dict[str, Any] | None, error_message: str) -> dict[str, Any]:
    """Build the envelope from a handler's (success, payload, error_message) result."""
    return {"success": int(not success), "payload": payload or {}, "error_message": error_message}
