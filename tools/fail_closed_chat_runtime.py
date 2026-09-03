from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from dataclasses import dataclass
from contextlib import closing
from pathlib import Path
from typing import Iterable, Iterator, Optional, Protocol


class DurableLogError(RuntimeError):
    pass


class RemoteAckError(DurableLogError):
    pass


class DeliveryBlocked(DurableLogError):
    pass


@dataclass(frozen=True)
class Event:
    conversation_id: str
    event_id: str
    seq: int
    role: str
    content: str
    created_ns: int
    prev_hash: str
    event_hash: str


@dataclass(frozen=True)
class CommitReceipt:
    event: Event
    local_committed: bool
    remote_acked: bool
    remote_receipt: Optional[str]


class ReplicaSink(Protocol):
    def replicate(self, event: Event) -> str:
        """Persist event remotely and return an opaque durable ACK/receipt."""
        ...


class SQLiteDurableEventLog:
    """Durable local event log with WAL + FULL synchronous commits + hash chain."""

    def __init__(self, path: str | os.PathLike[str], *, fail_roles: Optional[set[str]] = None):
        self.path = str(path)
        self.fail_roles = fail_roles or set()
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    conversation_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_ns INTEGER NOT NULL,
                    prev_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    PRIMARY KEY (conversation_id, event_id),
                    UNIQUE (conversation_id, seq)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS replica_receipts (
                    conversation_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    receipt TEXT NOT NULL,
                    acked_ns INTEGER NOT NULL,
                    PRIMARY KEY (conversation_id, event_id),
                    FOREIGN KEY (conversation_id, event_id)
                        REFERENCES events(conversation_id, event_id)
                )
                """
            )

    @staticmethod
    def _canonical_payload(conversation_id: str, event_id: str, seq: int, role: str,
                           content: str, created_ns: int, prev_hash: str) -> bytes:
        obj = {
            "content": content,
            "conversation_id": conversation_id,
            "created_ns": created_ns,
            "event_id": event_id,
            "prev_hash": prev_hash,
            "role": role,
            "seq": seq,
        }
        return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def append(self, *, conversation_id: str, event_id: str, role: str, content: str) -> Event:
        if role in self.fail_roles:
            raise DurableLogError(f"injected durable-write failure for role={role}")

        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """SELECT seq, role, content, created_ns, prev_hash, event_hash
                   FROM events WHERE conversation_id=? AND event_id=?""",
                (conversation_id, event_id),
            ).fetchone()
            if row is not None:
                seq, old_role, old_content, created_ns, prev_hash, event_hash = row
                if old_role != role or old_content != content:
                    raise DurableLogError("event_id replay conflict")
                conn.execute("COMMIT")
                return Event(conversation_id, event_id, seq, role, content, created_ns, prev_hash, event_hash)

            prev = conn.execute(
                """SELECT seq, event_hash FROM events
                   WHERE conversation_id=? ORDER BY seq DESC LIMIT 1""",
                (conversation_id,),
            ).fetchone()
            if prev is None:
                seq = 1
                prev_hash = "0" * 64
            else:
                seq = int(prev[0]) + 1
                prev_hash = str(prev[1])

            created_ns = time.time_ns()
            payload = self._canonical_payload(conversation_id, event_id, seq, role, content, created_ns, prev_hash)
            event_hash = hashlib.sha256(payload).hexdigest()
            conn.execute(
                """INSERT INTO events
                   (conversation_id, event_id, seq, role, content, created_ns, prev_hash, event_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (conversation_id, event_id, seq, role, content, created_ns, prev_hash, event_hash),
            )
            conn.execute("COMMIT")
            return Event(conversation_id, event_id, seq, role, content, created_ns, prev_hash, event_hash)
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            conn.close()

    def mark_remote_ack(self, event: Event, receipt: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                """SELECT event_hash, receipt FROM replica_receipts
                   WHERE conversation_id=? AND event_id=?""",
                (event.conversation_id, event.event_id),
            ).fetchone()
            if existing is not None:
                old_hash, _old_receipt = existing
                if old_hash != event.event_hash:
                    conn.execute("ROLLBACK")
                    raise DurableLogError("replica receipt hash conflict")
                conn.execute("COMMIT")
                return
            conn.execute(
                """INSERT INTO replica_receipts
                   (conversation_id, event_id, event_hash, receipt, acked_ns)
                   VALUES (?, ?, ?, ?, ?)""",
                (event.conversation_id, event.event_id, event.event_hash, receipt, time.time_ns()),
            )
            conn.execute("COMMIT")

    def remote_receipt(self, event: Event) -> Optional[str]:
        with closing(self._connect()) as conn:
            row = conn.execute(
                """SELECT receipt FROM replica_receipts
                   WHERE conversation_id=? AND event_id=? AND event_hash=?""",
                (event.conversation_id, event.event_id, event.event_hash),
            ).fetchone()
        return None if row is None else str(row[0])

    def get_event(self, conversation_id: str, event_id: str) -> Optional[Event]:
        conn = self._connect()
        try:
            row = conn.execute(
                """SELECT seq, role, content, created_ns, prev_hash, event_hash
                   FROM events WHERE conversation_id=? AND event_id=?""",
                (conversation_id, event_id),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        seq, role, content, created_ns, prev_hash, event_hash = row
        return Event(conversation_id, event_id, seq, role, content, created_ns, prev_hash, event_hash)

    def events(self, conversation_id: str) -> list[Event]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """SELECT event_id, seq, role, content, created_ns, prev_hash, event_hash
                   FROM events WHERE conversation_id=? ORDER BY seq""",
                (conversation_id,),
            ).fetchall()
        return [Event(conversation_id, *row) for row in rows]

    def verify_chain(self, conversation_id: str) -> bool:
        prev_hash = "0" * 64
        expected_seq = 1
        for ev in self.events(conversation_id):
            if ev.seq != expected_seq or ev.prev_hash != prev_hash:
                return False
            payload = self._canonical_payload(
                ev.conversation_id, ev.event_id, ev.seq, ev.role, ev.content, ev.created_ns, ev.prev_hash
            )
            if hashlib.sha256(payload).hexdigest() != ev.event_hash:
                return False
            prev_hash = ev.event_hash
            expected_seq += 1
        return True


class JsonlFilesystemReplica:
    """Secondary durable filesystem replica using atomic per-event files.

    This is useful for a second disk/mounted volume and for production fault testing.
    It is not itself proof of cloud durability unless the target filesystem provides it.
    """

    def __init__(self, root: str | os.PathLike[str]):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def replicate(self, event: Event) -> str:
        safe_conversation = hashlib.sha256(event.conversation_id.encode("utf-8")).hexdigest()[:24]
        directory = self.root / safe_conversation
        directory.mkdir(parents=True, exist_ok=True)
        final = directory / f"{event.seq:012d}-{event.event_hash}.json"
        payload = {
            "conversation_id": event.conversation_id,
            "event_id": event.event_id,
            "seq": event.seq,
            "role": event.role,
            "content": event.content,
            "created_ns": event.created_ns,
            "prev_hash": event.prev_hash,
            "event_hash": event.event_hash,
        }
        encoded = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        if final.exists():
            existing = final.read_bytes()
            if existing != encoded:
                raise RemoteAckError("filesystem replica collision/content mismatch")
            return f"file:{final}"
        tmp = directory / f".{final.name}.{os.getpid()}.tmp"
        with open(tmp, "xb") as fh:
            fh.write(encoded)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, final)
        try:
            dir_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
        return f"file:{final}"


class DurableCommitter:
    """Combines local durable commit with optional mandatory remote ACK."""

    def __init__(self, log: SQLiteDurableEventLog, *, replica: Optional[ReplicaSink] = None,
                 require_remote_ack: bool = True):
        if require_remote_ack and replica is None:
            raise ValueError("require_remote_ack=True requires a replica")
        self.log = log
        self.replica = replica
        self.require_remote_ack = require_remote_ack

    def commit(self, *, conversation_id: str, event_id: str, role: str, content: str) -> CommitReceipt:
        event = self.log.append(
            conversation_id=conversation_id,
            event_id=event_id,
            role=role,
            content=content,
        )
        if self.replica is None:
            return CommitReceipt(event, True, False, None)

        existing = self.log.remote_receipt(event)
        if existing is not None:
            return CommitReceipt(event, True, True, existing)

        try:
            receipt = self.replica.replicate(event)
        except Exception as exc:
            if self.require_remote_ack:
                raise RemoteAckError("remote durable ACK failed") from exc
            return CommitReceipt(event, True, False, None)

        self.log.mark_remote_ack(event, receipt)
        return CommitReceipt(event, True, True, receipt)


class ModelAdapter(Protocol):
    def complete(self, user_text: str) -> str:
        ...

    def stream(self, user_text: str) -> Iterable[str]:
        ...


class OpenAIResponsesAdapter:
    """OpenAI Responses API adapter.

    Import is lazy so the core logger has no mandatory external dependency.
    A live call requires the official `openai` Python package and OPENAI_API_KEY.
    """

    def __init__(self, *, model: str = "gpt-5.6-sol", client=None):
        self.model = model
        if client is None:
            from openai import OpenAI  # type: ignore
            client = OpenAI()
        self.client = client

    def complete(self, user_text: str) -> str:
        response = self.client.responses.create(model=self.model, input=user_text)
        return str(response.output_text)

    def stream(self, user_text: str) -> Iterator[str]:
        stream = self.client.responses.create(model=self.model, input=user_text, stream=True)
        for event in stream:
            if getattr(event, "type", None) == "response.output_text.delta":
                delta = getattr(event, "delta", None)
                if delta:
                    yield str(delta)


class FailClosedChatHarness:
    """Strict write-before-call and write-before-deliver harness."""

    def __init__(self, committer: DurableCommitter, model: ModelAdapter):
        self.committer = committer
        self.model = model

    def exchange(self, *, conversation_id: str, request_id: str, user_text: str) -> str:
        self.committer.commit(
            conversation_id=conversation_id,
            event_id=f"{request_id}:user",
            role="user",
            content=user_text,
        )

        assistant_event_id = f"{request_id}:assistant"
        existing = self.committer.log.get_event(conversation_id, assistant_event_id)
        if existing is not None:
            try:
                self.committer.commit(
                    conversation_id=conversation_id,
                    event_id=assistant_event_id,
                    role="assistant",
                    content=existing.content,
                )
            except Exception as exc:
                raise DeliveryBlocked("cached assistant output durable ACK retry failed; delivery blocked") from exc
            return existing.content

        assistant_text = self.model.complete(user_text)

        try:
            self.committer.commit(
                conversation_id=conversation_id,
                event_id=assistant_event_id,
                role="assistant",
                content=assistant_text,
            )
        except Exception as exc:
            raise DeliveryBlocked("assistant output durable commit/ACK failed; delivery blocked") from exc

        return assistant_text

    def stream_exchange(self, *, conversation_id: str, request_id: str, user_text: str) -> Iterator[str]:
        self.committer.commit(
            conversation_id=conversation_id,
            event_id=f"{request_id}:user",
            role="user",
            content=user_text,
        )

        chunks: list[str] = []
        for index, delta in enumerate(self.model.stream(user_text)):
            try:
                self.committer.commit(
                    conversation_id=conversation_id,
                    event_id=f"{request_id}:assistant:chunk:{index:08d}",
                    role="assistant_chunk",
                    content=delta,
                )
            except Exception as exc:
                raise DeliveryBlocked(
                    f"assistant stream chunk {index} durable commit/ACK failed; render blocked"
                ) from exc
            chunks.append(delta)
            yield delta

        full_text = "".join(chunks)
        try:
            self.committer.commit(
                conversation_id=conversation_id,
                event_id=f"{request_id}:assistant:final",
                role="assistant_final",
                content=full_text,
            )
        except Exception as exc:
            raise DeliveryBlocked("assistant stream finalization durable commit/ACK failed") from exc
