# AgentMail front door

Claim an inbound thread, classify it, and create a draft. The plugin does not send mail. A send still has to pass the Hermes approval gate.

## Install

Copy this directory to `~/.hermes/plugins/agentmail-frontdoor`, then enable it.

```bash
hermes plugins install /absolute/path/to/plugins/agentmail-frontdoor
export AGENTMAIL_API_KEY=mock
hermes plugins enable agentmail-frontdoor
```

`AGENTMAIL_API_KEY=mock` is a placeholder. With that value, or with the key unset when you call the tools outside the loader, every tool stays on the local ledger. A real key plus `mode: live` (or `mode: auto`) calls `https://api.agentmail.to`.

The loader refuses to enable the plugin when `AGENTMAIL_API_KEY` is missing. The placeholder keeps doctor and chat usable offline.

## Demo

From this directory, with no API key:

```bash
python demo.py
```

The script claims `tests/fixtures/inbound.json`, classifies it, creates a draft, and prints:

```text
label=needs-approval
draft_id=draft_mock_thrd_fixture_1001
sent=false
```

The ledger file is `$HERMES_HOME/plugin-data/agentmail-frontdoor/ledger.db`. The script sets `HERMES_HOME` to a temp directory when you do not.

In chat, after the placeholder key is set:

```text
Claim thread thrd_fixture_1001 in inbox ops about "Urgent invoice for dock GL-14", classify the body, and draft a reply to vendor@example.com. Do not send it.
```

## Labels

`triage` to `delegated` to `awaiting-worker` to `needs-approval` to `done`. `am_ledger_upsert` takes an event (`delegate`, `assign`, `draft`, `complete`, `approve`, `return`). A direct jump is rejected.

## Disclosures

Live mode sends HTTPS requests to `https://api.agentmail.to` with `AGENTMAIL_API_KEY`, read through `agent.secret_scope.get_secret`. Draft creation uses `POST /v0/inboxes/{inbox_id}/drafts`. Label changes use `PATCH` on the thread. The plugin never calls the send endpoints.

Mock mode does not open a socket. The plugin does not read `.env` or `auth.json`, does not run shell commands, and does not send telemetry. State is written under the profile data directory, not into this install tree.

`pre_tool_call` blocks `message_send`, `draft_send`, and any tool call with `send: true` when the recipient is missing or not on `recipient_allowlist`. Allowlisted sends return an approve directive. They are not sent automatically. A call that already carries `approved: true` is left to Hermes.
