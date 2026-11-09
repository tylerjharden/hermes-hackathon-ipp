---
name: fleet-ops
description: Search local fleet notes before answering an ops question.
---

# Fleet ops

Call `fleet_memory_search` with the dock, route, or carrier words from the question. Call `fleet_memory_status` for store counts. Call `fleet_memory_ingest` to save a new local note.

Prefetch already runs before the turn. Answer with each matched title, its score, and the fact from the note. A dock question should name the 14:30 America/New_York cutoff. Do not answer with a single bare line. Do not wait on Notion. Ingest writes the local store only.
