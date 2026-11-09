"""Local fleet notes. The profile directory comes from hermes_home."""

from __future__ import annotations

import json
import math
import os
import re
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
        columns = {row[1] for row in self._conn.execute("PRAGMA table_info(recalls)")}
        if "source" not in columns:
            self._conn.execute("ALTER TABLE recalls ADD COLUMN source TEXT NOT NULL DEFAULT 'tool'")
        if "hits" not in columns:
            self._conn.execute("ALTER TABLE recalls ADD COLUMN hits TEXT NOT NULL DEFAULT '[]'")
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
        with self._lock:
            rows = self._conn.execute("SELECT * FROM notes").fetchall()
        notes = [_note(row) for row in rows]
        return _bm25(notes, query, limit)

    def record_recall(self, query: str, hit_ids: list[str], source: str = "tool", hits: list[dict] | None = None) -> None:
        cards = []
        for hit in hits or []:
            cards.append({
                "id": hit.get("id"),
                "title": hit.get("title") or "",
                "snippet": hit.get("snippet") or (hit.get("body") or "")[:160],
                "score": hit.get("score") or 0,
            })
        with self._lock:
            self._conn.execute(
                "INSERT INTO recalls (at, query, hit_ids, source, hits) VALUES (?, ?, ?, ?, ?)",
                (_now(), query, json.dumps(hit_ids), source, json.dumps(cards)),
            )
            self._conn.commit()

    def recent_recalls(self, limit: int = 10) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT at, query, hit_ids, source, hits FROM recalls ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        found = []
        for row in rows:
            item = dict(row)
            item["hit_ids"] = json.loads(item["hit_ids"])
            item["hits"] = json.loads(item["hits"] or "[]")
            found.append(item)
        return found

    def recent_notes(self, limit: int = 8) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM notes ORDER BY updated_at DESC, id ASC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_note(row) for row in rows]

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


def open_profile_store() -> NoteStore:
    home = os.environ.get("HERMES_HOME", "").strip()
    if not home:
        raise RuntimeError("HERMES_HOME is not set")
    return NoteStore(Path(home) / "fleet-memory")


def format_recall(notes: list[dict], budget_chars: int) -> str:
    lines = ["Local store matches:"]
    used = len(lines[0])
    shown = 0
    for note in notes:
        score = note.get("score", 0)
        shown_score = f"{score:.2f}" if isinstance(score, float) else str(score)
        line = f"- {note['title']} (score {shown_score}): {note['body']}"
        if used + len(line) + 1 > budget_chars:
            break
        lines.append(line)
        used += len(line) + 1
        shown += 1
    if shown == 0:
        return ""
    return "\n".join(lines)


_STOP = frozenset(
    "a an the to of and or for on in at is are was were be do does did when what how with from this that it".split()
)
_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return [tok for tok in _TOKEN.findall(text.lower()) if tok not in _STOP]


def _bm25(notes: list[dict], query: str, limit: int) -> list[dict]:
    """Rank notes with BM25. A hit must clear 45% of the best score."""
    query_tokens = _tokens(query)
    if not notes or not query_tokens or limit <= 0:
        return []
    docs = []
    for note in notes:
        weighted = (
            _tokens(note["title"]) * 3
            + _tokens(note["body"])
            + _tokens(" ".join(note["tags"]))
            + _tokens(str(note["id"]).replace("-", " "))
        )
        docs.append((note, weighted))
    total = len(docs)
    avgdl = sum(len(tokens) for _, tokens in docs) / total or 1
    df: dict[str, int] = {}
    for _, tokens in docs:
        for token in set(tokens):
            df[token] = df.get(token, 0) + 1
    k1 = 1.5
    b = 0.75
    ranked = []
    for note, tokens in docs:
        counts: dict[str, int] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        length = len(tokens) or 1
        score = 0.0
        for token in query_tokens:
            freq = counts.get(token, 0)
            if not freq:
                continue
            idf = math.log(1 + (total - df.get(token, 0) + 0.5) / (df.get(token, 0) + 0.5))
            denom = freq + k1 * (1 - b + b * length / avgdl)
            score += idf * (freq * (k1 + 1)) / denom
        if score > 0:
            ranked.append((score, note))
    if not ranked:
        return []
    ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
    floor = ranked[0][0] * 0.45
    found = []
    for score, note in ranked:
        if score < floor:
            break
        card = dict(note)
        card["score"] = round(score, 2)
        card["snippet"] = note["body"][:160]
        found.append(card)
        if len(found) >= limit:
            break
    return found
