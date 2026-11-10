# Hermes hackathon plugins

Three Hermes Agent plugins for the Nous Research plugin hackathon. Each one registers tools. Two also ship a desktop pane. One is a memory provider.

| Plugin | What it does |
| --- | --- |
| `plugins/agentmail-frontdoor` | Claims, classifies, and routes AgentMail threads. Creates drafts. Does not send. |
| `plugins/odoo-prod-guard` | Odoo JSON-2 reads and writes. Non-routine production writes wait for Hermes approval. |
| `plugins/fleet-memory` | Recalls local fleet notes and can search Notion off the turn thread. |

## Live session

Capture Hermes TUI and Desktop with [LIVE_DEMO.md](LIVE_DEMO.md). That path installs Hermes `v0.22.7`, installs each plugin with `--ref`, and leaves secrets unset so the tools and panes run on the fixture stores. `demo.py` is the unit-test helper.

## Install

Follow [LIVE_DEMO.md](LIVE_DEMO.md). The installer id is `tylerjharden/hermes-hackathon-ipp/plugins/<name>` plus `--ref` set to the full commit SHA. Leave the secret prompts empty. Unset secrets stay on the fixture backend.

```bash
pytest
```

`stage/` is a copy of `plugins/` for copy-out. The intended drop folder on a later machine is `/workspace/turing-stage/hermes-hackathon-2026-11/`.

Catalog drafts live in `catalog/`. `catalog/SUBMIT.md` has the pull request text for `NousResearch/hermes-agent`.
