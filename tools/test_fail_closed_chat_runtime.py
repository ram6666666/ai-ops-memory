import tempfile
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
import types
import unittest
from pathlib import Path

from fail_closed_chat_runtime import (
    DeliveryBlocked,
    DurableCommitter,
    FailClosedChatHarness,
    JsonlFilesystemReplica,
    OpenAIResponsesAdapter,
    RemoteAckError,
    SQLiteDurableEventLog,
)


class MemoryReplica:
    def __init__(self, *, fail_roles=None):
        self.fail_roles = set(fail_roles or [])
        self.events = []

    def replicate(self, event):
        if event.role in self.fail_roles:
            raise RuntimeError("injected remote failure")
        self.events.append(event)
        return f"ack:{event.event_hash}"


class FakeModel:
    def __init__(self, *, text="pong", chunks=None):
        self.text = text
        self.chunks = chunks or ["po", "ng"]
        self.complete_calls = 0
        self.stream_calls = 0

    def complete(self, user_text):
        self.complete_calls += 1
        return self.text

    def stream(self, user_text):
        self.stream_calls += 1
        yield from self.chunks


class FakeResponses:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("stream"):
            return iter([
                types.SimpleNamespace(type="response.created"),
                types.SimpleNamespace(type="response.output_text.delta", delta="A"),
                types.SimpleNamespace(type="response.output_text.delta", delta="B"),
                types.SimpleNamespace(type="response.output_text.done", text="AB"),
            ])
        return types.SimpleNamespace(output_text="AB")


class FailClosedProductionCandidateTests(unittest.TestCase):
    def make(self, *, fail_local_roles=None, fail_remote_roles=None, require_remote_ack=True, model=None):
        td = tempfile.TemporaryDirectory()
        db = Path(td.name) / "events.sqlite"
        log = SQLiteDurableEventLog(db, fail_roles=set(fail_local_roles or []))
        replica = MemoryReplica(fail_roles=fail_remote_roles)
        committer = DurableCommitter(log, replica=replica, require_remote_ack=require_remote_ack)
        harness = FailClosedChatHarness(committer, model or FakeModel())
        return td, log, replica, harness

    def test_nonstream_remote_ack_required_on_both_sides(self):
        td, log, replica, harness = self.make()
        self.addCleanup(td.cleanup)
        self.assertEqual(harness.exchange(conversation_id="c", request_id="r1", user_text="ping"), "pong")
        self.assertEqual([e.role for e in log.events("c")], ["user", "assistant"])
        self.assertEqual([e.role for e in replica.events], ["user", "assistant"])
        self.assertTrue(all(log.remote_receipt(e) for e in log.events("c")))
        self.assertTrue(log.verify_chain("c"))

    def test_remote_user_ack_failure_blocks_model_call(self):
        model = FakeModel()
        td, log, replica, harness = self.make(fail_remote_roles={"user"}, model=model)
        self.addCleanup(td.cleanup)
        with self.assertRaises(RemoteAckError):
            harness.exchange(conversation_id="c", request_id="r1", user_text="ping")
        self.assertEqual(model.complete_calls, 0)
        self.assertEqual([e.role for e in log.events("c")], ["user"])

    def test_remote_assistant_ack_failure_blocks_delivery(self):
        model = FakeModel()
        td, log, replica, harness = self.make(fail_remote_roles={"assistant"}, model=model)
        self.addCleanup(td.cleanup)
        with self.assertRaises(DeliveryBlocked):
            harness.exchange(conversation_id="c", request_id="r1", user_text="ping")
        self.assertEqual(model.complete_calls, 1)
        self.assertEqual([e.role for e in log.events("c")], ["user", "assistant"])
        self.assertIsNotNone(log.remote_receipt(log.events("c")[0]))
        self.assertIsNone(log.remote_receipt(log.events("c")[1]))

    def test_stream_chunks_are_committed_and_remote_acked_before_yield(self):
        model = FakeModel(chunks=["A", "B", "C"])
        td, log, replica, harness = self.make(model=model)
        self.addCleanup(td.cleanup)
        gen = harness.stream_exchange(conversation_id="c", request_id="r1", user_text="ping")
        self.assertEqual(next(gen), "A")
        self.assertEqual([e.role for e in log.events("c")], ["user", "assistant_chunk"])
        self.assertTrue(all(log.remote_receipt(e) for e in log.events("c")))
        self.assertEqual(next(gen), "B")
        self.assertEqual(next(gen), "C")
        with self.assertRaises(StopIteration):
            next(gen)
        self.assertEqual([e.role for e in log.events("c")],
                         ["user", "assistant_chunk", "assistant_chunk", "assistant_chunk", "assistant_final"])
        self.assertEqual(log.events("c")[-1].content, "ABC")
        self.assertTrue(all(log.remote_receipt(e) for e in log.events("c")))

    def test_stream_remote_chunk_failure_blocks_that_chunk_from_render(self):
        model = FakeModel(chunks=["A", "B"])
        td, log, replica, harness = self.make(fail_remote_roles={"assistant_chunk"}, model=model)
        self.addCleanup(td.cleanup)
        gen = harness.stream_exchange(conversation_id="c", request_id="r1", user_text="ping")
        with self.assertRaises(DeliveryBlocked):
            next(gen)
        self.assertEqual([e.role for e in log.events("c")], ["user", "assistant_chunk"])
        self.assertIsNone(log.remote_receipt(log.events("c")[1]))

    def test_optional_local_only_policy_allows_async_replica_failure(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        log = SQLiteDurableEventLog(Path(td.name) / "events.sqlite")
        replica = MemoryReplica(fail_roles={"user", "assistant"})
        committer = DurableCommitter(log, replica=replica, require_remote_ack=False)
        harness = FailClosedChatHarness(committer, FakeModel())
        self.assertEqual(harness.exchange(conversation_id="c", request_id="r1", user_text="ping"), "pong")
        self.assertTrue(log.verify_chain("c"))
        self.assertTrue(all(log.remote_receipt(e) is None for e in log.events("c")))

    def test_openai_responses_adapter_matches_current_responses_shape(self):
        fake = types.SimpleNamespace(responses=FakeResponses())
        adapter = OpenAIResponsesAdapter(model="gpt-5.6-sol", client=fake)
        self.assertEqual(adapter.complete("hello"), "AB")
        self.assertEqual(list(adapter.stream("hello")), ["A", "B"])
        self.assertEqual(fake.responses.calls[0], {"model": "gpt-5.6-sol", "input": "hello"})
        self.assertEqual(fake.responses.calls[1], {"model": "gpt-5.6-sol", "input": "hello", "stream": True})

    def test_replay_is_idempotent_across_remote_ack(self):
        model = FakeModel()
        td, log, replica, harness = self.make(model=model)
        self.addCleanup(td.cleanup)
        self.assertEqual(harness.exchange(conversation_id="c", request_id="r1", user_text="ping"), "pong")
        first_count = len(replica.events)
        self.assertEqual(harness.exchange(conversation_id="c", request_id="r1", user_text="ping"), "pong")
        self.assertEqual(len(log.events("c")), 2)
        self.assertEqual(len(replica.events), first_count)
        self.assertEqual(model.complete_calls, 1)

    def test_assistant_remote_ack_recovery_does_not_reinvoke_model(self):
        model = FakeModel(text="stable")
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        log = SQLiteDurableEventLog(Path(td.name) / "events.sqlite")
        replica = MemoryReplica(fail_roles={"assistant"})
        harness = FailClosedChatHarness(DurableCommitter(log, replica=replica, require_remote_ack=True), model)
        with self.assertRaises(DeliveryBlocked):
            harness.exchange(conversation_id="c", request_id="r1", user_text="ping")
        self.assertEqual(model.complete_calls, 1)
        replica.fail_roles.clear()
        self.assertEqual(harness.exchange(conversation_id="c", request_id="r1", user_text="ping"), "stable")
        self.assertEqual(model.complete_calls, 1)
        self.assertIsNotNone(log.remote_receipt(log.get_event("c", "r1:assistant")))

    def test_filesystem_replica_is_atomic_and_idempotent(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        root = Path(td.name)
        log = SQLiteDurableEventLog(root / "events.sqlite")
        replica = JsonlFilesystemReplica(root / "replica")
        committer = DurableCommitter(log, replica=replica, require_remote_ack=True)
        r1 = committer.commit(conversation_id="c", event_id="e1", role="user", content="hello")
        r2 = committer.commit(conversation_id="c", event_id="e1", role="user", content="hello")
        self.assertEqual(r1.event.event_hash, r2.event.event_hash)
        self.assertEqual(r1.remote_receipt, r2.remote_receipt)
        files = list((root / "replica").rglob("*.json"))
        self.assertEqual(len(files), 1)
        self.assertIn('"content":"hello"', files[0].read_text())

    def test_concurrent_local_commits_preserve_single_hash_chain(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        log = SQLiteDurableEventLog(Path(td.name) / "events.sqlite")
        def write(i):
            return log.append(conversation_id="c", event_id=f"e{i}", role="user", content=str(i))
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(write, range(24)))
        events = log.events("c")
        self.assertEqual(len(events), 24)
        self.assertEqual([e.seq for e in events], list(range(1, 25)))
        self.assertTrue(log.verify_chain("c"))

    def test_full_sync_commit_survives_process_exit(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        db = Path(td.name) / "crash.sqlite"
        code = (
            "from fail_closed_chat_runtime import SQLiteDurableEventLog;"
            f"l=SQLiteDurableEventLog(r'{db}');"
            "l.append(conversation_id='c',event_id='e1',role='user',content='before-exit');"
            "import os;os._exit(0)"
        )
        env = dict(**__import__('os').environ)
        env['PYTHONPATH'] = str(Path(__file__).parent)
        subprocess.run([sys.executable, "-c", code], check=True, env=env)
        reopened = SQLiteDurableEventLog(db)
        self.assertEqual(reopened.get_event("c", "e1").content, "before-exit")
        self.assertTrue(reopened.verify_chain("c"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
