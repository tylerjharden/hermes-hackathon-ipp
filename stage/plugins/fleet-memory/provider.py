"""Fleet memory provider. One instance per register() call."""

from __future__ import annotations

import json
from pathlib import Path

from .store import NoteStore, format_recall, open_profile_store

try:
    from agent.memory_provider import MemoryProvider
except Exception:
    class MemoryProvider:
        pass

BUDGET_CHARS = 1500
NOTION_SEARCH = "https://api.notion.com/v1/search"


def read_secret(name: str) -> str:
    try:
        from agent.secret_scope import get_secret
    except Exception:
        return ""
    return (get_secret(name) or "").strip()


def start_network_thread(target, name: str):
    try:
        from agent.memory_provider import spawn_context_thread
    except Exception:
        import threading

        def spawn_context_thread(fn, name="fleet-memory-sync"):
            return threading.Thread(target=fn, name=name, daemon=True)

    thread = spawn_context_thread(target, name=name)
    thread.start()
    return thread


def _notion_token(explicit: str | None = None) -> str:
    token = explicit if explicit is not None else read_secret("NOTION_TOKEN")
    if not token or token == "mock":
        return ""
    return token


class FleetMemoryProvider(MemoryProvider):
    def __init__(self, token: str | None = None, spawner=None) -> None:
        self._token_override = token
        self._spawner = spawner or start_network_thread
        self._store: NoteStore | None = None
        self._home = ""
        self._budget = 3
        self._bound = False

    @property
    def name(self) -> str:
        return "fleet-memory"

    def is_available(self) -> bool:
        return True

    def initialize(self, session_id: str, **kwargs) -> None:
        if self._bound:
            raise RuntimeError("fleet-memory instance is already bound to a profile")
        home = kwargs.get("hermes_home")
        if not home:
            raise RuntimeError("hermes_home is required")
        self._home = str(home)
        self._session_id = session_id
        root = Path(self._home) / "fleet-memory"
        config_path = root / "config.json"
        if config_path.is_file():
            stored = json.loads(config_path.read_text())
            self._budget = int(stored.get("recall_budget") or 3)
        self._store = NoteStore(root)
        self._token = _notion_token(self._token_override)
        self._bound = True

    def get_config_schema(self):
        return [
            {
                "key": "recall_budget",
                "description": "Maximum notes prefetch returns",
                "default": "3",
            }
        ]

    def save_config(self, values: dict, hermes_home: str) -> None:
        root = Path(hermes_home) / "fleet-memory"
        root.mkdir(parents=True, exist_ok=True)
        budget = int(values.get("recall_budget") or 3)
        (root / "config.json").write_text(json.dumps({"recall_budget": budget}))

    def get_tool_schemas(self) -> list[dict]:
        return list(SCHEMAS)

    def handle_tool_call(self, tool_name: str, args: dict, **kwargs) -> str:
        handler = {
            "fleet_memory_search": self._search,
            "fleet_memory_status": self._status,
            "fleet_memory_ingest": self._ingest,
            "fleet_memory_remember": self._remember,
        }.get(tool_name)
        if handler is None:
            return json.dumps({"ok": False, "error": "unknown_tool"})
        return handler(args or {})

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if not is_readonly_recall(query):
            return ""
        store = self._require()
        _pulse(store, f"Auto-recall for {query}")
        notes = store.search(query, self._budget)
        store.record_recall(query, [note["id"] for note in notes], source="auto", hits=notes)
        return format_recall(notes, BUDGET_CHARS)

    def sync_turn(self, user_content, assistant_content, *, session_id: str = "", messages=None) -> None:
        store = self._require()
        store.append_turn(session_id or self._session_id, str(user_content or ""), str(assistant_content or ""))
        if not self._token:
            return
        self._spawner(
            lambda: _refresh_notion(self._token, str(user_content or ""), store),
            "fleet-memory-sync",
        )

    def system_prompt_block(self) -> str:
        return (
            "A fleet prefetch is only for a read-only question about docks, routes, "
            "carriers, cutoffs, or notes already saved. On that kind of question, "
            "answer from the prefetch and name the title and the score. "
            "When the user asks to remember, save, store, or ingest, call "
            "fleet_memory_remember. A prefetch card is not a save. "
            "When the user asks for mail, a draft, a send, Odoo, an invoice post, "
            "a partner unlink, or any tool outside fleet memory, ignore the prefetch "
            "and call that tool."
        )

    def on_session_end(self, messages=None) -> None:
        return None

    def shutdown(self) -> None:
        if self._store is not None:
            self._store.close()
            self._store = None

    def _require(self) -> NoteStore:
        if self._store is None:
            raise RuntimeError("fleet-memory is not initialized")
        return self._store

    def _search(self, args: dict) -> str:
        query = str(args.get("query") or "")
        limit = int(args.get("limit") or self._budget)
        store = self._require()
        _pulse(store, f"Searching the local store for {query}")
        notes = store.search(query, limit)
        store.record_recall(query, [note["id"] for note in notes], source="tool", hits=notes)
        return json.dumps({"ok": True, "backend": "notion" if self._token else "local", "notes": notes})

    def _status(self, args: dict) -> str:
        counts = self._require().counts()
        return json.dumps({
            "ok": True,
            "provider": self.name,
            "notion": bool(self._token),
            **counts,
        })

    def _ingest(self, args: dict) -> str:
        tags = args.get("tags") or []
        if isinstance(tags, str):
            tags = [part.strip() for part in tags.split(",") if part.strip()]
        store = self._require()
        note = store.ingest(
            str(args["id"]),
            str(args["title"]),
            str(args["body"]),
            [str(tag) for tag in tags],
        )
        _pulse(store, f"Ingested {note['title']} into the local store")
        return json.dumps({"ok": True, "note": note})

    def _remember(self, args: dict) -> str:
        stored = json.loads(self._ingest(args))
        if not stored.get("ok"):
            return json.dumps(stored)
        notes = self._require().search(str(args.get("title") or ""), 3)
        self._require().record_recall(str(args.get("title") or ""), [note["id"] for note in notes], source="saved", hits=notes)
        return json.dumps({"ok": True, "note": stored["note"], "notes": notes})


def tool_search(args: dict, **kwargs) -> str:
    store = open_profile_store()
    try:
        query = str((args or {}).get("query") or "")
        limit = int((args or {}).get("limit") or 3)
        _pulse(store, f"Searching the local store for {query}")
        notes = store.search(query, limit)
        store.record_recall(query, [note["id"] for note in notes], source="tool", hits=notes)
        return json.dumps({"ok": True, "backend": "local", "notes": notes})
    finally:
        store.close()


def tool_status(args: dict, **kwargs) -> str:
    store = open_profile_store()
    try:
        counts = store.counts()
        token = bool(_notion_token())
        return json.dumps({
            "ok": True,
            "provider": "fleet-memory",
            "backend": "notion" if token else "local",
            "notion": token,
            **counts,
        })
    finally:
        store.close()


def tool_ingest(args: dict, **kwargs) -> str:
    store = open_profile_store()
    try:
        tags = (args or {}).get("tags") or []
        if isinstance(tags, str):
            tags = [part.strip() for part in tags.split(",") if part.strip()]
        note = store.ingest(
            str(args["id"]),
            str(args["title"]),
            str(args["body"]),
            [str(tag) for tag in tags],
        )
        _pulse(store, f"Ingested {note['title']} into the local store")
        return json.dumps({"ok": True, "backend": "local", "note": note})
    finally:
        store.close()


def tool_remember(args: dict, **kwargs) -> str:
    store = open_profile_store()
    try:
        tags = (args or {}).get("tags") or []
        if isinstance(tags, str):
            tags = [part.strip() for part in tags.split(",") if part.strip()]
        note = store.ingest(
            str(args["id"]),
            str(args["title"]),
            str(args["body"]),
            [str(tag) for tag in tags],
        )
        notes = store.search(str(args.get("title") or ""), 3)
        store.record_recall(str(args.get("title") or ""), [item["id"] for item in notes], source="saved", hits=notes)
        _pulse(store, f"Remembered {note['title']}")
        return json.dumps({"ok": True, "backend": "local", "note": note, "notes": notes})
    finally:
        store.close()


TOOL_HANDLERS = {
    "fleet_memory_search": tool_search,
    "fleet_memory_status": tool_status,
    "fleet_memory_ingest": tool_ingest,
    "fleet_memory_remember": tool_remember,
}


def is_readonly_recall(query: str) -> bool:
    """True only for a question the local store can answer without another tool."""
    text = " ".join(str(query or "").lower().split())
    if not text:
        return False
    if any(phrase in text for phrase in ("remember this", "remember:", "save it as", "save this as", "ingest")):
        return False
    if any(token in text for token in ("odoo", "unlink", "action_post", "res.partner", "account.move", "am_prepare", "am_send", "thrd_")):
        return False
    if "post" in text and "invoice" in text:
        return False
    if "prepare a reply" in text or ("send" in text and "reply" in text):
        return False
    return True


def _pulse(store: NoteStore, line: str) -> None:
    try:
        from datetime import datetime, timezone
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        (store.root / "status.json").write_text(json.dumps({"at": stamp, "line": line}))
    except Exception:
        return


def _refresh_notion(token: str, query: str, store: NoteStore) -> None:
    import urllib.request

    req = urllib.request.Request(
        NOTION_SEARCH,
        data=json.dumps({"query": query, "page_size": 5}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.loads(resp.read().decode())
    for item in payload.get("results") or []:
        title = ""
        props = item.get("properties") or {}
        for prop in props.values():
            if isinstance(prop, dict) and prop.get("type") == "title":
                title = "".join(part.get("plain_text", "") for part in prop.get("title") or [])
                break
        if not title:
            continue
        store.ingest(f"notion-{item.get('id')}", title, title, ["notion"])


def _schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    }


SCHEMAS = [
    _schema(
        "fleet_memory_search",
        "Search the local store. Skip this when prefetch already answered.",
        {"query": {"type": "string"}, "limit": {"type": "integer"}},
        ["query"],
    ),
    _schema(
        "fleet_memory_status",
        "Counts only. Skip this during a normal answer.",
        {},
        [],
    ),
    _schema(
        "fleet_memory_ingest",
        "Low-level save. Prefer fleet_memory_remember.",
        {
            "id": {"type": "string"},
            "title": {"type": "string"},
            "body": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
        },
        ["id", "title", "body"],
    ),
    _schema(
        "fleet_memory_remember",
        "One call: save a note and return the ranked card. Does not write to Notion.",
        {
            "id": {"type": "string"},
            "title": {"type": "string"},
            "body": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
        },
        ["id", "title", "body"],
    ),
]
