from __future__ import annotations

from typing import Iterator

from fail_closed_chat_runtime_v2 import DeliveryBlocked, DurableCommitter, ModelAdapter


class BufferedFailClosedChatHarness:
    """Fail-closed harness with bounded-frame write-before-render streaming.

    Provider deltas are buffered only until `frame_chars` is reached. A frame is
    not yielded/rendered until the configured DurableCommitter barrier succeeds.
    This preserves the visible-text durability invariant while avoiding one remote
    write per tiny provider delta.
    """

    def __init__(self, committer: DurableCommitter, model: ModelAdapter, *, frame_chars: int = 512):
        if frame_chars < 1:
            raise ValueError("frame_chars must be >= 1")
        self.committer = committer
        self.model = model
        self.frame_chars = frame_chars

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
                raise DeliveryBlocked("cached assistant durability retry failed") from exc
            return existing.content

        text = self.model.complete(user_text)
        try:
            self.committer.commit(
                conversation_id=conversation_id,
                event_id=assistant_event_id,
                role="assistant",
                content=text,
            )
        except Exception as exc:
            raise DeliveryBlocked("assistant durability failed; delivery blocked") from exc
        return text

    def stream_exchange(self, *, conversation_id: str, request_id: str, user_text: str) -> Iterator[str]:
        self.committer.commit(
            conversation_id=conversation_id,
            event_id=f"{request_id}:user",
            role="user",
            content=user_text,
        )

        pending: list[str] = []
        pending_chars = 0
        rendered_frames: list[str] = []
        frame_index = 0

        def flush_frame() -> str | None:
            nonlocal pending, pending_chars, frame_index
            if not pending:
                return None
            frame = "".join(pending)
            try:
                self.committer.commit(
                    conversation_id=conversation_id,
                    event_id=f"{request_id}:assistant:frame:{frame_index:08d}",
                    role="assistant_frame",
                    content=frame,
                )
            except Exception as exc:
                raise DeliveryBlocked(
                    f"assistant frame {frame_index} durability failed; render blocked"
                ) from exc
            frame_index += 1
            pending = []
            pending_chars = 0
            rendered_frames.append(frame)
            return frame

        for delta in self.model.stream(user_text):
            pending.append(delta)
            pending_chars += len(delta)
            if pending_chars >= self.frame_chars:
                frame = flush_frame()
                if frame is not None:
                    yield frame

        frame = flush_frame()
        if frame is not None:
            yield frame

        full_text = "".join(rendered_frames)
        try:
            self.committer.commit(
                conversation_id=conversation_id,
                event_id=f"{request_id}:assistant:final",
                role="assistant_final",
                content=full_text,
            )
        except Exception as exc:
            raise DeliveryBlocked("stream finalization durability failed") from exc
