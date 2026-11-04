"""Offline demo. Recalls a seeded dock note and ingests one local note."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from plugin_loader import load_package

pkg = load_package(Path(__file__).resolve().parent, "fleet_memory")


def main() -> None:
    home = os.environ.get("HERMES_HOME") or tempfile.mkdtemp(prefix="fleet-memory-")
    os.environ["HERMES_HOME"] = home
    provider = pkg.provider.FleetMemoryProvider(token="mock")
    provider.initialize("demo", hermes_home=home)
    recalled = provider.prefetch("GL-14")
    status = json.loads(provider.handle_tool_call("fleet_memory_status", {}))
    ingested = json.loads(provider.handle_tool_call(
        "fleet_memory_ingest",
        {"id": "demo-note", "title": "Demo note", "body": "Loaded from the offline demo.", "tags": ["demo"]},
    ))
    provider.sync_turn("where is GL-14", recalled, session_id="demo")
    print(f"recall={'GL-14' if 'GL-14' in recalled else 'missing'}")
    print(f"ingested={ingested['note']['id']}")
    print(f"notes={status['notes']}")
    print(f"notion={str(status['notion']).lower()}")
    if "GL-14" not in recalled or status["notion"] is not False or status["notes"] < 6:
        raise SystemExit(1)
    provider.shutdown()


if __name__ == "__main__":
    main()
