"""Restore demo data for the three plugins in the active Hermes profile."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from plugin_loader import load_package


def _home() -> Path:
    raw = os.environ.get("HERMES_HOME", "").strip()
    if not raw:
        raw = str(Path.home() / ".hermes")
        os.environ["HERMES_HOME"] = raw
    path = Path(raw)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _wipe(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.is_file():
        path.unlink()


def main() -> None:
    home = _home()
    mail_dir = home / "plugin-data" / "agentmail-frontdoor"
    odoo_dir = home / "plugin-data" / "odoo-prod-guard"
    fleet_dir = home / "fleet-memory"
    _wipe(mail_dir)
    _wipe(odoo_dir)
    _wipe(fleet_dir)

    mail = load_package(ROOT / "plugins" / "agentmail-frontdoor", "agentmail_frontdoor_reset")
    threads = mail.tools.ensure_demo_threads() or []
    odoo = load_package(ROOT / "plugins" / "odoo-prod-guard", "odoo_prod_guard_reset")
    log = odoo.log.GateLog()
    log.write_summary("prod", ["account.move:action_post"])
    fleet = load_package(ROOT / "plugins" / "fleet-memory", "fleet_memory_reset")
    provider = fleet.provider.FleetMemoryProvider(token="mock")
    provider.initialize("demo-reset", hermes_home=str(home))
    provider.prefetch("freight cutoff")
    provider.shutdown()

    names = ", ".join(row["from_name"] or row["thread_id"] for row in threads)
    print(f"home={home}")
    print(f"agentmail={len(threads)} threads ({names})")
    print(f"odoo={len(log.recent())} gate rows")
    print("fleet=local store reseeded")
    print("data_label=demo data")


if __name__ == "__main__":
    main()
