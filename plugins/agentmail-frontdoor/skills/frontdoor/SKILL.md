---
name: frontdoor
description: Claim an AgentMail thread, classify it, and draft a reply. Do not send.
---

# Front door

Use the AgentMail front-door tools in this order.

1. Call `am_queue` to read the inbox. The seeded rows are demo data for Maria Chen at Harborline Logistics (`thrd_harborline_1842`) and Devon Okonkwo at North Pier Freight (`thrd_northpier_220`).
2. Call `am_claim_thread` with the inbound thread id.
3. Call `am_classify` with the subject and body.
4. Call `am_route` with a worker name when a person or queue should own the thread.
5. Call `am_draft_reply` to create a draft. The ledger label becomes `needs-approval`.
6. Call `am_ledger_get` to read the row back. Say the label, the recipient, and that the draft was not sent.

`am_draft_reply` creates a draft. It does not send. A send tool is blocked for recipients outside the allowlist. An allowlisted send returns an approve directive so Hermes asks a person.

Label order is `triage`, `delegated`, `awaiting-worker`, `needs-approval`, `done`. `am_ledger_upsert` accepts an event name. It rejects a raw jump to another label.
