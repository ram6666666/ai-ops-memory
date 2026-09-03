from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict
from typing import Optional

from fail_closed_chat_runtime_v2 import Event, RemoteAckError


class GitHubContentsReplicaSink:
    """Network ReplicaSink backed by the GitHub Contents API.

    Intended for synthetic validation or a deliberately selected private archive repo.
    Do not use a public repository for private conversation content.
    A successful replicate() returns only after provider write + GET readback match.
    """

    def __init__(self, *, repository: str, token: str, branch: str = "main",
                 prefix: str = "replicas", api_base: str = "https://api.github.com"):
        if "/" not in repository:
            raise ValueError("repository must be owner/name")
        if not token:
            raise ValueError("token is required")
        self.repository = repository
        self.token = token
        self.branch = branch
        self.prefix = prefix.strip("/")
        self.api_base = api_base.rstrip("/")

    @staticmethod
    def event_bytes(event: Event) -> bytes:
        return (json.dumps(asdict(event), ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")) + "\n").encode("utf-8")

    def _path(self, event: Event) -> str:
        safe_conversation = event.conversation_id.encode("utf-8").hex()[:64] or "empty"
        return f"{self.prefix}/{safe_conversation}/{event.seq:012d}-{event.event_hash}.json"

    def _url(self, path: str) -> str:
        owner, repo = self.repository.split("/", 1)
        encoded = urllib.parse.quote(path, safe="/")
        return f"{self.api_base}/repos/{owner}/{repo}/contents/{encoded}"

    def _request(self, method: str, url: str, body: Optional[dict] = None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "fail-closed-chat-replica/1",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read()
                return resp.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            detail = raw.decode("utf-8", "replace")[:1000]
            raise RemoteAckError(f"GitHub HTTP {exc.code}: {detail}") from exc
        except OSError as exc:
            raise RemoteAckError(f"GitHub network failure: {exc}") from exc

    def _get(self, path: str):
        url = self._url(path) + "?ref=" + urllib.parse.quote(self.branch, safe="")
        try:
            return self._request("GET", url)[1]
        except RemoteAckError as exc:
            if "GitHub HTTP 404" in str(exc):
                return None
            raise

    def replicate(self, event: Event) -> str:
        path = self._path(event)
        expected = self.event_bytes(event)
        existing = self._get(path)
        if existing is not None:
            current = base64.b64decode(existing.get("content", "").replace("\n", ""))
            if current != expected:
                raise RemoteAckError("GitHub replica path collision/content mismatch")
            sha = str(existing.get("sha", ""))
            if not sha:
                raise RemoteAckError("GitHub readback missing blob sha")
            return f"github:{self.repository}:{sha}"

        body = {
            "message": f"Replica synthetic/chat event {event.event_hash[:12]}",
            "content": base64.b64encode(expected).decode("ascii"),
            "branch": self.branch,
        }
        self._request("PUT", self._url(path), body)

        readback = self._get(path)
        if readback is None:
            raise RemoteAckError("GitHub write returned but readback is missing")
        actual = base64.b64decode(readback.get("content", "").replace("\n", ""))
        if actual != expected:
            raise RemoteAckError("GitHub post-write readback mismatch")
        sha = str(readback.get("sha", ""))
        if not sha:
            raise RemoteAckError("GitHub readback missing blob sha")
        return f"github:{self.repository}:{sha}"
