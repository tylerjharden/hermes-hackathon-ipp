# Typeform material

Deadline: Wednesday 2026-11-11 17:00 ET. This file is the copy for the form. Nothing here has been submitted.

## Links

- Repository: https://github.com/tylerjharden/hermes-hackathon-ipp
- Plugin pull request: https://github.com/tylerjharden/hermes-hackathon-ipp/pull/2
- Nous catalog pull request: https://github.com/NousResearch/hermes-agent/pull/149142

## Pinned SHAs

- Catalog entries pin the plugin tree at `3e2feea4b1216a6b2343b18a6de710ae5b126c46`.
- That pin is recorded in this repository at `e6574606995256a4337cc70118d4be32d88e7664`.
- Install with `hermes plugins install "tylerjharden/hermes-hackathon-ipp/plugins/<name>" --ref <SHA> --enable --yes-deps`. The subdirectory is part of the install id. Hermes `v0.22.7` from GitHub is the version these steps use. Leave every secret prompt empty so the session stays on demo data. The full click path is `LIVE_DEMO.md`. The takes are in `docs/DEMO_SCRIPT.md`.

## agentmail-frontdoor

The front door claims an inbound thread, classifies it, and creates an AgentMail draft. It does not send. A send to an address outside the allowlist is blocked. On first load the profile ledger holds demo threads for Maria Chen at Harborline Logistics (`thrd_harborline_1842`) and Devon Okonkwo at North Pier Freight (`thrd_northpier_220`). In Hermes TUI, ask it to classify Maria's thread and draft a reply to maria.chen@harborline.example, and leave the draft for approval. The row should land on `needs-approval` with `sent` false. The desktop pane is the right-hand Front door. `am_prepare` drafts in one call. `am_send` always raises the approval prompt. Demo mode does not send, even after that prompt is accepted. Approve and Deny on the draft update the ledger and do not send.

Demo video:

## odoo-prod-guard

Odoo JSON-2 reads always pass. With `env: prod`, a write that is not on `routine_allowlist` waits for Hermes approval. Unset `ODOO_*` values stay on demo responses, including version `19.0-mock`, and do not open a socket. Set `plugins.entries.odoo-prod-guard.settings.env` to `prod` and `routine_allowlist` to `account.move:action_post`. In the TUI, ask to post Harborline Logistics invoice INV-1842 with `account.move` `action_post`, then unlink the North Pier Freight partner, and leave the approval prompt. The desktop pane is the right-hand Odoo guard. Enable it under Capabilities, Plugins. It shows the allowlisted post beside the gated unlink. Approve and Deny in the pane only mark the audit trail.

Demo video:

## fleet-memory

Fleet memory recalls local ops notes and, only when `NOTION_TOKEN` is a real token, searches Notion without creating or editing pages. Set `memory.provider` to `fleet-memory`. The seed file loads into `$HERMES_HOME/fleet-memory/notes.db` on first use. In the TUI, ask when dock GL-14 stops taking same-day freight. The answer names the note title, a score, and 14:30 America/New_York. The desktop pane is the right-hand Fleet memory pane, labeled local store, enabled the same way as the Odoo pane. `python scripts/demo_reset.py` restores all three plugins between takes.

Demo video:
