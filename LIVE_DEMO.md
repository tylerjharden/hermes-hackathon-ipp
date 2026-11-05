# Live Hermes session

Use this path to capture Hermes itself. The plugins stay on local fixtures when the secrets are unset or set to the placeholder `mock`. `demo.py` is only a unit-test helper.

Hermes on PyPI was 0.19.0 in this environment. These steps use the GitHub release `v0.22.7`.

## Install Hermes

```bash
git clone --depth 1 --branch v0.22.7 https://github.com/NousResearch/hermes-agent.git
cd hermes-agent
bash setup-hermes.sh --runtime-only
source ./activate
hermes --help
```

## Install the plugins

`<SHA>` is the full 40-character commit on `main` that contains the plugins. The subdirectory is part of the install id. There is no separate `--subdir` flag.

```bash
export HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
SHA=<SHA>
hermes plugins install "tylerjharden/hermes-hackathon-ipp/plugins/agentmail-frontdoor" --ref "$SHA" --enable --yes-deps
hermes plugins install "tylerjharden/hermes-hackathon-ipp/plugins/odoo-prod-guard" --ref "$SHA" --enable --yes-deps
hermes plugins install "tylerjharden/hermes-hackathon-ipp/plugins/fleet-memory" --ref "$SHA" --enable --yes-deps
```

From a clone of this repo, the same installer accepts a file URL and the same `--ref`:

```bash
hermes plugins install "file://$PWD#plugins/agentmail-frontdoor" --ref "$SHA" --enable --yes-deps
hermes plugins install "file://$PWD#plugins/odoo-prod-guard" --ref "$SHA" --enable --yes-deps
hermes plugins install "file://$PWD#plugins/fleet-memory" --ref "$SHA" --enable --yes-deps
```

When the installer asks for `AGENTMAIL_API_KEY`, `ODOO_URL`, `ODOO_DB`, `ODOO_USER`, `ODOO_API_KEY`, or `NOTION_TOKEN`, press enter. Unset and `mock` both keep the fixture backend. Do not commit real keys.

## Profile config

Put this in `$HERMES_HOME/config.yaml` next to the enabled list. `env: prod` only arms the approval gate. With the secrets unset, Odoo calls still return fixture rows and do not open a socket.

```yaml
memory:
  provider: fleet-memory
plugins:
  entries:
    odoo-prod-guard:
      settings:
        env: prod
        routine_allowlist:
          - account.move:action_post
```

## What the session already has

No seed command. The first load claims AgentMail thread `thrd_fixture_1001` from `plugins/agentmail-frontdoor/tests/fixtures/inbound.json` into the profile ledger. Fleet loads `plugins/fleet-memory/data/fleet_ops_seed.json` into `$HERMES_HOME/fleet-memory/notes.db`. Odoo `search_read` returns one fixture row named `GL-14 fixture`.

## Checks

```bash
hermes plugins validate plugins/agentmail-frontdoor
hermes plugins validate plugins/odoo-prod-guard
hermes plugins validate plugins/fleet-memory
hermes plugins doctor agentmail-frontdoor
hermes plugins doctor odoo-prod-guard
hermes plugins doctor fleet-memory
```

## TUI capture

Pick a model first with `hermes model`. A fresh profile with no model queues the prompt and the TUI shows `storage_unavailable`, because Hermes will not store a session policy that has no model.

```bash
hermes chat --tui
```

Send these three prompts, in order.

1. Classify thread thrd_fixture_1001 and draft a reply to vendor@example.com. Do not send it.
2. Read the Odoo version, then unlink res.partner. Stop if Hermes asks for approval. Do not approve a production write.
3. When does dock GL-14 stop taking same-day freight?

The first prompt ends with label `needs-approval` and `sent` false. The second prompt's unlink returns an approve directive. The third prompt recalls the 14:30 cutoff from the local store.

## Desktop capture

```bash
hermes desktop
```

Open the right-hand Odoo guard pane, then the Fleet memory pane. Both poll their plugin route every 3 seconds.

Before the TUI prompts, the Odoo event list is empty and the badge reads `fixture`. After the unlink prompt, the list gains an `approve` row for `res.partner.unlink`. After the dock prompt, Fleet memory shows a recall for `GL-14`.

Capture each pane at about 1280 pixels wide and again at about 390. The chat column stays on the left at desktop width. At 390 the pane fills the width.

## Boundaries

AgentMail creates drafts only. A send to an address outside the allowlist is blocked. Odoo fixture mode does not call a server. A real `ODOO_*` set would use HTTPS, and non-routine production writes still wait for Hermes approval. Notion search runs only when `NOTION_TOKEN` is a real token, and it does not create or edit pages.
