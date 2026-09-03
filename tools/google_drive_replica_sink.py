from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict
from typing import Optional

from fail_closed_chat_runtime_v2 import Event, RemoteAckError


class GoogleDriveFileReplicaSink:
    """Google Drive v3 file ReplicaSink with exact post-write readback.

    Uses an injected OAuth bearer token and one target folder. Each event is stored
    as an immutable JSON file. replicate() returns only after Drive readback bytes
    exactly match the event bytes. The token is runtime-only and must never be
    persisted in the operations repository.
    """

    def __init__(self, *, access_token: str, folder_id: str,
                 api_base: str = "https://www.googleapis.com"):
        if not access_token:
            raise ValueError("access_token is required")
        if not folder_id:
            raise ValueError("folder_id is required")
        self.access_token = access_token
        self.folder_id = folder_id
        self.api_base = api_base.rstrip("/")

    @staticmethod
    def event_bytes(event: Event) -> bytes:
        return (json.dumps(asdict(event), ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")) + "\n").encode("utf-8")

    @staticmethod
    def file_name(event: Event) -> str:
        conversation = hashlib.sha256(event.conversation_id.encode("utf-8")).hexdigest()[:20]
        return f"chat-event-{conversation}-{event.seq:012d}-{event.event_hash}.json"

    @staticmethod
    def _quote_drive_q(value: str) -> str:
        return value.replace("\\", "\\\\").replace("'", "\\'")

    def _request(self, method: str, url: str, *, body: Optional[bytes] = None,
                 content_type: Optional[str] = None, accept_json: bool = True):
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": "fail-closed-chat-drive-replica/1",
        }
        if content_type:
            headers["Content-Type"] = content_type
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                if accept_json:
                    return resp.status, (json.loads(raw) if raw else {})
                return resp.status, raw
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:1200]
            raise RemoteAckError(f"Google Drive HTTP {exc.code}: {detail}") from exc
        except OSError as exc:
            raise RemoteAckError(f"Google Drive network failure: {exc}") from exc

    def _find_existing(self, name: str):
        q = (
            f"'{self._quote_drive_q(self.folder_id)}' in parents and "
            f"name = '{self._quote_drive_q(name)}' and trashed = false"
        )
        params = urllib.parse.urlencode({
            "q": q,
            "spaces": "drive",
            "pageSize": 2,
            "fields": "files(id,name,size,md5Checksum)",
        })
        _, obj = self._request("GET", f"{self.api_base}/drive/v3/files?{params}")
        files = obj.get("files", [])
        if len(files) > 1:
            raise RemoteAckError("multiple Drive files match immutable event name")
        return files[0] if files else None

    def _download(self, file_id: str) -> bytes:
        encoded = urllib.parse.quote(file_id, safe="")
        _, raw = self._request(
            "GET", f"{self.api_base}/drive/v3/files/{encoded}?alt=media",
            accept_json=False,
        )
        return raw

    def _create(self, name: str, content: bytes):
        boundary = "fc-" + uuid.uuid4().hex
        metadata = json.dumps({
            "name": name,
            "parents": [self.folder_id],
            "mimeType": "application/json",
        }, separators=(",", ":")).encode("utf-8")
        body = (
            b"--" + boundary.encode() + b"\r\n"
            b"Content-Type: application/json; charset=UTF-8\r\n\r\n" + metadata + b"\r\n"
            b"--" + boundary.encode() + b"\r\n"
            b"Content-Type: application/json\r\n\r\n" + content + b"\r\n"
            b"--" + boundary.encode() + b"--\r\n"
        )
        fields = urllib.parse.quote("id,name,size,md5Checksum", safe=",")
        _, obj = self._request(
            "POST",
            f"{self.api_base}/upload/drive/v3/files?uploadType=multipart&fields={fields}",
            body=body,
            content_type=f"multipart/related; boundary={boundary}",
        )
        if not obj.get("id"):
            raise RemoteAckError("Google Drive create missing file id")
        return obj

    def replicate(self, event: Event) -> str:
        name = self.file_name(event)
        expected = self.event_bytes(event)
        existing = self._find_existing(name)
        if existing is None:
            existing = self._create(name, expected)

        file_id = str(existing.get("id", ""))
        if not file_id:
            raise RemoteAckError("Google Drive replica missing file id")
        actual = self._download(file_id)
        if actual != expected:
            raise RemoteAckError("Google Drive post-write readback mismatch")

        md5 = str(existing.get("md5Checksum") or "")
        expected_md5 = hashlib.md5(expected).hexdigest()
        if md5 and md5 != expected_md5:
            raise RemoteAckError("Google Drive md5Checksum mismatch")
        return f"gdrive:{file_id}:{md5 or expected_md5}"
