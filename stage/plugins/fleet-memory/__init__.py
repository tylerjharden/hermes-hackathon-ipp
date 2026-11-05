"""Register a new memory provider instance for this profile."""

from __future__ import annotations

from pathlib import Path

from .provider import SCHEMAS, TOOL_HANDLERS, FleetMemoryProvider


def register(ctx) -> None:
    ctx.register_memory_provider(FleetMemoryProvider())
    for schema in SCHEMAS:
        ctx.register_tool(
            name=schema["name"],
            toolset="fleet-memory",
            schema=schema,
            handler=TOOL_HANDLERS[schema["name"]],
        )
    skill = Path(__file__).resolve().parent / "skills" / "fleet-ops" / "SKILL.md"
    ctx.register_skill("fleet-ops", skill, "Search and ingest local fleet ops notes.")
