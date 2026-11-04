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
        self._conn.commit()

    def record(self, env: str, model: str, method: str, decision: str, message: str) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO gate_events (at, env, model, method, decision, message)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (_now(), env, model, method, decision, message),
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
                "SELECT at, env, model, method, decision, message FROM gate_events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def write_summary(self, env: str, allowlist: list[str]) -> None:
        payload = {"env": env, "routine_allowlist": allowlist, "events": self.recent()}
        target = self.root / "summary.json"
        target.write_text(json.dumps(payload, indent=2))

    def read_summary(self) -> dict:
        target = self.root / "summary.json"
        events = self.recent()
        if not target.is_file():
            return {"env": "dev", "routine_allowlist": [], "events": events}
        stored = json.loads(target.read_text())
        stored["events"] = events
        return stored
