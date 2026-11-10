---
name: fleet-ops
description: Answer a read-only note question from prefetch. Save with one remember call.
---

# Fleet ops

Use a prefetch only when the question is a read-only question about a dock, route, carrier, cutoff, or a note already saved. Name the title and the score.

If the user says remember, save, store, or ingest, call `fleet_memory_remember` once. Do not answer with a recall card instead of saving.

If the user asks about mail, a draft, a send, Odoo, an invoice post, or a partner unlink, ignore fleet notes and call that other plugin's tool.
