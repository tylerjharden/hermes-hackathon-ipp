"""Register the front-door tools and the send gate."""

from __future__ import annotations

from pathlib import Path

from .hooks import pre_tool_call
from .tools import SCHEMAS, make_handlers


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
            import json
            parsed = json.loads(text)
            return [str(item) for item in parsed]
        return [part.strip() for part in text.split(",") if part.strip()]
    raise TypeError("recipient_allowlist must be a list")


def register(ctx) -> None:
    def config() -> dict:
        return {
            "mode": ctx.get_config("mode", default="auto"),
            "inbox_id": ctx.get_config("inbox_id", default="ops"),
            "recipient_allowlist": _as_list(
                ctx.get_config("recipient_allowlist", default=[])
            ),
        }

    handlers = make_handlers(config)
    for name, schema in SCHEMAS.items():
        ctx.register_tool(
            name=name,
            toolset="agentmail-frontdoor",
            schema=schema,
            handler=handlers[name],
        )

    def gate(tool_name, args, **kwargs):
        current = config()
        return pre_tool_call(
            tool_name,
            args,
            current["recipient_allowlist"],
            **kwargs,
        )

    ctx.register_hook("pre_tool_call", gate)
    skill = Path(__file__).resolve().parent / "skills" / "frontdoor" / "SKILL.md"
    ctx.register_skill("frontdoor", skill, "Route inbound mail and draft replies. Do not send.")
