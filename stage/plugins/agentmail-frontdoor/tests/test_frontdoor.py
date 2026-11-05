import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from plugin_loader import load_package

PKG = load_package(Path(__file__).resolve().parents[1], "agentmail_frontdoor")


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return tmp_path


def test_offline_demo_reaches_needs_approval(home):
    handlers = PKG.tools.make_handlers(lambda: {"mode": "mock", "inbox_id": "ops"})
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "inbound.json").read_text()
    )
    handlers["am_claim_thread"](
        {"thread_id": fixture["thread_id"], "inbox_id": "ops", "subject": fixture["subject"]}
    )
    handlers["am_classify"](
        {"thread_id": fixture["thread_id"], "subject": fixture["subject"], "text": fixture["text"]}
    )
    drafted = json.loads(
        handlers["am_draft_reply"](
            {
                "thread_id": fixture["thread_id"],
                "to": fixture["from"],
                "body": "Holding for approval.",
            }
        )
    )
    row = json.loads(handlers["am_ledger_get"]({"thread_id": fixture["thread_id"]}))
    assert drafted["sent"] is False
    assert drafted["mock"] is True
    assert row["thread"]["label"] == "needs-approval"
    assert row["thread"]["classification"]["urgency"] == "high"
    assert row["thread"]["draft_id"] == "draft_mock_thrd_fixture_1001"
    db = home / "plugin-data" / "agentmail-frontdoor" / "ledger.db"
    assert db.is_file()


def test_label_jump_is_rejected(home):
    handlers = PKG.tools.make_handlers(lambda: {"mode": "mock", "inbox_id": "ops"})
    handlers["am_claim_thread"]({"thread_id": "t1", "inbox_id": "ops"})
    result = json.loads(handlers["am_ledger_upsert"]({"thread_id": "t1", "event": "approve"}))
    assert result["ok"] is False
    assert result["error"] == "illegal_transition"


def test_send_gate_blocks_strangers_and_approves_allowlist():
    block = PKG.hooks.pre_tool_call(
        "message_send",
        {"to": "stranger@example.com"},
        ["ops@example.com"],
    )
    assert block["action"] == "block"
    approve = PKG.hooks.pre_tool_call(
        "draft_send",
        {"to": "ops@example.com"},
        ["ops@example.com"],
    )
    assert approve["action"] == "approve"
    missing = PKG.hooks.pre_tool_call("message_send", {}, [])
    assert missing["action"] == "block"
    already = PKG.hooks.pre_tool_call(
        "message_send",
        {"to": "stranger@example.com"},
        [],
        approved=True,
    )
    assert already is None
    draft = PKG.hooks.pre_tool_call(
        "am_draft_reply",
        {"to": "vendor@example.com", "body": "hello"},
        [],
    )
    assert draft is None
    forced = PKG.hooks.pre_tool_call(
        "am_draft_reply",
        {"to": "vendor@example.com", "send": True},
        [],
    )
    assert forced["action"] == "block"


def test_live_draft_posts_to_drafts_endpoint_not_send():
    seen = {}

    def transport(method, url, headers, body):
        seen["method"] = method
        seen["url"] = url
        seen["body"] = body
        seen["auth"] = headers.get("Authorization")
        return {"draft_id": "draft_live_1"}

    client = PKG.client.AgentMailClient("real-key", "live", transport=transport)
    created = client.create_draft("ops", "thrd_1", ["a@example.com"], "Re", "body", ["needs-approval"])
    assert created["draft_id"] == "draft_live_1"
    assert seen["method"] == "POST"
    assert seen["url"] == "https://api.agentmail.to/v0/inboxes/ops/drafts"
    assert seen["url"].endswith("/send") is False
    assert seen["auth"] == "Bearer real-key"
    assert "send" not in seen["body"]


def test_mock_key_does_not_call_transport():
    def transport(method, url, headers, body):
        raise AssertionError("mock mode opened the network")

    client = PKG.client.AgentMailClient("mock", "auto", transport=transport)
    created = client.create_draft("ops", "thrd_1", ["a@example.com"], "Re", "body", [])
    assert created["mock"] is True
    assert created["sent"] is False


def test_register_seeds_fixture_thread(home):
    class Ctx:
        def register_tool(self, **kwargs):
            return None

        def register_hook(self, name, callback):
            return None

        def register_skill(self, *args, **kwargs):
            return None

        def get_config(self, key, default=None):
            return default

    PKG.register(Ctx())
    row = json.loads(PKG.tools.make_handlers(lambda: {"mode": "mock", "inbox_id": "ops"})["am_ledger_get"](
        {"thread_id": "thrd_fixture_1001"}
    ))
    assert row["ok"] is True
    assert row["thread"]["label"] == "triage"
    classified = json.loads(PKG.tools.make_handlers(lambda: {"mode": "mock", "inbox_id": "ops"})["am_classify"](
        {"thread_id": "thrd_fixture_1001"}
    ))
    assert classified["thread"]["classification"]["urgency"] == "high"


def test_register_matches_manifest():
    class Ctx:
        def __init__(self):
            self.tools = {}
            self.hooks = {}
            self.skills = []

        def register_tool(self, **kwargs):
            self.tools[kwargs["name"]] = kwargs

        def register_hook(self, name, callback):
            self.hooks.setdefault(name, []).append(callback)

        def register_skill(self, *args, **kwargs):
            self.skills.append(args)

        def get_config(self, key, default=None):
            return default

    ctx = Ctx()
    PKG.register(ctx)
    manifest = (Path(__file__).resolve().parents[1] / "plugin.yaml").read_text()
    for name in ctx.tools:
        assert f"- {name}" in manifest
    assert "pre_tool_call" in ctx.hooks
    ctx.hooks["pre_tool_call"][0]("am_ledger_get", {"thread_id": "t"}, task_id="x", extra=1)


def test_demo_script(home):
    env = os.environ.copy()
    env["HERMES_HOME"] = str(home)
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[1] / "demo.py")],
        cwd=str(home),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "label=needs-approval" in proc.stdout
    assert "sent=false" in proc.stdout


def test_source_does_not_read_dotenv_or_override_core():
    root = Path(__file__).resolve().parents[1]
    for path in root.rglob("*.py"):
        if "tests" in path.parts:
            continue
        text = path.read_text()
        assert "auth.json" not in text
        assert "load_dotenv" not in text
        assert "sys.modules[" not in text
        for line in text.splitlines():
            if "environ" in line:
                assert "AGENTMAIL_API_KEY" not in line
                assert "HERMES_HOME" in line
