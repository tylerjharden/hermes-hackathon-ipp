# Catalog submission

Do not open this from a fork until `sha` points at the commit on `main` that contains the three plugins. The drafts below pin `1c1a12cfb7ab1372158363e45a89bd6be1d843bf` on `cursor/hermes-hackathon-plugins-9099`. A squash merge changes that commit. Replace every `sha` and every raw screenshot URL with the full 40-character `main` commit, then open one pull request on `NousResearch/hermes-agent`.

## Pull request

Title:

```text
catalog: add agentmail-frontdoor, odoo-prod-guard, and fleet-memory
```

Body:

```markdown
## Why

Three community plugins from https://github.com/tylerjharden/hermes-hackathon-ipp. Each one is a native package with tools. Two also ship a desktop pane. One is a memory provider.

## What changed

- `plugin-catalog/agentmail-frontdoor.yaml`
- `plugin-catalog/odoo-prod-guard.yaml`
- `plugin-catalog/fleet-memory.yaml`

## Scope

Adds three community entries. Does not change Hermes core.

## Disclosures

- agentmail-frontdoor calls `https://api.agentmail.to` when `AGENTMAIL_API_KEY` is a real key. It creates drafts with `POST /v0/inboxes/{inbox_id}/drafts` and updates labels with `PATCH` on the thread. It does not call the send endpoints. `pre_tool_call` blocks sends to recipients outside the allowlist and returns an approve directive for allowlisted sends. The placeholder key `mock` stays on a local SQLite ledger.
- odoo-prod-guard calls the configured Odoo base URL over HTTPS when `ODOO_URL`, `ODOO_DB`, `ODOO_USER`, and `ODOO_API_KEY` are real. Reads use JSON-2. On `env: prod`, a write that is not on `routine_allowlist` returns an approve directive. The plugin does not approve its own calls. Placeholder secrets stay on fixture responses. The desktop pane reads gate history from the profile data directory.
- fleet-memory stores notes under the active profile `hermes_home`. With a real `NOTION_TOKEN`, `sync_turn` searches `https://api.notion.com/v1/search` on a `spawn_context_thread`. It does not create or edit Notion pages. The placeholder `mock` does not open a socket. The desktop pane shows recall counts from that local store.

Secrets are read with `agent.secret_scope.get_secret`. None of the plugins read `.env` or `auth.json`, run shell commands, send telemetry, or patch Hermes core.

## Verification

`pytest` from the plugin repo: 24 passed. Offline demos: `python plugins/agentmail-frontdoor/demo.py`, `python plugins/odoo-prod-guard/demo.py`, `python plugins/fleet-memory/demo.py`. `hermes` on PyPI in the build environment was 0.19.0, behind GitHub release v0.22.7, so `hermes plugins validate` was not run. Re-run `hermes plugins validate plugins/<name> --install-deps` on Hermes `>=0.22.0` before merge.
```

Copy `catalog/*.yaml` to `plugin-catalog/` in that pull request. Keep `subdir` and the pinned `sha`.
