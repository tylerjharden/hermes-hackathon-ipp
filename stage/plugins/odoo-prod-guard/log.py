"""Recent gate decisions. One sqlite file under the profile data dir."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from .paths import data_dir

PLUGIN_ID = "odoo-prod-guard"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class GateLog:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or data_dir(PLUGIN_ID)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.root / "gate.db", check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gate_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                at TEXT NOT NULL,
                env TEXT NOT NULL,
                model TEXT NOT NULL,
                method TEXT NOT NULL,
                decision TEXT NOT NULL,
                message TEXT NOT NULL
            )
            """
        )
        columns = {row[1] for row in self._conn.execute("PRAGMA table_info(gate_events)")}
        if "preview" not in columns:
            self._conn.execute("ALTER TABLE gate_events ADD COLUMN preview TEXT NOT NULL DEFAULT ''")
        if "audit" not in columns:
            self._conn.execute("ALTER TABLE gate_events ADD COLUMN audit TEXT NOT NULL DEFAULT ''")
        self._conn.commit()
        count = self._conn.execute("SELECT COUNT(*) AS n FROM gate_events").fetchone()["n"]
        if count == 0:
            self._seed_demo()
            self.write_summary("prod", ["account.move:action_post"])

    def _seed_demo(self) -> None:
        samples = (
            (
                "prod",
                "account.move",
                "action_post",
                "allowed",
                "Routine production write account.move.action_post.",
                '{"partner":"Harborline Logistics","move":"INV-1842","amount":"18420.00"}',
            ),
            (
                "prod",
                "res.partner",
                "unlink",
                "approve",
                "Production write res.partner.unlink is not on the routine allowlist.",
                '{"partner":"North Pier Freight","id":220}',
            ),
        )
        for env, model, method, decision, message, preview in samples:
            self._conn.execute(
                """
                INSERT INTO gate_events (at, env, model, method, decision, message, preview, audit)
                VALUES (?, ?, ?, ?, ?, ?, ?, '')
                """,
                (_now(), env, model, method, decision, message, preview),
            )
        self._conn.commit()

    def record(self, env: str, model: str, method: str, decision: str, message: str, preview: str = "") -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO gate_events (at, env, model, method, decision, message, preview, audit)
                VALUES (?, ?, ?, ?, ?, ?, ?, '')
                """,
                (_now(), env, model, method, decision, message, preview),
            )
            self._conn.execute(
                """
                DELETE FROM gate_events
                WHERE id NOT IN (SELECT id FROM gate_events ORDER BY id DESC LIMIT 50)
                """
            )
            self._conn.commit()

    def recent(self, limit: int = 20) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, at, env, model, method, decision, message, preview, audit
                FROM gate_events ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def audit(self, event_id: int, decision: str, actor: str = "operator") -> dict:
        person = _display_actor(actor)
        if decision == "approve":
            note = f"Approved by {person} - write not executed"
            state = "approved"
        elif decision == "deny":
            note = f"Denied by {person} - write not executed"
            state = "denied"
        else:
            raise ValueError("decision")
        with self._lock:
            cur = self._conn.execute(
                "UPDATE gate_events SET decision = ?, audit = ? WHERE id = ?",
                (state, note, event_id),
            )
            self._conn.commit()
            if cur.rowcount == 0:
                raise ValueError("not_found")
            row = self._conn.execute(
                """
                SELECT id, at, env, model, method, decision, message, preview, audit
                FROM gate_events WHERE id = ?
                """,
                (event_id,),
            ).fetchone()
        pulse(f"Pane {decision} recorded. No write was executed.")
        return {"ok": True, "executed": False, "event": dict(row)}

    def write_summary(self, env: str, allowlist: list[str]) -> None:
        payload = {"env": env, "routine_allowlist": allowlist, "events": self.recent()}
        target = self.root / "summary.json"
        target.write_text(json.dumps(payload, indent=2))

    def read_summary(self) -> dict:
        target = self.root / "summary.json"
        events = self.recent()
        if not target.is_file():
            stored = {"env": "dev", "routine_allowlist": []}
        else:
            stored = json.loads(target.read_text())
        stored["events"] = events
        from .client import current_backend
        stored["backend"] = current_backend()
        stored["data_label"] = "live" if stored["backend"] == "live" else "demo data"
        stored["status"] = read_status(self.root)
        stored["server_time"] = _now()
        return stored


def _display_actor(actor: str | None) -> str:
    person = str(actor or "").strip()
    if not person or person.lower() == "default":
        return "operator"
    return person


def pulse(line: str, root: Path | None = None) -> None:
    try:
        base = root or data_dir(PLUGIN_ID)
        base.mkdir(parents=True, exist_ok=True)
        (base / "status.json").write_text(json.dumps({"at": _now(), "line": line}))
    except Exception:
        return


def read_status(root: Path | None = None) -> dict:
    try:
        base = root or data_dir(PLUGIN_ID)
        target = base / "status.json"
    except Exception:
        return {"at": "", "line": "Watching the production gate"}
    if not target.is_file():
        return {"at": "", "line": "Watching the production gate"}
    try:
        return json.loads(target.read_text())
    except Exception:
        return {"at": "", "line": "Watching the production gate"}
