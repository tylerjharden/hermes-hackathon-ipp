"""REST stats for the desktop pane. Mounted at /api/plugins/fleet-memory/."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()
_ROOT = Path(__file__).resolve().parents[1]


def _store():
    name = "fleet_memory_pkg"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            name,
            _ROOT / "__init__.py",
            submodule_search_locations=[str(_ROOT)],
        )
        module = importlib.util.module_from_spec(spec)
        module.__path__ = [str(_ROOT)]
        module.__package__ = name
        sys.modules[name] = module
        spec.loader.exec_module(module)
    home = os.environ.get("HERMES_HOME", "").strip()
    if not home:
        raise RuntimeError("HERMES_HOME is not set")
    return sys.modules[name].store.NoteStore(Path(home) / "fleet-memory")


@router.get("/summary")
async def summary():
    store = _store()
    payload = {
        "counts": store.counts(),
        "recalls": store.recent_recalls(),
    }
    store.close()
    return payload
