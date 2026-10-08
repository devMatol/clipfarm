from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator


class EventManager:
    def __init__(self) -> None:
        # project_id -> set of asyncio.Queue
        self._listeners: dict[str, set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, project_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            if project_id not in self._listeners:
                self._listeners[project_id] = set()
            self._listeners[project_id].add(queue)
        return queue

    async def unsubscribe(self, project_id: str, queue: asyncio.Queue) -> None:
        async with self._lock:
            if project_id in self._listeners:
                self._listeners[project_id].discard(queue)
                if not self._listeners[project_id]:
                    del self._listeners[project_id]

    async def publish(self, project_id: str, data: dict) -> None:
        payload = json.dumps(data)
        async with self._lock:
            queues = list(self._listeners.get(project_id, []))
        for q in queues:
            await q.put(payload)

    def publish_sync(self, project_id: str, data: dict) -> None:
        """Call from synchronous code (e.g. worker thread or callback)."""
        try:
            loop = asyncio.get_running_loop()
            asyncio.run_coroutine_threadsafe(self.publish(project_id, data), loop)
        except RuntimeError:
            pass


event_manager = EventManager()


async def event_generator(project_id: str) -> AsyncGenerator[dict, None]:
    queue = await event_manager.subscribe(project_id)
    try:
        while True:
            try:
                # Wait for next event or heartbeat
                payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                yield {"event": "progress", "data": payload}
            except asyncio.TimeoutError:
                # Send periodic heartbeat
                yield {"event": "ping", "data": "keep-alive"}
    finally:
        await event_manager.unsubscribe(project_id, queue)
