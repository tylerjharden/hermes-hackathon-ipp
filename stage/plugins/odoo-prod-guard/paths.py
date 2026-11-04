"""Profile data directory. Never write into the plugin install tree."""

from __future__ import annotations

import os
from pathlib import Path


def data_dir(plugin_id: str) -> Path:
    try:
        from plugins.plugin_storage import plugin_data_dir

        path = Path(plugin_data_dir(plugin_id))
    except Exception:
        home = os.environ.get("HERMES_HOME", "").strip()
        if not home:
            raise RuntimeError(
                "HERMES_HOME is not set and plugins.plugin_storage is unavailable"
            )
        path = Path(home) / "plugin-data" / plugin_id
    path.mkdir(parents=True, exist_ok=True)
    return path
