"""Register a new memory provider instance for this profile."""

from __future__ import annotations

from pathlib import Path

from .provider import FleetMemoryProvider


def register(ctx) -> None:
    ctx.register_memory_provider(FleetMemoryProvider())
    skill = Path(__file__).resolve().parent / "skills" / "fleet-ops" / "SKILL.md"
    ctx.register_skill("fleet-ops", skill, "Search and ingest local fleet ops notes.")
