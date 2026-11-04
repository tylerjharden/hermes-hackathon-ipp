import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from plugin_loader import load_package

PKG = load_package(Path(__file__).resolve().parents[1], "fleet_memory")
PLUGIN = Path(__file__).resolve().parents[1]


def test_offline_recall_and_ingest(tmp_path):
    provider = PKG.provider.FleetMemoryProvider(token="mock")
    provider.initialize("s1", hermes_home=str(tmp_path))
    recalled = provider.prefetch("GL-14")
    assert "GL-14" in recalled
    assert "dock" in recalled.lower()
    status = json.loads(provider.handle_tool_call("fleet_memory_status", {}))
    assert status["notes"] == 6
    assert status["notion"] is False
    assert status["recalls"] == 1
    ingested = json.loads(provider.handle_tool_call(
        "fleet_memory_ingest",
        {"id": "late-truck", "title": "Late truck", "body": "Route GL-14 truck is holding at the gate.", "tags": ["gl-14"]},
    ))
    assert ingested["ok"] is True
    found = json.loads(provider.handle_tool_call("fleet_memory_search", {"query": "late truck", "limit": 3}))
    assert found["notes"][0]["id"] == "late-truck"
    db = tmp_path / "fleet-memory" / "notes.db"
    assert db.is_file()
    provider.shutdown()


def test_sync_turn_spawns_only_when_notion_is_configured(tmp_path):
    calls = []

    def spawner(target, name):
        calls.append((name, target))

    live = PKG.provider.FleetMemoryProvider(token="secret-token", spawner=spawner)
    live.initialize("s1", hermes_home=str(tmp_path / "live"))
    live.sync_turn("user", "assistant", session_id="s1")
    assert calls and calls[0][0] == "fleet-memory-sync"
    assert live.handle_tool_call("fleet_memory_status", {})
    status = json.loads(live.handle_tool_call("fleet_memory_status", {}))
    assert status["turns"] == 1
    live.shutdown()

    calls.clear()
    offline = PKG.provider.FleetMemoryProvider(token="mock", spawner=spawner)
    offline.initialize("s2", hermes_home=str(tmp_path / "offline"))
    offline.sync_turn("user", "assistant", session_id="s2")
    assert calls == []
    offline.shutdown()


def test_register_returns_a_new_instance():
    seen = []

    class Ctx:
        def register_memory_provider(self, provider):
            seen.append(provider)

        def register_skill(self, *args, **kwargs):
            return None

    PKG.register(Ctx())
    PKG.register(Ctx())
    assert seen[0] is not seen[1]
    assert seen[0].name == "fleet-memory"
    names = [item["name"] for item in seen[0].get_tool_schemas()]
    manifest = (PLUGIN / "plugin.yaml").read_text()
    for name in names:
        assert f"- {name}" in manifest


def test_second_initialize_is_rejected(tmp_path):
    provider = PKG.provider.FleetMemoryProvider(token="mock")
    provider.initialize("s1", hermes_home=str(tmp_path))
    with pytest.raises(RuntimeError):
        provider.initialize("s2", hermes_home=str(tmp_path / "other"))
    provider.shutdown()


def test_plugin_js_and_dashboard_parse():
    text = (PLUGIN / "desktop" / "plugin.js").read_text()
    for banned in ("eval(", "new Function", "import(", "data-slot", "window.hermesDesktop"):
        assert banned not in text
    ast.parse((PLUGIN / "dashboard" / "plugin_api.py").read_text())
    proc = subprocess.run(
        [
            "node",
            "--import",
            str(ROOT / "scripts" / "register-desktop-loader.mjs"),
            str(ROOT / "scripts" / "check-desktop.mjs"),
            str(PLUGIN / "desktop" / "plugin.js"),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert '"area":"panes"' in proc.stdout


def test_demo_script(tmp_path):
    env = os.environ.copy()
    env["HERMES_HOME"] = str(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(PLUGIN / "demo.py")],
        cwd=str(tmp_path),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "recall=GL-14" in proc.stdout
    assert "notion=false" in proc.stdout


def test_source_avoids_secret_files():
    for path in PLUGIN.rglob("*.py"):
        if "tests" in path.parts:
            continue
        text = path.read_text()
        assert "auth.json" not in text
        assert "setattr(" not in text
        for line in text.splitlines():
            if "environ" in line:
                assert "NOTION_TOKEN" not in line
                assert "HERMES_HOME" in line
