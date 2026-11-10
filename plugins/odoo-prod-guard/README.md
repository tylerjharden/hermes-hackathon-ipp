# Odoo prod guard

Read Odoo over JSON-2. Routine production writes run. Other production writes stop for Hermes approval. Dev does not ask.

## Install

```bash
hermes plugins install /absolute/path/to/plugins/odoo-prod-guard
export ODOO_URL=mock ODOO_DB=mock ODOO_USER=mock ODOO_API_KEY=mock
hermes plugins enable odoo-prod-guard
```

Set `env` to `prod` and `routine_allowlist` to patterns such as `account.move:action_post` under the plugin settings. The four `ODOO_*` values are placeholders until you replace them. Placeholders keep the tools on fixture responses.

## Demo

```bash
python demo.py
```

The script prints `mock=true`, `routine=None`, and `gated=approve`. `None` means the hook let the call through. `approve` means Hermes must ask a person before `res.partner.unlink` runs on prod.

In chat:

```text
What Odoo version is this, and do not change any records.
```

The desktop pane is `desktop/plugin.js`. It polls `GET /api/plugins/odoo-prod-guard/summary` every second. The pane shows an allowlisted write beside a gated write, the call log, and a preview of the values. Approve and Deny post to `/decision` and only mark the audit trail. They do not run the write. Open `desktop/fixture.html` when Hermes Desktop is not running. The badge reads `demo data` while the Odoo secrets are unset or `mock`.

## Gate

`odoo_search_read` and `odoo_version` are reads. `odoo_call` on prod asks for approval when the method is not a read and the `model:method` pair does not match `routine_allowlist` (`fnmatch`). Dev records a warning and returns no directive. An env value other than `dev` or `prod` is treated as prod.

## Disclosures

Live mode sends HTTPS to the Odoo base URL. JSON-2 writes and reads use `POST /json/2/{model}/{method}` with `Authorization: bearer` and `X-Odoo-Database`. Version uses `GET /web/version`. Secrets are read with `agent.secret_scope.get_secret` for `ODOO_URL`, `ODOO_DB`, `ODOO_USER`, and `ODOO_API_KEY`.

Mock mode does not open a socket. The plugin does not read `.env` or `auth.json`, does not run shell commands, and does not send telemetry. Gate history is stored under `$HERMES_HOME/plugin-data/odoo-prod-guard/`. The plugin does not approve its own writes.
