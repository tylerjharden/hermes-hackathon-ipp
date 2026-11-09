"""REST summary for the desktop pane. Mounted at /api/plugins/odoo-prod-guard/."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()
_ROOT = Path(__file__).resolve().parents[1]


def _package():
    name = "odoo_prod_guard_pkg"
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
    id: int
    decision: str


@router.get("/summary")
async def summary():
    log = _package().log.GateLog()
    return log.read_summary()


@router.post("/decision")
async def decision(body: Decision):
    log = _package().log.GateLog()
    try:
        return log.audit(body.id, body.decision)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
