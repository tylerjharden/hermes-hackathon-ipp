"""Tool handlers for the Odoo guard."""

from __future__ import annotations

import json

from .client import OdooClient, read_secret
from .guard import decide, decision_label
from .log import GateLog, pulse

PLUGIN_TOOLS = ("odoo_call", "odoo_search_read", "odoo_version")


def _dump(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True)


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            return json.loads(text)
        return [part.strip() for part in text.split(",") if part.strip()]
    raise TypeError("expected a list")


def _client(config: dict) -> OdooClient:
    url = read_secret("ODOO_URL") or str(config.get("base_url") or "")
    db = read_secret("ODOO_DB") or str(config.get("database") or "")
    user = read_secret("ODOO_USER")
    key = read_secret("ODOO_API_KEY")
    return OdooClient(url, db, user, key)


def make_handlers(config_fn):
    def version(args: dict, **kwargs) -> str:
        try:
            result = _client(config_fn()).version()
            return _dump({"ok": True, **result})
        except Exception as exc:
            return _dump({"ok": False, "error": str(exc)})

    def search_read(args: dict, **kwargs) -> str:
        try:
            model = str(args["model"])
            domain = _as_list(args.get("domain"))
            fields = [str(item) for item in _as_list(args.get("fields"))]
            limit = int(args.get("limit") or 5)
            result = _client(config_fn()).search_read(model, domain, fields, limit)
            return _dump({"ok": True, **result})
        except Exception as exc:
            return _dump({"ok": False, "error": str(exc)})

    def call(args: dict, **kwargs) -> str:
        try:
            model = str(args["model"])
            method = str(args["method"])
            call_args = _as_list(args.get("args"))
            call_kwargs = args.get("kwargs") or {}
            if isinstance(call_kwargs, str):
                call_kwargs = json.loads(call_kwargs)
            if not isinstance(call_kwargs, dict):
                raise TypeError("kwargs must be an object")
            result = _client(config_fn()).call(model, method, call_args, call_kwargs)
            return _dump({"ok": True, **result})
        except Exception as exc:
            return _dump({"ok": False, "error": str(exc)})

    return {
        "odoo_version": version,
        "odoo_search_read": search_read,
        "odoo_call": call,
    }


def gate_call(tool_name: str, args: dict | None, config: dict, log: GateLog | None = None) -> dict | None:
    if tool_name != "odoo_call":
        return None
    payload = args or {}
    pulse(f"Checking {payload.get('model') or 'model'}.{payload.get('method') or 'method'}")
    model = str(payload.get("model") or "")
    method = str(payload.get("method") or "")
    if not model or not method:
        return {
            "action": "block",
            "message": "odoo_call needs a model and a method.",
        }
    env = str(config.get("env") or "dev")
    patterns = [str(item) for item in _as_list(config.get("routine_allowlist"))]
    if env not in {"dev", "prod"}:
        env = "prod"
    label = decision_label(env, model, method, patterns)
    directive = decide(env, model, method, patterns)
    if label and log is not None:
        message = "" if directive is None else directive["message"]
        if label == "warn":
            message = f"Dev write {model}.{method} is not gated."
        if label == "allowed":
            message = f"Routine production write {model}.{method}."
        preview = json.dumps(
            {
                "model": model,
                "method": method,
                "args": payload.get("args") or [],
                "kwargs": payload.get("kwargs") or {},
            },
            default=str,
        )[:500]
        log.record(env, model, method, label, message, preview)
        log.write_summary(env, patterns)
    return directive


def _schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    }


SCHEMAS = {
    "odoo_call": _schema(
        "odoo_call",
        "Call an Odoo JSON-2 model method. Production writes outside the routine allowlist need Hermes approval.",
        {
            "model": {"type": "string"},
            "method": {"type": "string"},
            "args": {"type": "array"},
            "kwargs": {"type": "object"},
        },
        ["model", "method"],
    ),
    "odoo_search_read": _schema(
        "odoo_search_read",
        "Read Odoo records. This tool is never a write.",
        {
            "model": {"type": "string"},
            "domain": {"type": "array"},
            "fields": {"type": "array", "items": {"type": "string"}},
            "limit": {"type": "integer"},
        },
        ["model"],
    ),
    "odoo_version": _schema(
        "odoo_version",
        "Read the Odoo server version.",
        {},
        [],
    ),
}
