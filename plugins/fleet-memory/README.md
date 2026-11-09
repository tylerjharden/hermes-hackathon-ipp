# Fleet memory

Recall fleet ops notes from a profile-local store. Notion search is optional and runs off the turn thread.

## Install

```bash
hermes plugins install /absolute/path/to/plugins/fleet-memory
export NOTION_TOKEN=mock
hermes plugins enable fleet-memory
```

Select `fleet-memory` as `memory.provider` when you want prefetch on each turn. `NOTION_TOKEN=mock` keeps the provider on the seeded SQLite file. A real token makes `sync_turn` search Notion in the background. It does not create or edit Notion pages.

## Demo

```bash
python demo.py
```

The script prints `recall=GL-14`, `notes=6`, and `notion=false`. The database is `$HERMES_HOME/fleet-memory/notes.db`. Seed rows ship in `data/fleet_ops_seed.json`.

In chat:

```text
When does dock GL-14 stop taking same-day freight?
```

The desktop pane is `desktop/plugin.js`. It reads `GET /api/plugins/fleet-memory/summary` and shows store counts plus recent recalls. Open `desktop/fixture.html` when Hermes Desktop is not running. `?state=before` is the empty pane. The default shows one recall. Refresh on the empty pane fills the sample.

If that route returns 404, `fleet-memory` is missing from `plugins.enabled`. Setting `memory.provider` alone does not mount the pane API. Run `hermes plugins enable fleet-memory`. The install command in `LIVE_DEMO.md` already passes `--enable`, so a 404 after that install means the enable step did not stay on.

## Disclosures

The store lives under the active profile's `hermes_home`, passed into `initialize`. The plugin does not read `~/.hermes` by a hardcoded path, `.env`, or `auth.json`.

With a real `NOTION_TOKEN` (read through `agent.secret_scope.get_secret`), `sync_turn` starts `spawn_context_thread` and `POST`s `https://api.notion.com/v1/search`. That call is a search. Ingest stays local. Mock and missing tokens do not open a socket.

No shell commands. No telemetry. `register` builds a new provider each time. One instance does not serve two profiles.
