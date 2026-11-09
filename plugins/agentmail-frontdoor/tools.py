"""Tool handlers. Each returns a JSON string and does not raise."""

from __future__ import annotations

import json
from datetime import datetime, timezone
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


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def pulse(line: str) -> None:
    try:
        target = data_dir(PLUGIN_ID) / "status.json"
        target.write_text(json.dumps({"at": _now(), "line": line}))
    except Exception:
        return


def read_status() -> dict:
    try:
        target = data_dir(PLUGIN_ID) / "status.json"
    except Exception:
        return {"at": "", "line": "Watching the inbox"}
    if not target.is_file():
        return {"at": "", "line": "Watching the inbox"}
    try:
        return json.loads(target.read_text())
    except Exception:
        return {"at": "", "line": "Watching the inbox"}


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
            pulse("Claiming a thread into the inbox queue")
            thread_id = str(args["thread_id"]).strip()
            inbox_id = str(args.get("inbox_id") or config_fn().get("inbox_id") or "ops").strip()
            subject = str(args.get("subject") or "")
            ledger = _ledger()
            previous = ledger.get(thread_id)
            row = ledger.claim(
                thread_id,
                inbox_id,
                subject,
                str(args.get("body") or ""),
                str(args.get("from_name") or ""),
                str(args.get("from_addr") or args.get("from") or ""),
            )
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
            pulse("Classifying the open thread")
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
            pulse(f"Routing to {args.get('worker') or 'a worker'}")
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
            pulse("Writing a draft. Nothing is sent.")
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
            ledger.note(thread_id, "draft", "Draft stored. It has not been sent.")
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

    def prepare(args: dict, **kwargs) -> str:
        try:
            pulse("Preparing one draft. Nothing is sent.")
            thread_id = str(args["thread_id"]).strip()
            inbox_id = str(args.get("inbox_id") or config_fn().get("inbox_id") or "ops").strip()
            ledger = _ledger()
            row = ledger.get(thread_id)
            if row is None:
                row = ledger.claim(
                    thread_id,
                    inbox_id,
                    str(args.get("subject") or ""),
                    str(args.get("text") or ""),
                    str(args.get("from_name") or ""),
                    str(args.get("to") or ""),
                )
            subject = str(args.get("subject") or row.get("subject") or "")
            text = str(args.get("text") or row.get("body") or "")
            if not row.get("classification"):
                row = ledger.classify(thread_id, classify_text(subject, text))
            if row["label"] not in {"needs-approval", "done"}:
                recipient = str(args.get("to") or row.get("from_addr") or "").strip()
                if not recipient:
                    raise LedgerError("missing_recipient", thread_id=thread_id)
                who = row.get("from_name") or recipient
                given_body = str(args.get("body") or "").strip()
                if given_body:
                    draft_body = given_body
                elif text:
                    draft_body = (
                        f"{who}, replying about {subject or 'your note'}. {text} "
                        "This draft was written from the thread. It has not been sent."
                    )
                else:
                    draft_body = f"{who}, this draft was written from the thread. It has not been sent."
                draft_subject = "Re: " + (subject or "thread")
                client = _client(config_fn())
                created = client.create_draft(
                    row["inbox_id"],
                    thread_id,
                    [recipient],
                    draft_subject,
                    draft_body,
                    ["needs-approval"],
                )
                draft_id = str(created.get("draft_id") or created.get("id") or "")
                row = ledger.draft(thread_id, draft_body, recipient, draft_id)
                ledger.note(thread_id, "draft", "Draft stored. It has not been sent.")
            stored = ledger.get(thread_id)
            draft_subject = "Re: " + str(stored.get("subject") or subject or "thread")
            ledger.close()
            return _dump({
                "ok": True,
                "sent": False,
                "draft_subject": draft_subject,
                "draft_body": stored.get("draft_body") or "",
                "message": "Drafted from the thread. Do not ask for a subject or a body. Call am_send next.",
                "thread": stored,
            })
        except Exception as exc:
            return _error(exc)

    def send(args: dict, **kwargs) -> str:
        try:
            pulse("Send is at the approval gate. Demo mode does not send.")
            thread_id = str(args["thread_id"]).strip()
            ledger = _ledger()
            row = ledger.get(thread_id)
            if row is None:
                raise LedgerError("not_found", thread_id=thread_id)
            client = _client(config_fn())
            if client.mode != "live":
                stored = ledger.mark_send(
                    thread_id,
                    "not-sent",
                    "Demo mode did not send. The approval gate was the only step.",
                )
                ledger.close()
                return _dump({
                    "ok": True,
                    "sent": False,
                    "mock": True,
                    "gate": "approve",
                    "thread": stored,
                })
            draft_id = str(row.get("draft_id") or "")
            if not draft_id:
                raise LedgerError("no_draft", thread_id=thread_id)
            client.send_draft(row["inbox_id"], draft_id)
            stored = ledger.mark_send(thread_id, "sent", "Live send ran after approval.")
            ledger.close()
            return _dump({"ok": True, "sent": True, "mock": False, "gate": "approve", "thread": stored})
        except Exception as exc:
            return _error(exc)

    def queue(args: dict, **kwargs) -> str:
        try:
            pulse("Reading the inbox queue")
            ledger = _ledger()
            threads = ledger.list_threads()
            ledger.close()
            slim = []
            for row in threads:
                slim.append({
                    "thread_id": row["thread_id"],
                    "label": row["label"],
                    "subject": row["subject"],
                    "from_name": row.get("from_name") or "",
                    "from_addr": row.get("from_addr") or "",
                    "vendor": (row.get("classification") or {}).get("vendor") if isinstance(row.get("classification"), dict) else "",
                })
            return _dump({"ok": True, "data_label": "demo data", "threads": slim})
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
        "am_prepare": prepare,
        "am_send": send,
        "am_queue": queue,
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
        "Do not call. am_prepare claims, classifies, and drafts in one step.",
        {
            "thread_id": {"type": "string"},
            "inbox_id": {"type": "string"},
            "subject": {"type": "string"},
        },
        ["thread_id"],
    ),
    "am_classify": _schema(
        "am_classify",
        "Do not call. am_prepare already classifies.",
        {
            "thread_id": {"type": "string"},
            "subject": {"type": "string"},
            "text": {"type": "string"},
        },
        ["thread_id", "text"],
    ),
    "am_route": _schema(
        "am_route",
        "Do not call. Not part of the demo flow.",
        {"thread_id": {"type": "string"}, "worker": {"type": "string"}},
        ["thread_id", "worker"],
    ),
    "am_draft_reply": _schema(
        "am_draft_reply",
        "Do not call. am_prepare already drafts. Calling this breaks the flow.",
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
        "Do not call. Not part of the demo flow.",
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
    "am_prepare": _schema(
        "am_prepare",
        "Call this immediately with only thread_id. Do not ask for a subject or a body. When they are omitted, the subject is Re: <thread subject> and the body is written from the thread. Then call am_send. Do not call am_ledger_get or am_draft_reply.",
        {"thread_id": {"type": "string"}},
        ["thread_id"],
    ),
    "am_send": _schema(
        "am_send",
        "Call this once, immediately after am_prepare. It always asks for approval. Demo mode does not send. Do not call another tool after it.",
        {"thread_id": {"type": "string"}},
        ["thread_id"],
    ),
    "am_queue": _schema(
        "am_queue",
        "Do not call. The desktop pane already lists the queue.",
        {},
        [],
    ),
    "am_ledger_get": _schema(
        "am_ledger_get",
        "Do not call. am_prepare returns the row. Do not call this before or after am_prepare.",
        {"thread_id": {"type": "string"}},
        ["thread_id"],
    ),
}


def load_demo_file(path: Path | None = None) -> dict:
    fixture = path or Path(__file__).resolve().parent / "tests" / "fixtures" / "inbound.json"
    return json.loads(fixture.read_text())


def load_demo_threads(path: Path | None = None) -> list[dict]:
    payload = load_demo_file(path)
    if "threads" in payload:
        return list(payload["threads"])
    return [payload]


def load_fixture(path: Path | None = None) -> dict:
    payload = load_demo_file(path)
    if "primary" in payload:
        return payload["primary"]
    return payload


def seed_demo(ledger: Ledger) -> list[dict]:
    """Insert missing demo threads. Existing rows are left alone."""
    seeded = []
    for thread in load_demo_threads():
        thread_id = thread["thread_id"]
        if ledger.get(thread_id) is not None:
            continue
        ledger.claim(
            thread_id,
            thread.get("inbox_id") or "ops",
            thread.get("subject") or "",
            thread.get("text") or "",
            thread.get("from_name") or "",
            thread.get("from") or "",
        )
        if thread.get("seed_label") == "needs-approval":
            ledger.classify(thread_id, classify_text(thread.get("subject") or "", thread.get("text") or ""))
            draft_body = thread.get("draft_body") or "Draft waiting for a person. It has not been sent."
            ledger.draft(
                thread_id,
                draft_body,
                thread.get("from") or "",
                f"draft_mock_{thread_id}",
            )
            ledger.note(thread_id, "awaiting", "Waiting in the pane. The draft has not been sent.")
        seeded.append(ledger.get(thread_id))
    return seeded


def ensure_demo_threads() -> list[dict] | None:
    try:
        ledger = _ledger()
    except RuntimeError:
        return None
    try:
        seed_demo(ledger)
        return ledger.list_threads()
    finally:
        ledger.close()


def ensure_fixture_thread() -> dict | None:
    rows = ensure_demo_threads()
    if not rows:
        return None
    primary = load_fixture()["thread_id"]
    for row in rows:
        if row["thread_id"] == primary:
            return row
    return rows[0]


def board(thread_id: str = "") -> dict:
    ledger = _ledger()
    try:
        seed_demo(ledger)
        threads = ledger.list_threads()
        focus = thread_id
        if not focus:
            waiting = next((row for row in threads if row["label"] == "needs-approval"), None)
            focus = (waiting or (threads[0] if threads else {})).get("thread_id", "")
        selected = ledger.get(focus) if focus else None
        history = ledger.history(focus) if focus else []
        return {
            "data_label": "demo data",
            "status": read_status(),
            "server_time": _now(),
            "threads": threads,
            "focus": focus,
            "selected": selected,
            "history": history,
        }
    finally:
        ledger.close()


def pane_decision(thread_id: str, decision: str, actor: str = "operator") -> dict:
    """Record a pane decision on the selected row. This never sends the draft."""
    person = str(actor or "operator").strip() or "operator"
    if decision == "approve":
        detail = f"Approved by {person} - demo mode, not sent"
    elif decision == "deny":
        detail = f"Denied by {person} - demo mode, not sent"
    else:
        raise LedgerError("unknown_decision", decision=decision)
    pulse("Recording a pane decision. The draft is not sent.")
    ledger = _ledger()
    try:
        row = ledger.get(thread_id)
        if row is None:
            raise LedgerError("not_found", thread_id=thread_id)
        if row["label"] == "needs-approval":
            ledger.apply_event(thread_id, "approve" if decision == "approve" else "return")
        stored = ledger.mark_send(thread_id, "not-sent", detail)
        return {
            "ok": True,
            "sent": False,
            "mock": True,
            "decision": decision,
            "thread": stored,
            "history": ledger.history(thread_id),
        }
    finally:
        ledger.close()
