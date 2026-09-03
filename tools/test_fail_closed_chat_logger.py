import os
import sqlite3
import tempfile
import unittest

from fail_closed_chat_logger import (
    DeliveryBlocked,
    DurableLogError,
    FailClosedChatHarness,
    SQLiteDurableEventLog,
)


class FailClosedLoggerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "events.sqlite3")

    def tearDown(self):
        self.tmp.cleanup()

    def test_success_is_write_before_call_and_write_before_deliver(self):
        trace = []
        log = SQLiteDurableEventLog(self.db)

        def model(text):
            events = log.events("c1")
            self.assertEqual([(e.role, e.content) for e in events], [("user", "hello")])
            trace.append("model_called")
            return "world"

        out = FailClosedChatHarness(log, model).exchange(
            conversation_id="c1", request_id="r1", user_text="hello"
        )
        self.assertEqual(out, "world")
        self.assertEqual(trace, ["model_called"])
        self.assertEqual(
            [(e.seq, e.role, e.content) for e in log.events("c1")],
            [(1, "user", "hello"), (2, "assistant", "world")],
        )
        self.assertTrue(log.verify_chain("c1"))

    def test_input_write_failure_blocks_model_call(self):
        called = False
        log = SQLiteDurableEventLog(self.db, fail_roles={"user"})

        def model(text):
            nonlocal called
            called = True
            return "should-not-run"

        with self.assertRaises(DurableLogError):
            FailClosedChatHarness(log, model).exchange(
                conversation_id="c1", request_id="r1", user_text="hello"
            )
        self.assertFalse(called)
        self.assertEqual(log.events("c1"), [])

    def test_output_write_failure_blocks_delivery(self):
        called = False
        log = SQLiteDurableEventLog(self.db, fail_roles={"assistant"})

        def model(text):
            nonlocal called
            called = True
            return "generated-but-not-delivered"

        with self.assertRaises(DeliveryBlocked):
            FailClosedChatHarness(log, model).exchange(
                conversation_id="c1", request_id="r1", user_text="hello"
            )
        self.assertTrue(called)
        self.assertEqual(
            [(e.role, e.content) for e in log.events("c1")],
            [("user", "hello")],
        )

    def test_restart_continuity_and_idempotent_retry(self):
        log1 = SQLiteDurableEventLog(self.db)
        h1 = FailClosedChatHarness(log1, lambda _: "a1")
        self.assertEqual(h1.exchange(conversation_id="c1", request_id="r1", user_text="u1"), "a1")

        log2 = SQLiteDurableEventLog(self.db)
        h2 = FailClosedChatHarness(log2, lambda _: "a2")
        self.assertEqual(h2.exchange(conversation_id="c1", request_id="r2", user_text="u2"), "a2")
        self.assertEqual([e.seq for e in log2.events("c1")], [1, 2, 3, 4])
        self.assertTrue(log2.verify_chain("c1"))

        h_retry = FailClosedChatHarness(log2, lambda _: "a1")
        self.assertEqual(h_retry.exchange(conversation_id="c2", request_id="r1", user_text="u1"), "a1")
        self.assertEqual(h_retry.exchange(conversation_id="c2", request_id="r1", user_text="u1"), "a1")
        self.assertEqual(len(log2.events("c2")), 2)
        self.assertTrue(log2.verify_chain("c2"))

    def test_tamper_is_detected(self):
        log = SQLiteDurableEventLog(self.db)
        FailClosedChatHarness(log, lambda _: "a1").exchange(
            conversation_id="c1", request_id="r1", user_text="u1"
        )
        self.assertTrue(log.verify_chain("c1"))
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE events SET content='tampered' WHERE conversation_id='c1' AND seq=1")
            conn.commit()
        self.assertFalse(log.verify_chain("c1"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
