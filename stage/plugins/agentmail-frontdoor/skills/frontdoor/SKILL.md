---
name: frontdoor
description: Claim an AgentMail thread, classify it, and draft a reply. Do not send.
---

# Front door

Use the AgentMail front-door tools in this order.

1. Call `am_claim_thread` with the inbound thread id.
2. Call `am_classify` with the subject and body.
3. Call `am_route` with a worker name when a person or queue should own the thread.
4. Call `am_draft_reply` to create a draft. The ledger label becomes `needs-approval`.
5. Call `am_ledger_get` to read the row back.

`am_draft_reply` creates a draft. It does not send. A send tool is blocked for recipients outside the allowlist. An allowlisted send returns an approve directive so Hermes asks a person.

Label order is `triage`, `delegated`, `awaiting-worker`, `needs-approval`, `done`. `am_ledger_upsert` accepts an event name. It rejects a raw jump to another label.
