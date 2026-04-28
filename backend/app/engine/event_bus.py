"""In-process pub/sub event bus.

Used to broadcast sensor readings, AI detections, incidents, and dispatch
state changes to subscribers (WebSocket hub, alert manager, audit logger).
Designed to be swappable for Redis pub/sub in production by implementing the
same publish/subscribe interface.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any


class EventBus:
    def __init__(self, max_queue: int = 1024) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._max_queue = max_queue

    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        # Always include topic for fan-in subscribers.
        message = {"topic": topic, **payload}
        for queue in list(self._subscribers.get(topic, set())) + list(self._subscribers.get("*", set())):
            if queue.qsize() >= self._max_queue:
                # drop oldest to avoid unbounded growth
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            await queue.put(message)

    @asynccontextmanager
    async def subscribe(self, topic: str = "*") -> AsyncIterator[asyncio.Queue]:
        q: asyncio.Queue = asyncio.Queue(maxsize=self._max_queue)
        self._subscribers[topic].add(q)
        try:
            yield q
        finally:
            self._subscribers[topic].discard(q)


bus = EventBus()
