---
name: frontdoor
description: Call am_prepare once, then am_send once. Do not call the other mail tools.
---

# Front door

The only tool order is `am_prepare`, then `am_send`. Stop when the approval prompt appears.

Do not call `am_ledger_get`, `am_draft_reply`, `am_claim_thread`, `am_classify`, `am_route`, `am_queue`, or `am_ledger_upsert`.

Demo thread for the take: Maria Chen, Harborline Logistics, `thrd_harborline_1842`.

`am_send` always asks a person. Demo mode does not send after the person accepts.
