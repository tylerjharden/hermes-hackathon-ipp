"""Thread ledger and the front-door label state machine."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

LABELS = (
    "triage",
    "delegated",
    "awaiting-worker",
    "needs-approval",
    "done",
)

_NEXT = {
    ("triage", "delegate"): "delegated",
    ("triage", "draft"): "needs-approval",
    ("delegated", "assign"): "awaiting-worker",
    ("delegated", "draft"): "needs-approval",
    ("awaiting-worker", "draft"): "needs-approval",
    ("awaiting-worker", "complete"): "done",
    ("needs-approval", "approve"): "done",
    ("needs-approval", "return"): "triage",
}


class LedgerError(Exception):
    def __init__(self, code: str, **detail: object) -> None:
        self.code = code
        self.detail = detail
        super().__init__(code)


def transition(label: str, event: str) -> str:
    try:
        return _NEXT[(label, event)]
    except KeyError as exc:
        raise LedgerError("illegal_transition", label=label, event=event) from exc


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Ledger:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS threads (
                thread_id TEXT PRIMARY KEY,
                inbox_id TEXT NOT NULL,
                label TEXT NOT NULL,
                classification TEXT NOT NULL DEFAULT '',
                worker TEXT NOT NULL DEFAULT '',
                draft_id TEXT NOT NULL DEFAULT '',
                draft_body TEXT NOT NULL DEFAULT '',
                recipient TEXT NOT NULL DEFAULT '',
                subject TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            )
            """
        )
        columns = {row[1] for row in self._conn.execute("PRAGMA table_info(threads)")}
        for name, decl in (
            ("body", "TEXT NOT NULL DEFAULT ''"),
            ("from_name", "TEXT NOT NULL DEFAULT ''"),
            ("from_addr", "TEXT NOT NULL DEFAULT ''"),
            ("send_state", "TEXT NOT NULL DEFAULT ''"),
        ):
            if name not in columns:
                self._conn.execute(f"ALTER TABLE threads ADD COLUMN {name} {decl}")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                at TEXT NOT NULL,
                event TEXT NOT NULL,
                detail TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def get(self, thread_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM threads WHERE thread_id = ?", (thread_id,)
            ).fetchone()
        return _row(row) if row else None

    def claim(
        self,
        thread_id: str,
        inbox_id: str,
        subject: str = "",
        body: str = "",
        from_name: str = "",
        from_addr: str = "",
    ) -> dict:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO threads (
                    thread_id, inbox_id, label, subject, body, from_name, from_addr, updated_at
                )
                VALUES (?, ?, 'triage', ?, ?, ?, ?, ?)
                ON CONFLICT(thread_id) DO UPDATE SET
                    subject = CASE WHEN excluded.subject != '' THEN excluded.subject ELSE threads.subject END,
                    body = CASE WHEN excluded.body != '' THEN excluded.body ELSE threads.body END,
                    from_name = CASE WHEN excluded.from_name != '' THEN excluded.from_name ELSE threads.from_name END,
                    from_addr = CASE WHEN excluded.from_addr != '' THEN excluded.from_addr ELSE threads.from_addr END,
                    updated_at = excluded.updated_at
                """,
                (thread_id, inbox_id, subject, body, from_name, from_addr, _now()),
            )
            self._history_unlocked(thread_id, "claim", "Claimed into triage.")
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM threads WHERE thread_id = ?", (thread_id,)
            ).fetchone()
        return _row(row)

    def list_threads(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM threads ORDER BY updated_at DESC, thread_id ASC"
            ).fetchall()
        return [_row(row) for row in rows]

    def history(self, thread_id: str, limit: int = 20) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT at, event, detail FROM history
                WHERE thread_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (thread_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def classify(self, thread_id: str, classification: dict) -> dict:
        payload = json.dumps(classification, sort_keys=True)
        with self._lock:
            cur =             self._conn.execute(
                "UPDATE threads SET classification = ?, updated_at = ? WHERE thread_id = ?",
                (payload, _now(), thread_id),
            )
            intent = str(classification.get("intent") or "general")
            urgency = str(classification.get("urgency") or "normal")
            self._history_unlocked(thread_id, "classify", f"Classified {intent}, {urgency}.")
            self._conn.commit()
            if cur.rowcount == 0:
                raise LedgerError("not_found", thread_id=thread_id)
        found = self.get(thread_id)
        if found is None:
            raise LedgerError("not_found", thread_id=thread_id)
        return found

    def route(self, thread_id: str, worker: str) -> dict:
        row = self._require(thread_id)
        label = row["label"]
        if label == "triage":
            return self._apply(thread_id, "delegate", worker=worker)
        if label == "delegated":
            return self._apply(thread_id, "assign", worker=worker)
        if label == "awaiting-worker":
            return self._apply_fields(thread_id, worker=worker)
        raise LedgerError("illegal_transition", label=label, event="route")

    def draft(self, thread_id: str, body: str, recipient: str, draft_id: str) -> dict:
        row = self._require(thread_id)
        if row["label"] != "needs-approval":
            self._apply(thread_id, "draft")
        return self._apply_fields(
            thread_id,
            draft_body=body,
            recipient=recipient,
            draft_id=draft_id,
        )

    def apply_event(self, thread_id: str, event: str) -> dict:
        self._require(thread_id)
        return self._apply(thread_id, event)

    def update_fields(self, thread_id: str, **fields: str) -> dict:
        self._require(thread_id)
        return self._apply_fields(thread_id, **fields)

    def _require(self, thread_id: str) -> dict:
        row = self.get(thread_id)
        if row is None:
            raise LedgerError("not_found", thread_id=thread_id)
        return row

    def _apply(self, thread_id: str, event: str, worker: str | None = None) -> dict:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM threads WHERE thread_id = ?", (thread_id,)
            ).fetchone()
            if row is None:
                raise LedgerError("not_found", thread_id=thread_id)
            label = transition(row["label"], event)
            if worker is None:
                self._conn.execute(
                    "UPDATE threads SET label = ?, updated_at = ? WHERE thread_id = ?",
                    (label, _now(), thread_id),
                )
            else:
                self._conn.execute(
                    "UPDATE threads SET label = ?, worker = ?, updated_at = ? WHERE thread_id = ?",
                    (label, worker, _now(), thread_id),
                )
            self._history_unlocked(thread_id, event, f"Label is now {label}.")
            self._conn.commit()
            stored = self._conn.execute(
                "SELECT * FROM threads WHERE thread_id = ?", (thread_id,)
            ).fetchone()
        return _row(stored)

    def _apply_fields(self, thread_id: str, **fields: str) -> dict:
        allowed = {"worker", "draft_body", "recipient", "draft_id", "subject"}
        unknown = set(fields) - allowed
        if unknown:
            raise LedgerError("unknown_field", fields=sorted(unknown))
        assignments = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values()) + [_now(), thread_id]
        with self._lock:
            cur = self._conn.execute(
                f"UPDATE threads SET {assignments}, updated_at = ? WHERE thread_id = ?",
                values,
            )
            self._conn.commit()
            if cur.rowcount == 0:
                raise LedgerError("not_found", thread_id=thread_id)
            stored = self._conn.execute(
                "SELECT * FROM threads WHERE thread_id = ?", (thread_id,)
            ).fetchone()
        return _row(stored)

    def mark_send(self, thread_id: str, state: str, detail: str) -> dict:
        self._require(thread_id)
        with self._lock:
            self._conn.execute(
                "UPDATE threads SET send_state = ?, updated_at = ? WHERE thread_id = ?",
                (state, _now(), thread_id),
            )
            self._history_unlocked(thread_id, "send", detail)
            self._conn.commit()
            stored = self._conn.execute(
                "SELECT * FROM threads WHERE thread_id = ?", (thread_id,)
            ).fetchone()
        return _row(stored)

    def note(self, thread_id: str, event: str, detail: str) -> None:
        self._require(thread_id)
        with self._lock:
            self._history_unlocked(thread_id, event, detail)
            self._conn.commit()

    def _history_unlocked(self, thread_id: str, event: str, detail: str) -> None:
        self._conn.execute(
            "INSERT INTO history (thread_id, at, event, detail) VALUES (?, ?, ?, ?)",
            (thread_id, _now(), event, detail),
        )


def _row(row: sqlite3.Row) -> dict:
    data = dict(row)
    raw = data.get("classification") or ""
    if raw:
        data["classification"] = json.loads(raw)
    else:
        data["classification"] = None
    return data
