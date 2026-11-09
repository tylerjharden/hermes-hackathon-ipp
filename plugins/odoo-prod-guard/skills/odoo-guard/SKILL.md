---
name: odoo-guard
description: Two Odoo calls. The allowlisted post runs. The other write stops for approval.
---

# Odoo guard

Call `odoo_call` twice and stop.

1. `account.move` `action_post` for the Harborline invoice. That pattern is allowlisted.
2. `res.partner` `unlink` for North Pier Freight. Stop when the approval prompt appears. Do not approve it.

Do not call `odoo_version` or `odoo_search_read` unless the person asked for a read. Do not narrate before the first call.
