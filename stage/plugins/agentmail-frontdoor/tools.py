"""Tool handlers. Each returns a JSON string and does not raise."""

from __future__ import annotations

import json
from pathlib import Path

from .client import AgentMailClient, read_secret
from .ledger import Ledger, LedgerError
from .paths import data_dir

PLUGIN_ID = "agentmail-frontdoor"

_RULES = (
    ("outage", "ops", "high"),
    ("urgent", "ops", "high"),
    ("invoice", "billing", "normal"),
    ("quote", "sales", "normal"),
    ("shipment", "ops", "normal"),
)


def classify_text(subject: str, text: str) -> dict:
    blob = f"{subject}\n{text}".lower()
    intent = "general"
    urgency = "normal"
    for needle, found_intent, found_urgency in _RULES:
        if needle in blob:
            intent = found_intent
            urgency = found_urgency
            break
    summary = " ".join(text.split())[:140]
    return {"intent": intent, "urgency": urgency, "summary": summary}


def _dump(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True)


def _error(exc: Exception) -> str:
    if isinstance(exc, LedgerError):
        return _dump({"ok": False, "error": exc.code, **exc.detail})
    return _dump({"ok": False, "error": exc.__class__.__name__, "message": str(exc)})


def _ledger() -> Ledger:
    return Ledger(data_dir(PLUGIN_ID) / "ledger.db")


def _client(config: dict) -> AgentMailClient:
    return AgentMailClient(
        api_key=read_secret("AGENTMAIL_API_KEY"),
        mode=str(config.get("mode") or "auto"),
    )


def _sync_label(client: AgentMailClient, inbox_id: str, thread_id: str, label: str, previous: str | None) -> str | None:
    if client.mode != "live":
        return None
    try:
        client.set_labels(inbox_id, thread_id, label, previous)
    except Exception as exc:
        return str(exc)
    return None


def make_handlers(config_fn):
    def claim(args: dict, **kwargs) -> str:
        try:
            thread_id = str(args["thread_id"]).strip()
            inbox_id = str(args.get("inbox_id") or config_fn().get("inbox_id") or "ops").strip()
            subject = str(args.get("subject") or "")
            ledger = _ledger()
            previous = ledger.get(thread_id)
            row = ledger.claim(thread_id, inbox_id, subject)
            client = _client(config_fn())
            if client.mode == "live":
                client.get_thread(inbox_id, thread_id)
            warning = _sync_label(
                client,
                inbox_id,
                thread_id,
                row["label"],
                None if previous is None else previous["label"],
            )
            ledger.close()
            return _dump({"ok": True, "mock": client.mode == "mock", "warning": warning, "thread": row})
        except Exception as exc:
            return _error(exc)

    def classify(args: dict, **kwargs) -> str:
        try:
            thread_id = str(args["thread_id"]).strip()
            ledger = _ledger()
            row = ledger.get(thread_id)
            if row is None:
                raise LedgerError("not_found", thread_id=thread_id)
            subject = str(args.get("subject") or row.get("subject") or "")
            text = str(args.get("text") or row.get("body") or "")
            found = classify_text(subject, text)
            stored = ledger.classify(thread_id, found)
            ledger.close()
            return _dump({"ok": True, "thread": stored})
        except Exception as exc:
            return _error(exc)

    def route(args: dict, **kwargs) -> str:
        try:
            thread_id = str(args["thread_id"]).strip()
            worker = str(args["worker"]).strip()
            ledger = _ledger()
            previous = ledger.get(thread_id)
            stored = ledger.route(thread_id, worker)
            warning = None
            if previous is not None:
                warning = _sync_label(
                    _client(config_fn()),
                    stored["inbox_id"],
                    thread_id,
                    stored["label"],
                    previous["label"],
                )
            ledger.close()
            return _dump({"ok": True, "warning": warning, "thread": stored})
        except Exception as exc:
            return _error(exc)

    def draft_reply(args: dict, **kwargs) -> str:
        try:
            if args.get("send") is True:
                return _dump({
                    "ok": False,
                    "error": "draft_only",
                    "message": "am_draft_reply creates a draft. It does not send.",
                })
            thread_id = str(args["thread_id"]).strip()
            body = str(args["body"])
            recipient = str(args["to"]).strip()
            ledger = _ledger()
            previous = ledger.get(thread_id)
            if previous is None:
                raise LedgerError("not_found", thread_id=thread_id)
            client = _client(config_fn())
            subject = str(args.get("subject") or previous.get("subject") or "Re: thread")
            created = client.create_draft(
                previous["inbox_id"],
                thread_id,
                [recipient],
                subject,
                body,
                ["needs-approval"],
            )
            draft_id = str(created.get("draft_id") or created.get("id") or "")
            stored = ledger.draft(thread_id, body, recipient, draft_id)
            warning = _sync_label(
                client,
                stored["inbox_id"],
                thread_id,
                stored["label"],
                previous["label"],
            )
            ledger.close()
            return _dump({
                "ok": True,
                "sent": False,
                "mock": client.mode == "mock",
                "warning": warning,
                "thread": stored,
            })
        except Exception as exc:
            return _error(exc)

    def ledger_upsert(args: dict, **kwargs) -> str:
        try:
            thread_id = str(args["thread_id"]).strip()
            event = args.get("event")
            ledger = _ledger()
            if event:
                stored = ledger.apply_event(thread_id, str(event))
            else:
                fields = {}
                for key in ("worker", "subject"):
                    if key in args and args[key] is not None:
                        fields[key] = str(args[key])
                if not fields:
                    raise LedgerError("missing_event")
                stored = ledger.update_fields(thread_id, **fields)
            ledger.close()
            return _dump({"ok": True, "thread": stored})
        except Exception as exc:
            return _error(exc)

    def ledger_get(args: dict, **kwargs) -> str:
        try:
            thread_id = str(args["thread_id"]).strip()
            ledger = _ledger()
            row = ledger.get(thread_id)
            ledger.close()
            if row is None:
                return _dump({"ok": False, "error": "not_found", "thread_id": thread_id})
            return _dump({"ok": True, "thread": row})
        except Exception as exc:
            return _error(exc)

    return {
        "am_claim_thread": claim,
        "am_classify": classify,
        "am_route": route,
        "am_draft_reply": draft_reply,
        "am_ledger_upsert": ledger_upsert,
        "am_ledger_get": ledger_get,
    }


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


SCHEMAS = {
    "am_claim_thread": _schema(
        "am_claim_thread",
        "Claim an inbound AgentMail thread into the local ledger at label triage.",
        {
            "thread_id": {"type": "string"},
            "inbox_id": {"type": "string"},
            "subject": {"type": "string"},
        },
        ["thread_id"],
    ),
    "am_classify": _schema(
        "am_classify",
        "Classify a claimed thread from its subject and body. Does not send mail.",
        {
            "thread_id": {"type": "string"},
            "subject": {"type": "string"},
            "text": {"type": "string"},
        },
        ["thread_id", "text"],
    ),
    "am_route": _schema(
        "am_route",
        "Move a thread from triage to delegated, then to awaiting-worker, and record the worker.",
        {"thread_id": {"type": "string"}, "worker": {"type": "string"}},
        ["thread_id", "worker"],
    ),
    "am_draft_reply": _schema(
        "am_draft_reply",
        "Create an AgentMail draft and move the thread to needs-approval. Never sends.",
        {
            "thread_id": {"type": "string"},
            "to": {"type": "string"},
            "body": {"type": "string"},
            "subject": {"type": "string"},
        },
        ["thread_id", "to", "body"],
    ),
    "am_ledger_upsert": _schema(
        "am_ledger_upsert",
        "Apply a legal label event or update worker/subject. Raw label jumps are rejected.",
        {
            "thread_id": {"type": "string"},
            "event": {
                "type": "string",
                "enum": ["delegate", "assign", "draft", "complete", "approve", "return"],
            },
            "worker": {"type": "string"},
            "subject": {"type": "string"},
        },
        ["thread_id"],
    ),
    "am_ledger_get": _schema(
        "am_ledger_get",
        "Read one ledger row.",
        {"thread_id": {"type": "string"}},
        ["thread_id"],
    ),
}


def ensure_fixture_thread() -> dict | None:
    """Claim the shipped inbound fixture once per profile. Later calls leave the row alone."""
    try:
        ledger = _ledger()
    except RuntimeError:
        return None
    try:
        fixture = load_fixture()
        existing = ledger.get(fixture["thread_id"])
        if existing is not None:
            return existing
        return ledger.claim(
            fixture["thread_id"],
            fixture["inbox_id"],
            fixture["subject"],
            fixture["text"],
        )
    finally:
        ledger.close()


def load_fixture(path: Path | None = None) -> dict:
    fixture = path or Path(__file__).resolve().parent / "tests" / "fixtures" / "inbound.json"
    return json.loads(fixture.read_text())
