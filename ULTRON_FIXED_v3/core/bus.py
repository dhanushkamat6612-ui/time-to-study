import asyncio, time
from collections import deque


class EventBus:
    def __init__(self):
        self._subs = set()
        self._loop = None
        self.history = deque(maxlen=120)

    def bind_loop(self, loop): self._loop = loop
    def subscribe(self, q): self._subs.add(q)
    def unsubscribe(self, q): self._subs.discard(q)

    async def publish(self, event):
        event.setdefault("ts", time.time())
        if event.get("type") in ("log", "notification", "message"):
            self.history.append(event)
        for q in list(self._subs):
            try: q.put_nowait(event)
            except asyncio.QueueFull: pass

    def publish_threadsafe(self, event):
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.publish(event), self._loop)
