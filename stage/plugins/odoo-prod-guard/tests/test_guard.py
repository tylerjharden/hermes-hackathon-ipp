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

PKG = load_package(Path(__file__).resolve().parents[1], "odoo_prod_guard")
PLUGIN = Path(__file__).resolve().parents[1]


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return tmp_path


def test_prod_gate_and_mock_read(home):
    config = {"env": "prod", "routine_allowlist": ["account.move:action_post"]}
    log = PKG.log.GateLog()
    version = json.loads(PKG.tools.make_handlers(lambda: config)["odoo_version"]({}))
    assert version["mock"] is True
    assert version["server_version"] == "19.0-mock"
    assert PKG.tools.gate_call("odoo_search_read", {"model": "sale.order", "method": "search_read"}, config, log) is None
    assert PKG.tools.gate_call("odoo_call", {"model": "sale.order", "method": "search_read"}, config, log) is None
    assert PKG.tools.gate_call("odoo_call", {"model": "account.move", "method": "action_post"}, config, log) is None
    gated = PKG.tools.gate_call("odoo_call", {"model": "res.partner", "method": "unlink"}, config, log)
    assert gated["action"] == "approve"
    dev = PKG.tools.gate_call(
        "odoo_call",
        {"model": "res.partner", "method": "unlink"},
        {"env": "dev", "routine_allowlist": []},
        log,
    )
    assert dev is None
    summary = log.read_summary()
    decisions = [event["decision"] for event in summary["events"]]
    assert "approve" in decisions
    assert "allowed" in decisions
    assert "warn" in decisions


def test_unknown_env_fails_closed(home):
    directive = PKG.tools.gate_call(
        "odoo_call",
        {"model": "res.partner", "method": "write"},
        {"env": "staging", "routine_allowlist": []},
        PKG.log.GateLog(),
    )
    assert directive["action"] == "approve"


def test_live_call_posts_json2():
    seen = {}

    def transport(method, url, headers, body):
        seen["method"] = method
        seen["url"] = url
        seen["db"] = headers.get("X-Odoo-Database")
        seen["auth"] = headers.get("Authorization")
        seen["body"] = body
        return {"result": True}

    client = PKG.client.OdooClient(
        "https://odoo.example.com",
        "prod",
        "bot",
        "real-key",
        transport=transport,
    )
    client.call("res.partner", "write", [], {"ids": [1], "values": {"name": "Ada"}})
    assert seen["method"] == "POST"
    assert seen["url"] == "https://odoo.example.com/json/2/res.partner/write"
    assert seen["db"] == "prod"
    assert seen["auth"] == "bearer real-key"
    assert seen["body"]["ids"] == [1]


def test_mock_key_skips_transport():
    def transport(method, url, headers, body):
        raise AssertionError("mock opened the network")

    client = PKG.client.OdooClient("mock", "mock", "mock", "mock", transport=transport)
    assert client.version()["mock"] is True


def test_register_and_hook_kwargs(home):
    class Ctx:
        def __init__(self):
            self.tools = {}
            self.hooks = {}

        def register_tool(self, **kwargs):
            self.tools[kwargs["name"]] = kwargs

        def register_hook(self, name, callback):
            self.hooks.setdefault(name, []).append(callback)

        def register_skill(self, *args, **kwargs):
            return None

        def get_config(self, key, default=None):
            values = {"env": "prod", "routine_allowlist": ["account.move:action_post"]}
            return values.get(key, default)

    ctx = Ctx()
    PKG.register(ctx)
    manifest = (PLUGIN / "plugin.yaml").read_text()
    for name in ("odoo_call", "odoo_search_read", "odoo_version"):
        assert name in ctx.tools
        assert f"- {name}" in manifest
    directive = ctx.hooks["pre_tool_call"][0](
        "odoo_call",
        {"model": "res.partner", "method": "create"},
        task_id="t",
        unexpected=True,
    )
    assert directive["action"] == "approve"


def test_plugin_js_has_no_forbidden_surface():
    text = (PLUGIN / "desktop" / "plugin.js").read_text()
    for banned in ("eval(", "new Function", "import(", "data-slot", "window.hermesDesktop", "fixture"):
        assert banned not in text
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


def test_dashboard_module_parses():
    ast.parse((PLUGIN / "dashboard" / "plugin_api.py").read_text())


def test_pane_audit_does_not_execute(home):
    log = PKG.log.GateLog()
    events = log.recent()
    gated = next(event for event in events if event["decision"] == "approve")
    result = log.audit(gated["id"], "deny")
    assert result["executed"] is False
    assert "not executed" in result["event"]["audit"]
    summary = log.read_summary()
    assert summary["data_label"] == "demo data"
    assert "Harborline Logistics" in json.dumps(summary["events"])


def test_demo_script(home):
    env = os.environ.copy()
    env["HERMES_HOME"] = str(home)
    proc = subprocess.run(
        [sys.executable, str(PLUGIN / "demo.py")],
        cwd=str(home),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "gated=approve" in proc.stdout
    assert "mock=true" in proc.stdout


def test_source_avoids_secret_files():
    for path in PLUGIN.rglob("*.py"):
        if "tests" in path.parts:
            continue
        text = path.read_text()
        assert "auth.json" not in text
        assert "setattr(" not in text
        for line in text.splitlines():
            if "environ" in line:
                assert "ODOO_" not in line
                assert "HERMES_HOME" in line
