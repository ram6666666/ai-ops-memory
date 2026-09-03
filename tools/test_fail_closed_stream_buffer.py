import tempfile
import unittest
from pathlib import Path

from fail_closed_chat_runtime_v2 import DurableCommitter, RemoteAckError, SQLiteDurableEventLog
from fail_closed_stream_buffer import BufferedFailClosedChatHarness


class MemoryReplica:
    def __init__(self, fail_frame_index=None):
        self.events = []
        self.fail_frame_index = fail_frame_index
        self.frame_seen = 0

    def replicate(self, event):
        if event.role == "assistant_frame":
            index = self.frame_seen
            self.frame_seen += 1
            if index == self.fail_frame_index:
                raise RuntimeError("injected frame replica failure")
        self.events.append(event)
        return "ack:" + event.event_hash


class FakeModel:
    def __init__(self, deltas):
        self.deltas = deltas

    def complete(self, text):
        return "".join(self.deltas)

    def stream(self, text):
        yield from self.deltas


class BufferedStreamingTests(unittest.TestCase):
    def make(self, deltas, *, frame_chars=4, fail_frame_index=None):
        td = tempfile.TemporaryDirectory()
        log = SQLiteDurableEventLog(Path(td.name) / "events.sqlite")
        replica = MemoryReplica(fail_frame_index=fail_frame_index)
        committer = DurableCommitter(log, replica=replica, require_remote_ack=True)
        harness = BufferedFailClosedChatHarness(
            committer,
            FakeModel(deltas),
            frame_chars=frame_chars,
        )
        return td, log, replica, harness

    def test_small_provider_deltas_are_coalesced_before_render(self):
        td, log, replica, harness = self.make(["a", "b", "c", "d", "e", "f"], frame_chars=4)
        self.addCleanup(td.cleanup)
        frames = list(harness.stream_exchange(conversation_id="c", request_id="r", user_text="x"))
        self.assertEqual(frames, ["abcd", "ef"])
        events = log.events("c")
        self.assertEqual([e.role for e in events], ["user", "assistant_frame", "assistant_frame", "assistant_final"])
        self.assertEqual(events[-1].content, "abcdef")
        self.assertTrue(all(log.remote_receipt(e) for e in events))
        self.assertTrue(log.verify_chain("c"))

    def test_frame_is_acked_before_generator_yields_it(self):
        td, log, replica, harness = self.make(["ab", "cd", "ef"], frame_chars=4)
        self.addCleanup(td.cleanup)
        gen = harness.stream_exchange(conversation_id="c", request_id="r", user_text="x")
        first = next(gen)
        self.assertEqual(first, "abcd")
        frame_event = [e for e in log.events("c") if e.role == "assistant_frame"][0]
        self.assertIsNotNone(log.remote_receipt(frame_event))

    def test_remote_failure_blocks_unacked_frame_from_render(self):
        td, log, replica, harness = self.make(["ab", "cd", "ef"], frame_chars=4, fail_frame_index=0)
        self.addCleanup(td.cleanup)
        gen = harness.stream_exchange(conversation_id="c", request_id="r", user_text="x")
        with self.assertRaises(Exception):
            next(gen)
        frame_event = [e for e in log.events("c") if e.role == "assistant_frame"][0]
        self.assertIsNone(log.remote_receipt(frame_event))

    def test_invalid_frame_size_rejected(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        log = SQLiteDurableEventLog(Path(td.name) / "events.sqlite")
        committer = DurableCommitter(log, replica=MemoryReplica(), require_remote_ack=True)
        with self.assertRaises(ValueError):
            BufferedFailClosedChatHarness(committer, FakeModel(["x"]), frame_chars=0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
