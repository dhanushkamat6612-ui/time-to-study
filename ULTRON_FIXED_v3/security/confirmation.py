import asyncio, uuid


class ConfirmationBroker:
    def __init__(self, bus):
        self.bus = bus
        self.pending = {}

    async def request(self, action, params, level, reason, summary, timeout=180):
        cid = uuid.uuid4().hex[:10]
        fut = asyncio.get_event_loop().create_future()
        self.pending[cid] = fut
        await self.bus.publish({"type": "confirm_request", "id": cid, "action": action,
                                "params": params, "level": level, "reason": reason,
                                "summary": summary})
        try:
            return await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            await self.bus.publish({"type": "confirm_expired", "id": cid})
            return {"approved": False, "reason": "no response"}
        finally:
            self.pending.pop(cid, None)

    def resolve(self, cid, approved, always=False):
        fut = self.pending.get(cid)
        if fut and not fut.done():
            fut.set_result({"approved": approved, "always": always})
            return True
        return False
