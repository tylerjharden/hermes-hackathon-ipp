---
name: frontdoor
description: Prepare one AgentMail draft, then request send. Demo mode never sends.
---

# Front door

Call `am_prepare` once for the thread, then `am_send` once. Stop when the approval prompt appears.

Do not call `am_claim_thread`, `am_classify`, `am_route`, or `am_draft_reply`. Do not narrate before the first tool call.

Demo threads: Maria Chen, Harborline Logistics, `thrd_harborline_1842`, maria.chen@harborline.example. Devon Okonkwo, North Pier Freight, `thrd_northpier_220`. These rows are demo data.

`am_send` always asks a person. In demo mode the draft is still not sent after the person accepts.
