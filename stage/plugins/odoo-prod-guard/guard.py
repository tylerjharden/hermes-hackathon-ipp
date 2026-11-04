"""Pure prod-write gate. Reads pass. Dev does not ask for approval."""

from __future__ import annotations

import fnmatch

READ_METHODS = {
    "search",
    "search_read",
    "read",
    "fields_get",
    "name_search",
    "name_get",
    "search_count",
    "read_group",
    "get_views",
    "fields_view_get",
    "check_access_rights",
    "exists",
}


def is_write(method: str) -> bool:
    return method.strip() not in READ_METHODS


def matches_routine(model: str, method: str, patterns: list[str]) -> bool:
    for raw in patterns:
        text = str(raw).strip()
        if ":" not in text:
            continue
        model_pat, method_pat = text.split(":", 1)
        if fnmatch.fnmatch(model, model_pat) and fnmatch.fnmatch(method, method_pat):
            return True
    return False


def decide(env: str, model: str, method: str, patterns: list[str]) -> dict | None:
    """Return a pre_tool_call directive, or None when the call may proceed."""
    if not is_write(method):
        return None
    if env != "prod":
        return None
    if matches_routine(model, method, patterns):
        return None
    return {
        "action": "approve",
        "message": (
            f"Production write {model}.{method} is not on the routine allowlist. "
            "Hermes must ask before this call runs."
        ),
    }


def decision_label(env: str, model: str, method: str, patterns: list[str]) -> str | None:
    if not is_write(method):
        return None
    if env != "prod":
        return "warn"
    if matches_routine(model, method, patterns):
        return "allowed"
    return "approve"
