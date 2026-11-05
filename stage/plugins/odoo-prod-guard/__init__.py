"""Register Odoo tools and the production write gate."""

from __future__ import annotations

import json

from .log import GateLog
from .tools import SCHEMAS, gate_call, make_handlers


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            return [str(item) for item in json.loads(text)]
        return [part.strip() for part in text.split(",") if part.strip()]
    raise TypeError("routine_allowlist must be a list")


def register(ctx) -> None:
    def config() -> dict:
        return {
            "base_url": ctx.get_config("base_url", default=""),
            "database": ctx.get_config("database", default=""),
            "env": ctx.get_config("env", default="dev"),
            "routine_allowlist": _as_list(ctx.get_config("routine_allowlist", default=[])),
        }

    handlers = make_handlers(config)
    for name, schema in SCHEMAS.items():
        ctx.register_tool(
            name=name,
            toolset="odoo-prod-guard",
            schema=schema,
            handler=handlers[name],
        )

    def gate(tool_name, args, **kwargs):
        try:
            log = GateLog()
            current = config()
            log.write_summary(str(current.get("env") or "dev"), list(current.get("routine_allowlist") or []))
        except Exception:
            log = None
        return gate_call(tool_name, args, config(), log)

    ctx.register_hook("pre_tool_call", gate)
