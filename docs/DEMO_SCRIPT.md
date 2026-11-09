# Demo script

Each beat is about 60–80 seconds. Record TUI and Desktop on the same profile. Before the first take, and between plugins:

```bash
export HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
python scripts/demo_reset.py
```

In Desktop, set Appearance to Simple so the file tree rests closed. Pick the fastest configured model with `hermes model`. The right-hand pane polls every second; its status age is the thing that moves while the model is thinking.

The inbox, the gate rows, and the fleet notes are demo data. Approve and Deny in a pane write the audit trail. They do not send mail and they do not run an Odoo write.

## AgentMail front door

Reset, then open the Front door pane. It is already on Devon Okonkwo, North Pier Freight, label `needs-approval`.

1. Desktop, about 15 seconds. Point at the sales chip, the draft, and the line that says the draft has not been sent. Click Deny. The label returns to `triage` and the history line says the draft was not sent.
2. TUI. Send: `Maria Chen at Harborline Logistics wrote about invoice 1842 for the generator move off dock GL-14. Claim thread thrd_harborline_1842, classify it, and draft a reply to maria.chen@harborline.example. Leave the draft for approval.`
3. While the model works, the pane status age keeps counting. When the tool calls land, Maria's row moves to `needs-approval` and the draft preview fills in.
4. Expected result: the spoken answer names `needs-approval`, `maria.chen@harborline.example`, and that nothing was sent. The history ledger shows claim, classify, and draft.
5. Click Approve on Maria's row. The label becomes `done`. The history says the draft was not sent. No mail leaves the machine.

Reset before the next plugin.

## Odoo prod guard

Reset. Open the Odoo guard pane. Prod badge, `demo data`, Harborline `account.move.action_post` marked allowed beside North Pier `res.partner.unlink` marked approve.

1. Desktop, about 15 seconds. Read the two previews. The allowlisted post shows Harborline invoice INV-1842. The gated unlink shows North Pier Freight id 220.
2. TUI. Send: `Post Harborline Logistics invoice INV-1842 with account.move action_post, then unlink the North Pier Freight partner.`
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
