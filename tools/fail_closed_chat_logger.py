from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


class DurableLogError(RuntimeError):
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


class SQLiteDurableEventLog:
    """Durable local event log with FULL synchronous commits and a hash chain.

    The log is the authority for whether a message may cross the harness boundary.
    An append either commits durably or raises; callers must fail closed on error.
    """

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
        with self._connect() as conn:
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

    def events(self, conversation_id: str) -> list[Event]:
        with self._connect() as conn:
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


class FailClosedChatHarness:
    """Write-before-call + write-before-deliver harness.

    User input must commit before model_fn executes.
    Assistant output must commit before this method returns the text to the caller.
    """

    def __init__(self, log: SQLiteDurableEventLog, model_fn: Callable[[str], str]):
        self.log = log
        self.model_fn = model_fn

    def exchange(self, *, conversation_id: str, request_id: str, user_text: str) -> str:
        self.log.append(
            conversation_id=conversation_id,
            event_id=f"{request_id}:user",
            role="user",
            content=user_text,
        )

        assistant_text = self.model_fn(user_text)

        try:
            self.log.append(
                conversation_id=conversation_id,
                event_id=f"{request_id}:assistant",
                role="assistant",
                content=assistant_text,
            )
        except Exception as exc:
            raise DeliveryBlocked("assistant output durable commit failed; delivery blocked") from exc

        return assistant_text
