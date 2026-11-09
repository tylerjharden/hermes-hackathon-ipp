"""REST stats for the desktop pane. Mounted at /api/plugins/fleet-memory/."""

from __future__ import annotations

import importlib.util
import json
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
    from agent.secret_scope import get_secret
    token = ""
    try:
        token = (get_secret("NOTION_TOKEN") or "").strip()
    except Exception:
        token = ""
    if token == "mock":
        token = ""
    status = {"at": "", "line": "Watching the local store"}
    status_path = store.root / "status.json"
    if status_path.is_file():
        try:
            status = json.loads(status_path.read_text())
        except Exception:
            status = status
    from datetime import datetime, timezone
    payload = {
        "counts": store.counts(),
        "recalls": store.recent_recalls(),
        "notes": store.recent_notes(),
        "backend": "notion" if token else "local",
        "data_label": "notion" if token else "local store",
        "status": status,
        "server_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    store.close()
    return payload
