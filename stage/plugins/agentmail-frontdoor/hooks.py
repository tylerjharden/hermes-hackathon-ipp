"""Fail-closed send gate. Drafts are not sends."""

from __future__ import annotations

_SEND_NAMES = {
    "draft_send",
    "message_send",
    "send_draft",
    "send_message",
    "am_draft_send",
    "am_message_send",
}


def _is_send(tool_name: str, args: dict) -> bool:
    name = (tool_name or "").strip().lower().replace("-", "_")
    if name in _SEND_NAMES:
        return True
    if name.endswith("_draft_send") or name.endswith("_message_send"):
        return True
    if name.endswith("/send") or name.endswith(".send"):
        return True
    if args.get("send") is True:
        return True
    return False


def _recipients(args: dict) -> list[str]:
    found: list[str] = []
    for key in ("to", "recipient", "recipients", "cc", "bcc"):
        value = args.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            found.append(value)
        elif isinstance(value, list):
            found.extend(str(item) for item in value)
    cleaned = []
    for item in found:
        text = item.strip().lower()
        if text:
            cleaned.append(text)
    return cleaned


def _approval_active(args: dict, kwargs: dict) -> bool:
    if kwargs.get("approved") is True:
        return True
    if args.get("approved") is True:
        return True
    return False


def pre_tool_call(tool_name: str, args: dict | None, allowlist: list[str], **kwargs) -> dict | None:
    payload = args or {}
    if not _is_send(tool_name, payload):
        return None
    if _approval_active(payload, kwargs):
        return None
    recipients = _recipients(payload)
    if not recipients:
        return {
            "action": "block",
            "message": "Blocked send. No recipient was provided, so the front door fails closed.",
        }
    allowed = {item.strip().lower() for item in allowlist if str(item).strip()}
    blocked = [item for item in recipients if item not in allowed]
    if blocked:
        return {
            "action": "block",
            "message": (
                "Blocked send to non-allowlisted recipients: "
                + ", ".join(blocked)
                + ". Create a draft with am_draft_reply instead."
            ),
        }
    return {
        "action": "approve",
        "message": "Allowlisted send still needs Hermes approval. This plugin does not auto-send.",
    }
