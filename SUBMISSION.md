# Typeform material

Deadline: Wednesday 2026-11-11 17:00 ET. This file is the copy for the form. Nothing here has been submitted.

## Links

- Repository: https://github.com/tylerjharden/hermes-hackathon-ipp
- Plugin pull request: https://github.com/tylerjharden/hermes-hackathon-ipp/pull/2
- Nous catalog pull request: https://github.com/NousResearch/hermes-agent/pull/149142

## Pinned SHAs

- Catalog entries pin the plugin tree at `3e2feea4b1216a6b2343b18a6de710ae5b126c46`.
- That pin is recorded in this repository at `e6574606995256a4337cc70118d4be32d88e7664`.
- Install with `hermes plugins install "tylerjharden/hermes-hackathon-ipp/plugins/<name>" --ref <SHA> --enable --yes-deps`. The subdirectory is part of the install id. Hermes `v0.22.7` from GitHub is the version these steps use. Leave every secret prompt empty so the session stays on the fixture store. The full click path is `LIVE_DEMO.md`.

## agentmail-frontdoor

The front door claims an inbound thread, classifies it, and creates an AgentMail draft. It does not send. A send to an address outside the allowlist is blocked. On first load the profile ledger already holds thread `thrd_fixture_1001`. In Hermes TUI, ask it to classify that thread and draft a reply to vendor@example.com, and not to send it. The row should land on `needs-approval` with `sent` false.

Demo video:

## odoo-prod-guard

Odoo JSON-2 reads always pass. With `env: prod`, a write that is not on `routine_allowlist` waits for Hermes approval. Unset `ODOO_*` values stay on fixture responses, including version `19.0-mock`, and do not open a socket. Set `plugins.entries.odoo-prod-guard.settings.env` to `prod` and `routine_allowlist` to `account.move:action_post`. In the TUI, ask for the Odoo version, then ask to unlink `res.partner`, and stop when Hermes asks for approval. The desktop pane is the right-hand Odoo guard. Enable it under Capabilities, Plugins. It polls recent gated calls.

Demo video:

## fleet-memory

Fleet memory recalls local ops notes and, only when `NOTION_TOKEN` is a real token, searches Notion without creating or editing pages. Set `memory.provider` to `fleet-memory`. The seed file loads into `$HERMES_HOME/fleet-memory/notes.db` on first use. In the TUI, ask when dock GL-14 stops taking same-day freight. The answer is 14:30 America/New_York. The desktop pane is the right-hand Fleet memory pane, enabled the same way as the Odoo pane.

Demo video:
