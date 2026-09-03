from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

from fail_closed_chat_runtime_v2 import (
    DurableCommitter,
    JsonlFilesystemReplica,
    OpenAIResponsesAdapter,
    SQLiteDurableEventLog,
)
from fail_closed_stream_buffer import BufferedFailClosedChatHarness
from github_contents_replica_sink import GitHubContentsReplicaSink
from google_drive_replica_sink import GoogleDriveFileReplicaSink


def build_replica(args):
    if args.replica == "filesystem":
        if not args.replica_root:
            raise SystemExit("--replica-root is required for filesystem replica")
        return JsonlFilesystemReplica(args.replica_root)
    if args.replica == "github":
        token = os.environ.get("GITHUB_TOKEN")
        repository = args.github_repository or os.environ.get("GITHUB_REPOSITORY")
        if not token or not repository:
            raise SystemExit("github replica requires GITHUB_TOKEN and repository")
        return GitHubContentsReplicaSink(
            repository=repository,
            token=token,
            branch=args.github_branch,
            prefix=args.github_prefix,
        )
    if args.replica == "drive":
        token = os.environ.get("GOOGLE_DRIVE_ACCESS_TOKEN")
        folder = args.drive_folder_id or os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
        if not token or not folder:
            raise SystemExit("drive replica requires GOOGLE_DRIVE_ACCESS_TOKEN and folder id")
        return GoogleDriveFileReplicaSink(access_token=token, folder_id=folder)
    raise SystemExit(f"unsupported replica: {args.replica}")


def parse_args():
    p = argparse.ArgumentParser(description="Fail-closed external OpenAI chat boundary")
    p.add_argument("--db", default=str(Path.home() / ".fail_closed_chat" / "events.sqlite"))
    p.add_argument("--conversation-id", required=True)
    p.add_argument("--request-id", default=None)
    p.add_argument("--model", default="gpt-5.6-sol")
    p.add_argument("--stream", action="store_true")
    p.add_argument("--stream-frame-chars", type=int, default=512)
    p.add_argument("--mode", choices=["strict", "local-outbox"], default="strict")
    p.add_argument("--replica", choices=["filesystem", "github", "drive"], default="drive")
    p.add_argument("--replica-root")
    p.add_argument("--github-repository")
    p.add_argument("--github-branch", default="main")
    p.add_argument("--github-prefix", default="chat-replicas")
    p.add_argument("--drive-folder-id")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    text = sys.stdin.read()
    if not text:
        raise SystemExit("refusing empty stdin")
    request_id = args.request_id or str(uuid.uuid4())

    log = SQLiteDurableEventLog(args.db)
    replica = build_replica(args)
    committer = DurableCommitter(
        log,
        replica=replica,
        require_remote_ack=(args.mode == "strict"),
    )
    model = OpenAIResponsesAdapter(model=args.model)
    harness = BufferedFailClosedChatHarness(
        committer,
        model,
        frame_chars=args.stream_frame_chars,
    )

    if args.stream:
        for frame in harness.stream_exchange(
            conversation_id=args.conversation_id,
            request_id=request_id,
            user_text=text,
        ):
            sys.stdout.write(frame)
            sys.stdout.flush()
        sys.stdout.write("\n")
        sys.stdout.flush()
    else:
        output = harness.exchange(
            conversation_id=args.conversation_id,
            request_id=request_id,
            user_text=text,
        )
        sys.stdout.write(output + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
