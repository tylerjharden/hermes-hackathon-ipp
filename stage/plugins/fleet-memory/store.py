"""Local fleet notes. The profile directory comes from hermes_home."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

SEED = Path(__file__).resolve().parent / "data" / "fleet_ops_seed.json"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class NoteStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.root / "notes.db", check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                tags TEXT NOT NULL,
                source TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recalls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                at TEXT NOT NULL,
                query TEXT NOT NULL,
                hit_ids TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                at TEXT NOT NULL,
                session_id TEXT NOT NULL,
                user_text TEXT NOT NULL,
                assistant_text TEXT NOT NULL
            )
            """
        )
        self._conn.commit()
        self._seed()

    def close(self) -> None:
        self._conn.close()

    def _seed(self) -> None:
        count = self._conn.execute("SELECT COUNT(*) AS n FROM notes").fetchone()["n"]
        if count:
            return
        for note in json.loads(SEED.read_text()):
            self._insert(note, "seed")

    def _insert(self, note: dict, source: str) -> None:
        self._conn.execute(
            """
            INSERT INTO notes (id, title, body, tags, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                body = excluded.body,
                tags = excluded.tags,
                source = excluded.source,
                updated_at = excluded.updated_at
            """,
            (
                note["id"],
                note["title"],
                note["body"],
                json.dumps(note.get("tags") or []),
                source,
                _now(),
            ),
        )
        self._conn.commit()

    def ingest(self, note_id: str, title: str, body: str, tags: list[str]) -> dict:
        with self._lock:
            self._insert({"id": note_id, "title": title, "body": body, "tags": tags}, "local")
        return self.get(note_id)

    def get(self, note_id: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        return _note(row) if row else None

    def search(self, query: str, limit: int) -> list[dict]:
        tokens = [part for part in query.lower().split() if part]
        with self._lock:
            rows = self._conn.execute("SELECT * FROM notes").fetchall()
        ranked = []
        for row in rows:
            note = _note(row)
            hay = " ".join([note["title"], note["body"], " ".join(note["tags"])]).lower()
            score = sum(1 for token in tokens if token in hay) if tokens else 1
            if score:
                ranked.append((score, note))
        ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
        return [note for _, note in ranked[:limit]]

    def record_recall(self, query: str, hit_ids: list[str]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO recalls (at, query, hit_ids) VALUES (?, ?, ?)",
                (_now(), query, json.dumps(hit_ids)),
            )
            self._conn.commit()

    def recent_recalls(self, limit: int = 10) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT at, query, hit_ids FROM recalls ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        found = []
        for row in rows:
            item = dict(row)
            item["hit_ids"] = json.loads(item["hit_ids"])
            found.append(item)
        return found

    def append_turn(self, session_id: str, user_text: str, assistant_text: str) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO turns (at, session_id, user_text, assistant_text)
                VALUES (?, ?, ?, ?)
                """,
                (_now(), session_id, user_text, assistant_text),
            )
            self._conn.commit()

    def counts(self) -> dict:
        with self._lock:
            notes = self._conn.execute("SELECT COUNT(*) AS n FROM notes").fetchone()["n"]
            recalls = self._conn.execute("SELECT COUNT(*) AS n FROM recalls").fetchone()["n"]
            turns = self._conn.execute("SELECT COUNT(*) AS n FROM turns").fetchone()["n"]
        return {"notes": notes, "recalls": recalls, "turns": turns}


def _note(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["tags"] = json.loads(data["tags"])
    return data


def format_recall(notes: list[dict], budget_chars: int) -> str:
    lines = ["Fleet notes:"]
    used = len(lines[0])
    for note in notes:
        line = f"- {note['title']}: {note['body']}"
        if used + len(line) + 1 > budget_chars:
            break
        lines.append(line)
        used += len(line) + 1
    if len(lines) == 1:
        return ""
    return "\n".join(lines)
