"""Odoo JSON-2 client. Mock mode returns fixture payloads and does not open a socket."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable

MOCK = "mock"
Transport = Callable[[str, str, dict, dict | None], dict]


def read_secret(name: str) -> str:
    try:
        from agent.secret_scope import get_secret
    except Exception:
        return ""
    return (get_secret(name) or "").strip()


def current_backend() -> str:
    if use_mock(read_secret("ODOO_URL"), read_secret("ODOO_DB"), read_secret("ODOO_USER"), read_secret("ODOO_API_KEY")):
        return "fixture"
    return "live"


def use_mock(url: str, db: str, user: str, api_key: str) -> bool:
    values = [url, db, user, api_key]
    if any(not value or value == MOCK for value in values):
        return True
    return False


class OdooClient:
    def __init__(
        self,
        url: str,
        db: str,
        user: str,
        api_key: str,
        transport: Transport | None = None,
    ) -> None:
        self.url = url.rstrip("/")
        self.db = db
        self.user = user
        self.api_key = api_key
        self.mock = use_mock(url, db, user, api_key)
        self._transport = transport or _urllib_transport

    def version(self) -> dict:
        if self.mock:
            return {"server_version": "19.0-mock", "mock": True}
        return self._request("GET", "/web/version", None)

    def search_read(self, model: str, domain: list, fields: list[str], limit: int) -> dict:
        if self.mock:
            return {
                "mock": True,
                "records": [
                    {"id": 1, "model": model, "name": "Harborline Logistics dock GL-14", "domain": domain, "fields": fields}
                ][:limit or 1],
            }
        body = {"domain": domain, "fields": fields, "limit": limit}
        return self._request("POST", f"/json/2/{model}/search_read", body)

    def call(self, model: str, method: str, args: list, kwargs: dict) -> dict:
        if self.mock:
            return {"mock": True, "model": model, "method": method, "ok": True}
        body = dict(kwargs)
        if args:
            body["args"] = args
        return self._request("POST", f"/json/2/{model}/{method}", body)

    def _request(self, method: str, path: str, body: dict | None) -> dict:
        if not self.url.startswith("https://"):
            raise RuntimeError("ODOO_URL must be https")
        headers = {
            "Authorization": f"bearer {self.api_key}",
            "X-Odoo-Database": self.db,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        return self._transport(method, self.url + path, headers, body)


def _urllib_transport(method: str, url: str, headers: dict, body: dict | None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        raise RuntimeError(f"odoo_http_{exc.code}: {detail}") from exc
    if not raw:
        return {}
    parsed = json.loads(raw)
    if isinstance(parsed, list):
        return {"records": parsed}
    if not isinstance(parsed, dict):
        raise RuntimeError("odoo_response_not_object")
    return parsed
