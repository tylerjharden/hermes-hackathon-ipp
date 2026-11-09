"""REST board for the desktop pane. Mounted at /api/plugins/agentmail-frontdoor/."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()
_ROOT = Path(__file__).resolve().parents[1]


def _package():
    name = "agentmail_frontdoor_pkg"
    if name in sys.modules:
        return sys.modules[name]
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
    return module


class Decision(BaseModel):
    thread_id: str
    decision: str
    actor: str = "operator"


@router.get("/board")
async def board(thread_id: str = ""):
    return _package().tools.board(thread_id)


@router.post("/decision")
async def decision(body: Decision):
    try:
        return _package().tools.pane_decision(body.thread_id, body.decision, body.actor)
    except Exception as exc:
        code = getattr(exc, "code", "") or exc.__class__.__name__
        raise HTTPException(status_code=400, detail=code) from exc
