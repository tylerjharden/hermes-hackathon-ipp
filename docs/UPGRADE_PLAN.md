# Upgrade plan

Director notes from the current cuts are the priority list. Tyler's verdict was low quality, dead time, panes that sit still, and too few features.

## What fits

| Note | What shipped |
| --- | --- |
| Dead time while the model thinks | Each pane polls every second and shows a status line plus an age in seconds. Tool handlers write that line as they start. `LIVE_DEMO.md` says to pick the fastest configured model with `hermes model`. |
| Staged prompts and fixture labels | Demo threads are Maria Chen at Harborline Logistics (`thrd_harborline_1842`) and Devon Okonkwo at North Pier Freight (`thrd_northpier_220`). Odoo samples use those partners. Panes say `demo data` or `local store`. The visible word `fixture` is gone from the panes. |
| File tree pops open and reflows | Documented, not patched. Simple mode sets `fileBrowserOpen` false. Appearance has the same toggle. ⌘J closes it. See below for the part that does not fit. |
| One reset between takes | `python scripts/demo_reset.py` wipes and reseeds all three stores in `$HERMES_HOME`. |
| AgentMail had no Desktop pane | `desktop/plugin.js` plus `dashboard/plugin_api.py`. Inbox queue, classification chips, draft preview, Approve/Deny, history. Approve and Deny call `pane_decision`. `sent` stays false. |
| Odoo pane was a static list | Allowlisted write beside a gated write, live log with badges, value preview, Approve/Deny audit, and the existing TUI gate. The pane does not execute the write. |
| Fleet pane was unstyled counts, and the query ran into the note id | Cards with title, snippet, and score. Query and title are separate lines. Auto-recall is tagged and the prefetch text names the local store, the title, and the score. Ingest shows up on the timeline. |
| A script for the takes | `docs/DEMO_SCRIPT.md`. Three to five beats per plugin, about 60–80 seconds, TUI and Desktop, exact prompts, expected screen, reset. |

## What does not fit

- Streaming the model's own tokens. The wait is inside Hermes. A plugin can only move its own pane. Simple mode also collapses the reasoning row on purpose.
- A hard lock on the file tree. `apps/desktop/src/store/pane-focus.ts` calls `setFileBrowserOpen(true)` when something focuses the files pane. Simple mode (`interface-mode.ts`) only shadows the resting preference. A session reveal can still open the tree. Closing it is ⌘J. Fixing that belongs in Hermes Desktop, not in these three plugins.
- The renderer dying. `hermes desktop` here exits at once with `Desktop GUI source not found` under the install workspace, so Electron never started and the kill could not be reproduced. `hermes plugins doctor` passed for all three plugins. The fixture pages stayed up under headless Chrome. Recovery on a machine where it does happen: quit Desktop, start it again, run `scripts/demo_reset.py`.
- Approve that sends mail, or Deny that rolls back a live Odoo write. Both stay audit marks. The TUI gate is still the only approval that can let a production write continue, and this demo leaves that prompt unanswered.

## Checks

`pytest --import-mode=importlib` on the three plugin test trees passed (29 tests).

`hermes plugins validate` passed for `plugins/agentmail-frontdoor`, `plugins/odoo-prod-guard`, and `plugins/fleet-memory`.

`hermes plugins doctor` on those three directories passed: 7 tools and 1 hook, 3 tools and 1 hook, 3 tools and 0 hooks.

## Pictures

`docs/live/` holds the previous panes and the new ones at 1280 and 390, plus a side-by-side overlay. AgentMail had no pane before; that frame is the empty column. The new frames are the fixture pages, which use the same layout as the Desktop panes.
