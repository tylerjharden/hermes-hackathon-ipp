"""Offline demo for the prod write gate."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from plugin_loader import load_package

pkg = load_package(Path(__file__).resolve().parent, "odoo_prod_guard")


def main() -> None:
    if not os.environ.get("HERMES_HOME"):
        os.environ["HERMES_HOME"] = tempfile.mkdtemp(prefix="odoo-prod-guard-")
    config = {
        "env": "prod",
        "routine_allowlist": ["account.move:action_post"],
        "base_url": "",
        "database": "",
    }
    log = pkg.log.GateLog()
    version = json.loads(pkg.tools.make_handlers(lambda: config)["odoo_version"]({}))
    read = pkg.tools.gate_call("odoo_search_read", {"model": "res.partner"}, config, log)
    routine = pkg.tools.gate_call(
        "odoo_call",
        {"model": "account.move", "method": "action_post"},
        config,
        log,
    )
    gated = pkg.tools.gate_call(
        "odoo_call",
        {"model": "res.partner", "method": "unlink"},
        config,
        log,
    )
    dev = pkg.tools.gate_call(
        "odoo_call",
        {"model": "res.partner", "method": "unlink"},
        {**config, "env": "dev"},
        log,
    )
    print(f"mock={str(version.get('mock')).lower()}")
    print(f"version={version.get('server_version')}")
    print(f"read={read}")
    print(f"routine={routine}")
    print(f"gated={gated['action'] if gated else None}")
    print(f"dev={dev}")
    if version.get("mock") is not True or gated["action"] != "approve" or routine is not None or dev is not None:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
