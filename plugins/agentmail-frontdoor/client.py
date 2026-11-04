"""AgentMail HTTP client. Mock mode never opens a socket."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable

API_BASE = "https://api.agentmail.to"
MOCK_KEY = "mock"

Transport = Callable[[str, str, dict, dict | None], dict]


def read_secret(name: str) -> str:
    try:
        from agent.secret_scope import get_secret
    except Exception:
        return ""
    value = get_secret(name)
    return (value or "").strip()


def resolve_mode(mode: str, api_key: str) -> str:
    if mode == "mock":
        return "mock"
    if mode == "live":
        return "live"
    if not api_key or api_key == MOCK_KEY:
        return "mock"
    return "live"


class AgentMailClient:
    def __init__(self, api_key: str, mode: str, transport: Transport | None = None) -> None:
        self.api_key = api_key
        self.mode = resolve_mode(mode, api_key)
        self._transport = transport or _urllib_transport

    def get_thread(self, inbox_id: str, thread_id: str) -> dict:
        if self.mode == "mock":
            return {"thread_id": thread_id, "inbox_id": inbox_id, "mock": True}
        return self._request(
            "GET", f"/v0/inboxes/{inbox_id}/threads/{thread_id}", None
        )

    def create_draft(
        self,
        inbox_id: str,
        thread_id: str,
        to: list[str],
        subject: str,
        text: str,
        labels: list[str],
    ) -> dict:
        if self.mode == "mock":
            return {
                "draft_id": f"draft_mock_{thread_id}",
                "mock": True,
                "sent": False,
            }
        body = {
            "to": to,
            "subject": subject,
            "text": text,
            "labels": labels,
            "client_id": thread_id,
        }
        return self._request("POST", f"/v0/inboxes/{inbox_id}/drafts", body)

    def set_labels(self, inbox_id: str, thread_id: str, label: str, previous: str | None) -> dict:
        if self.mode == "mock":
            return {"mock": True, "label": label}
        remove = [previous] if previous and previous != label else []
        body = {"add_labels": [label], "remove_labels": remove}
        return self._request(
            "PATCH", f"/v0/inboxes/{inbox_id}/threads/{thread_id}", body
        )

    def _request(self, method: str, path: str, body: dict | None) -> dict:
        if not self.api_key or self.api_key == MOCK_KEY:
            raise RuntimeError("AGENTMAIL_API_KEY is required for live mode")
        url = API_BASE + path
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        return self._transport(method, url, headers, body)


def _urllib_transport(method: str, url: str, headers: dict, body: dict | None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        raise RuntimeError(f"agentmail_http_{exc.code}: {detail}") from exc
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("agentmail_response_not_object")
    return parsed
