import hashlib
import unittest

from fail_closed_chat_runtime_v2 import Event, RemoteAckError
from google_drive_replica_sink import GoogleDriveFileReplicaSink


EVENT = Event(
    conversation_id="synthetic-drive-test",
    event_id="e1",
    seq=1,
    role="synthetic_test",
    content="non-sensitive",
    created_ns=123,
    prev_hash="0" * 64,
    event_hash="a" * 64,
)


class FakeDriveSink(GoogleDriveFileReplicaSink):
    def __init__(self, *, existing=None, download=None, create_result=None):
        super().__init__(access_token="fake-runtime-token", folder_id="folder")
        self.existing = existing
        self.download_bytes = download
        self.create_result = create_result
        self.created = 0

    def _find_existing(self, name):
        self.last_name = name
        return self.existing

    def _create(self, name, content):
        self.created += 1
        self.created_content = content
        if self.create_result is not None:
            return self.create_result
        return {
            "id": "file-created",
            "md5Checksum": hashlib.md5(content).hexdigest(),
        }

    def _download(self, file_id):
        if self.download_bytes is not None:
            return self.download_bytes
        return self.created_content


class GoogleDriveReplicaSinkTests(unittest.TestCase):
    def test_create_then_exact_readback_returns_ack(self):
        expected = GoogleDriveFileReplicaSink.event_bytes(EVENT)
        sink = FakeDriveSink(download=expected)
        receipt = sink.replicate(EVENT)
        self.assertEqual(sink.created, 1)
        self.assertTrue(receipt.startswith("gdrive:file-created:"))

    def test_existing_exact_file_is_idempotent(self):
        expected = GoogleDriveFileReplicaSink.event_bytes(EVENT)
        md5 = hashlib.md5(expected).hexdigest()
        sink = FakeDriveSink(
            existing={"id": "existing", "md5Checksum": md5},
            download=expected,
        )
        receipt = sink.replicate(EVENT)
        self.assertEqual(sink.created, 0)
        self.assertEqual(receipt, f"gdrive:existing:{md5}")

    def test_readback_mismatch_fails_closed(self):
        sink = FakeDriveSink(download=b"wrong")
        with self.assertRaises(RemoteAckError):
            sink.replicate(EVENT)

    def test_provider_md5_mismatch_fails_closed(self):
        expected = GoogleDriveFileReplicaSink.event_bytes(EVENT)
        sink = FakeDriveSink(
            existing={"id": "existing", "md5Checksum": "0" * 32},
            download=expected,
        )
        with self.assertRaises(RemoteAckError):
            sink.replicate(EVENT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
