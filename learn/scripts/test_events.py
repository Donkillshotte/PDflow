"""Acceptance tests for bounded agent event replay and payload retention."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "learn"))

from pdflow_agent.events import EventBus  # noqa: E402


def main() -> None:
    bus = EventBus(max_events=8, max_bytes=4096, max_event_bytes=512)
    for index in range(40):
        bus.emit("tool.log", {"chunk": "x" * 3000, "index": index})

    stats = bus.stats()
    assert stats["latest_id"] == 40, stats
    assert stats["retained_events"] <= 8, stats
    assert stats["retained_bytes"] <= 4096, stats
    retained = bus.since(0)
    assert len(retained) <= 8, retained
    assert all(event["payload"].get("truncated") is True for event in retained)

    latest = bus.latest_id()
    assert bus.since(latest) == []
    bus.emit("artifact.changed", {"artifact_id": "artifact-test"})
    assert [event["type"] for event in bus.wait_since(latest, timeout=0)] == [
        "artifact.changed"
    ]

    limited = bus.since(0, limit=2)
    assert len(limited) == 2, limited
    assert bus.oldest_id() == retained[0]["event_id"] or bus.oldest_id() > 0
    print("OK test_events")


if __name__ == "__main__":
    main()
