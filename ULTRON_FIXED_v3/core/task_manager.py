import asyncio, time, uuid


class TaskManager:
    def __init__(self, registry, permissions, confirmations, bus, notifier, narrator, ai, memory):
        self.registry, self.perm, self.confirm = registry, permissions, confirmations
        self.bus, self.notifier, self.narrator, self.ai, self.memory = bus, notifier, narrator, ai, memory
        self.history = []

    async def run_plan(self, steps, user_text=""):
        plan_id = uuid.uuid4().hex[:8]
        results = []
        await self.bus.publish({"type": "plan_start", "id": plan_id, "count": len(steps)})

        for idx, step in enumerate(steps):
            action, params = step.get("action"), step.get("params", {}) or {}
            spec = self.registry.get(action)
            if not spec:
                results.append({"action": action, "params": params, "status": "error",
                                "result": {"ok": False, "detail": f"I don't have a '{action}' capability."}})
                continue

            verdict = self.perm.evaluate(action, params)
            await self.bus.publish({"type": "task_update", "id": plan_id, "index": idx,
                                    "action": action, "status": "checking", "level": verdict["level"]})

            if verdict["decision"] == "deny":
                results.append({"action": action, "params": params, "status": "denied",
                                "result": {"ok": False, "detail": verdict["reason"]}})
                continue

            if verdict["decision"] == "confirm":
                summary = f"{spec.description} — {params}" if params else spec.description
                ans = await self.confirm.request(action, params, verdict["level"],
                                                 verdict.get("reason", ""), summary)
                if not ans["approved"]:
                    results.append({"action": action, "params": params, "status": "denied",
                                    "result": {"ok": False,
                                               "detail": f"You declined this action ({ans.get('reason','denied')})."}})
                    continue
                if ans.get("always"):
                    self.perm.grant_session(action)

            await self.bus.publish({"type": "task_update", "id": plan_id, "index": idx,
                                    "action": action, "status": "running"})
            t0 = time.time()
            try:
                res = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: spec.handler(**params))
                if not isinstance(res, dict):
                    res = {"ok": True, "detail": str(res)}
            except TypeError as e:
                res = {"ok": False, "detail": f"I understood the request but the parameters were wrong: {e}"}
            except PermissionError as e:
                res = {"ok": False, "detail": str(e)}
            except Exception as e:
                res = {"ok": False, "detail": f"{type(e).__name__}: {e}"}

            res["elapsed"] = round(time.time() - t0, 2)
            results.append({"action": action, "params": params,
                            "status": "ok" if res.get("ok") else "failed", "result": res})
            self.notifier.event(f"{action} → {'ok' if res.get('ok') else 'failed'}: {res.get('detail','')[:110]}",
                                "info" if res.get("ok") else "warn")
            await self.bus.publish({"type": "task_update", "id": plan_id, "index": idx, "action": action,
                                    "status": results[-1]["status"], "detail": res.get("detail")})

            if step.get("critical") and not res.get("ok"):
                results.append({"action": "—", "status": "aborted",
                                "result": {"ok": False,
                                           "detail": "I stopped here because that step was required for the rest."}})
                break

        text = self.ai.narrate(user_text, results) if self.ai.available() else None
        if not text:
            text = self.narrator.summarize(user_text, results)
        self.history.append({"ts": time.time(), "user": user_text, "results": results, "reply": text})
        self.history = self.history[-100:]
        await self.bus.publish({"type": "plan_done", "id": plan_id, "results": results})
        return text, results
