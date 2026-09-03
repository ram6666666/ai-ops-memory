from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fail_closed_chat_runtime_v2 import DurableCommitter, SQLiteDurableEventLog
from github_contents_replica_sink import GitHubContentsReplicaSink


def main() -> None:
    token = os.environ["GITHUB_TOKEN"]
    repository = os.environ["GITHUB_REPOSITORY"]
    branch = os.environ.get("GITHUB_REF_NAME", "main")

    with tempfile.TemporaryDirectory() as td:
        log = SQLiteDurableEventLog(Path(td) / "events.sqlite")
        sink = GitHubContentsReplicaSink(
            repository=repository,
            token=token,
            branch=branch,
            prefix="telemetry/ci_remote_replica",
        )
        committer = DurableCommitter(log, replica=sink, require_remote_ack=True)
        receipt = committer.commit(
            conversation_id="SYNTHETIC-CI-REMOTE-REPLICA",
            event_id="stable-v1",
            role="synthetic_test",
            content="non-sensitive synthetic fail-closed remote replica validation",
        )
        assert receipt.local_committed
        assert receipt.remote_acked
        assert receipt.remote_receipt and receipt.remote_receipt.startswith("github:")
        assert log.remote_receipt(receipt.event) == receipt.remote_receipt
        assert log.verify_chain("SYNTHETIC-CI-REMOTE-REPLICA")
        print("REMOTE_REPLICA_WRITE_READBACK_PASS")
        print(receipt.remote_receipt)


if __name__ == "__main__":
    main()
