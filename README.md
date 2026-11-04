# Hermes hackathon plugins

Three Hermes Agent plugins for the Nous Research plugin hackathon. Each one registers tools. Two also ship a desktop pane. One is a memory provider.

| Plugin | What it does |
| --- | --- |
| `plugins/agentmail-frontdoor` | Claims, classifies, and routes AgentMail threads. Creates drafts. Does not send. |
| `plugins/odoo-prod-guard` | Odoo JSON-2 reads and writes. Non-routine production writes wait for Hermes approval. |
| `plugins/fleet-memory` | Recalls local fleet notes and can search Notion off the turn thread. |

## Install

Install Hermes, then install one directory at a time:

```bash
hermes plugins install "$PWD/plugins/agentmail-frontdoor"
hermes plugins install "$PWD/plugins/odoo-prod-guard"
hermes plugins install "$PWD/plugins/fleet-memory"
export AGENTMAIL_API_KEY=mock ODOO_URL=mock ODOO_DB=mock ODOO_USER=mock ODOO_API_KEY=mock NOTION_TOKEN=mock
hermes plugins enable agentmail-frontdoor
hermes plugins enable odoo-prod-guard
hermes plugins enable fleet-memory
```

`mock` is a placeholder so the loader can enable the plugin with no live credential. The tools stay on local fixtures until you set a real secret and, where the plugin has a mode, switch it to live.

## Demo

Each plugin has a Demo section in its own README. From a checkout, with no credentials:

```bash
python plugins/agentmail-frontdoor/demo.py
python plugins/odoo-prod-guard/demo.py
python plugins/fleet-memory/demo.py
pytest
```

`stage/` is a copy of `plugins/` for copy-out. The intended drop folder on a later machine is `/workspace/turing-stage/hermes-hackathon-2026-11/`.

Catalog drafts live in `catalog/`. `catalog/SUBMIT.md` has the pull request text for `NousResearch/hermes-agent`.
