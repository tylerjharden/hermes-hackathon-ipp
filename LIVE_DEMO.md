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

When the installer asks for `AGENTMAIL_API_KEY`, `ODOO_URL`, `ODOO_DB`, `ODOO_USER`, `ODOO_API_KEY`, or `NOTION_TOKEN`, press enter. Unset and `mock` both keep the tools on demo data. Do not commit real keys.

## Profile config

Put this in `$HERMES_HOME/config.yaml` next to the enabled list. `env: prod` only arms the approval gate. With the secrets unset, Odoo calls still return demo rows and do not open a socket.

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

## Model

Pick a model with `hermes model` before the first take. Use the fastest chat model already configured for the profile. A slow model is the 5–15 seconds of silence in the chat column. The panes keep moving during that wait: each one polls every second and advances a status age. The plugins cannot stream the model's own tokens.

## File browser

Hermes Desktop opens the file tree when a tool focuses the files pane (`setFileBrowserOpen(true)` in `apps/desktop/src/store/pane-focus.ts`). That reflow is in Desktop, not in these plugins.

Before recording, set Appearance to Simple. Simple's policy sets `fileBrowserOpen` to false (`apps/desktop/src/store/interface-mode.ts`). The same Appearance page has a file-browser toggle, and ⌘J closes the tree. A tool can still reveal the tree for the current session. In Simple mode that reveal is not saved as the resting preference. Stay off file tools during the take.

## Reset

From the repo root, with `HERMES_HOME` pointed at the profile you are recording:

```bash
python scripts/demo_reset.py
```

That restores two demo inbox threads (Maria Chen at Harborline Logistics, Devon Okonkwo at North Pier Freight), two Odoo gate rows (an allowlisted `account.move.action_post` and a gated `res.partner.unlink`), and the local fleet store plus one auto-recall for `freight cutoff`. The panes label this `demo data` or `local store`.

## What the session already has

The first load claims the demo threads in `plugins/agentmail-frontdoor/tests/fixtures/inbound.json`. Fleet loads `plugins/fleet-memory/data/fleet_ops_seed.json` into `$HERMES_HOME/fleet-memory/notes.db`. Odoo demo mode returns a row named `Harborline Logistics dock GL-14`.

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

Send these three prompts, in order. The exact takes, with the Desktop beats, are in `docs/DEMO_SCRIPT.md`.

1. Maria Chen at Harborline Logistics wrote about invoice 1842 for the generator move off dock GL-14. Claim thread thrd_harborline_1842, classify it, and draft a reply to maria.chen@harborline.example. Leave the draft for approval.
2. Post Harborline Logistics invoice INV-1842 with account.move action_post, then unlink the North Pier Freight partner.
3. When does dock GL-14 stop taking same-day freight?

The first prompt ends with label `needs-approval` and the draft unsent. The second prompt's invoice post is allowlisted and the unlink stops on the Hermes approval prompt. Leave that prompt. The third prompt recalls the 14:30 cutoff from the local store, with the note title and score.

## Desktop capture

```bash
hermes desktop
```

Open the right-hand Front door pane, the Odoo guard pane, and the Fleet memory pane. Each polls its plugin route every second. The status line's age counts up while the model is still thinking.

If a pane returns 404, that plugin is missing from `plugins.enabled`. Setting `memory.provider` alone does not mount the Fleet pane API. The install commands above already pass `--enable`. If the pane still 404s, run `hermes plugins enable fleet-memory`.

Front door opens on Devon Okonkwo's draft, already `needs-approval`, with Approve and Deny. Those buttons mark the ledger. They do not send. Odoo opens with the Harborline post marked allowed beside the North Pier unlink waiting for approval. Fleet opens on a local-store recall card for `freight cutoff`, title and score on their own lines.

## Desktop renderer

`hermes desktop` in this environment exits immediately: `Desktop GUI source not found` under the install workspace, so the Electron renderer never started. The three `desktop/fixture.html` pages stayed up under headless Chrome, and `hermes plugins doctor` passed for each plugin. The cut where the renderer died and a restart cleared it was not reproduced here. If it happens on a recording machine, quit Desktop and start it again, then run `python scripts/demo_reset.py` before the next take.

Capture each pane at about 1280 pixels wide and again at about 390. The chat column stays on the left at desktop width. At 390 the pane fills the width.

## Boundaries

AgentMail creates drafts only. A send to an address outside the allowlist is blocked. Pane Approve and Deny do not send mail and do not execute Odoo writes. Odoo demo mode does not call a server. A real `ODOO_*` set would use HTTPS, and non-routine production writes still wait for Hermes approval. Notion search runs only when `NOTION_TOKEN` is a real token, and it does not create or edit pages.
