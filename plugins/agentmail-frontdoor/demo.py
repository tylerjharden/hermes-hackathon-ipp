"""Offline demo. Prints the needs-approval ledger row and exits 0."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from plugin_loader import load_package

pkg = load_package(Path(__file__).resolve().parent, "agentmail_frontdoor")


def main() -> None:
    home = os.environ.get("HERMES_HOME")
    if not home:
        home = tempfile.mkdtemp(prefix="agentmail-frontdoor-")
        os.environ["HERMES_HOME"] = home
    fixture = pkg.tools.load_fixture()
    handlers = pkg.tools.make_handlers(
        lambda: {"mode": "mock", "inbox_id": fixture["inbox_id"]}
    )
    handlers["am_claim_thread"](
        {
            "thread_id": fixture["thread_id"],
            "inbox_id": fixture["inbox_id"],
            "subject": fixture["subject"],
        }
    )
    handlers["am_classify"](
        {
            "thread_id": fixture["thread_id"],
            "subject": fixture["subject"],
            "text": fixture["text"],
        }
    )
    drafted = json.loads(
        handlers["am_draft_reply"](
            {
                "thread_id": fixture["thread_id"],
                "to": fixture["from"],
                "subject": "Re: " + fixture["subject"],
                "body": "Draft only. A person must approve before this leaves the inbox.",
            }
        )
    )
    row = json.loads(handlers["am_ledger_get"]({"thread_id": fixture["thread_id"]}))
    thread = row["thread"]
    print(f"label={thread['label']}")
    print(f"draft_id={thread['draft_id']}")
    print("sent=false")
    print(f"intent={thread['classification']['intent']}")
    print(f"ledger={Path(home) / 'plugin-data' / 'agentmail-frontdoor' / 'ledger.db'}")
    if thread["label"] != "needs-approval" or drafted["sent"] is not False:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
