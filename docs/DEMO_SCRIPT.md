# Demo script

Each beat is about 60–80 seconds. Record TUI and Desktop on the same profile. Before the first take, and between plugins:

```bash
export HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
python scripts/demo_reset.py
```

In Desktop, set Appearance to Simple so the file tree rests closed. There is no setting that hides `.ssh` if that pane is open on the home directory. Open this repo, not `$HOME`. The details are at the top of `LIVE_DEMO.md`. Pick the fastest configured model with `hermes model`. The fleet pane polls every half second.

The inbox, the gate rows, and the fleet notes are demo data. Approve and Deny in a pane write the audit trail. They do not send mail and they do not run an Odoo write.

## AgentMail front door

Reset, then open the Front door pane. It is already on Devon Okonkwo, North Pier Freight, label `needs-approval`.

1. Desktop, about 10 seconds. Point at the send gate under Devon Okonkwo. It already says the draft has not been sent.
2. TUI. Send: `Prepare a reply to Maria Chen on thread thrd_harborline_1842, then send it.`
3. Expected result: one `am_prepare` call, then `am_send`. The approval prompt appears. The pane send gate reads `Awaiting approval. Not sent.` Accept the prompt. The pane then reads `Not sent. Demo mode never sends.` No mail leaves the machine.

Reset before the next plugin.

## Odoo prod guard

Reset. Open the Odoo guard pane. Prod badge, `demo data`, Harborline `account.move.action_post` marked allowed beside North Pier `res.partner.unlink` marked approve.

1. Desktop, about 15 seconds. Read the two previews. The allowlisted post shows Harborline invoice INV-1842. The gated unlink shows North Pier Freight id 220.
2. TUI. Send: `Post Harborline invoice INV-1842, then unlink North Pier Freight.`
3. Expected result: the post is logged `allowed` and does not stop. The unlink stops on the Hermes approval prompt in the TUI. Leave that prompt. The pane's live log gains a new approve row and the status line names `res.partner.unlink`.
4. Click Deny on the gated card. The audit line says the write was not executed. The TUI prompt is still the real gate. Do not accept it.
5. The two states stay side by side: one write passed the allowlist, one write is waiting.

Reset before the next plugin.

## Fleet memory

Reset. Open the Fleet memory pane. The label is `local store`. A recall card shows the query `freight cutoff` and, on the next line, `Same-day dock cutoff` with a score and the 14:30 snippet.

1. TUI. Send: `When does dock GL-14 stop taking same-day freight?`
2. Expected result: the answer names the note title, a score, and 14:30 America/New_York. It is more than one bare line. The pane adds an auto-recall card. The query and the note title stay on separate lines.
3. TUI. Send: `Remember this: Maria Chen is holding the GL-14 generator until invoice 1842 is confirmed. Save it as harborline-hold.`
4. Expected result: the timeline gains `Harborline hold` within a second of the ingest tool returning.
5. TUI. Send: `What did we just note about Harborline?`
6. Expected result: a new recall card titled `Harborline hold`, with a snippet and a score. The store label still says `local store`.

## If the layout jumps

⌘J closes the file tree. Simple mode puts it back to closed on the next launch. Quit Desktop and start it again if the window stops accepting chat, then run the reset command before the next take.
