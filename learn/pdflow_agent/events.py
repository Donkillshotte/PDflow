"""Small in-process event bus used by the local agent and SSE endpoint."""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Mapping
import json
from typing import Any


DEFAULT_MAX_EVENTS = 256
DEFAULT_MAX_BYTES = 2 * 1024 * 1024
DEFAULT_MAX_EVENT_BYTES = 256 * 1024


def _serialized_size(value: Any) -> int:
    return len(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
    )


class EventBus:
    """Bounded event history for the local agent and its SSE consumers.

    Event payloads are hints for refreshing state, not a durable log.  Keep a
    small replay window so a reconnect cannot make the agent or browser retain
    an unbounded stream of reports and log chunks.  The durable job/report
    files remain the source of truth.
    """

    def __init__(
        self,
        max_events: int = DEFAULT_MAX_EVENTS,
        max_bytes: int = DEFAULT_MAX_BYTES,
        max_event_bytes: int = DEFAULT_MAX_EVENT_BYTES,
    ) -> None:
        if max_events < 1 or max_bytes < 1 or max_event_bytes < 1:
            raise ValueError("event bus limits must be positive")
        self._max_events = max_events
        self._max_bytes = max_bytes
        self._max_event_bytes = max_event_bytes
        self._events: deque[tuple[dict[str, Any], int]] = deque()
        self._bytes = 0
        self._condition = threading.Condition()
        self._sequence = 0

    def emit(self, event_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._condition:
            self._sequence += 1
            event = {
                "event_id": self._sequence,
                "type": event_type,
                "timestamp": time.time(),
                "payload": dict(payload) if isinstance(payload, Mapping) else {},
            }
            size = _serialized_size(event)
            if size > self._max_event_bytes:
                raw_payload = event["payload"]
                event["payload"] = {
                    "truncated": True,
                    "event_type": event_type,
                    "original_bytes": size,
                    "keys": sorted(str(key) for key in raw_payload)[:64],
                }
                size = _serialized_size(event)
            self._events.append((event, size))
            self._bytes += size
            while len(self._events) > self._max_events or self._bytes > self._max_bytes:
                _, removed_size = self._events.popleft()
                self._bytes -= removed_size
            self._condition.notify_all()
            return event

    def latest_id(self) -> int:
        with self._condition:
            return self._sequence

    def oldest_id(self) -> int | None:
        with self._condition:
            return self._events[0][0]["event_id"] if self._events else None

    def stats(self) -> dict[str, int]:
        with self._condition:
            return {
                "latest_id": self._sequence,
                "oldest_id": self._events[0][0]["event_id"] if self._events else 0,
                "retained_events": len(self._events),
                "retained_bytes": self._bytes,
                "max_events": self._max_events,
                "max_bytes": self._max_bytes,
                "max_event_bytes": self._max_event_bytes,
            }

    def _after_locked(self, sequence: int, limit: int | None) -> list[dict[str, Any]]:
        events = [event for event, _ in self._events if event["event_id"] > sequence]
        if limit is not None:
            events = events[: max(1, min(limit, self._max_events))]
        return events

    def since(self, sequence: int = 0, limit: int | None = None) -> list[dict[str, Any]]:
        with self._condition:
            return self._after_locked(sequence, limit)

    def wait_since(
        self,
        sequence: int = 0,
        timeout: float = 25.0,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        with self._condition:
            events = self._after_locked(sequence, limit)
            if events:
                return events
            self._condition.wait(timeout=max(0.0, timeout))
            return self._after_locked(sequence, limit)
