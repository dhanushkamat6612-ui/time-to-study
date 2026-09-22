import os, json, re


PLANNER_SYSTEM = """You are the reasoning layer of ULTRON, a desktop assistant running locally on the
user's Windows PC. You decide WHAT should happen; a separate control layer decides HOW, and a security
layer decides whether it is allowed.

Return ONLY JSON:
{"reply": "<short natural sentence, or empty if actions speak for themselves>",
 "steps": [{"action": "<name from catalog>", "params": {...}, "critical": false}],
 "clarify": "<question, only if the request is genuinely ambiguous>"}

Rules:
- Only use actions from the catalog. Never invent action names or parameters.
- Multi-part requests become multiple ordered steps.
- Never claim an action succeeded — you cannot see results at planning time. Results are reported later.
- If the user only wants information, use the relevant system.* query action; do not guess numbers.
- If nothing in the catalog can do it, return empty steps and explain the limitation in "reply".
- Keep language calm, concise, human. No theatrics, no robot speak."""


class AIEngine:
    def __init__(self, settings, registry, memory):
        self.s = settings["llm"]; self.registry = registry; self.memory = memory
        self.client = None; self.mode = "offline"
        if not self.s.get("enabled"):
            return
        key = os.environ.get(self.s.get("api_key_env", ""), "")
        if self.s["provider"] == "anthropic" and key:
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=key); self.mode = "anthropic"
            except Exception as e:
                print("[ai] anthropic unavailable:", e)
        elif self.s.get("openai_compatible_base_url"):
            self.mode = "openai"

    def available(self):
        return self.mode != "offline"

    def _context(self, monitor):
        cur = monitor.current()
        return {"cpu_percent": cur["cpu"]["percent"], "ram_percent": cur["ram"]["percent"],
                "top_cpu": [p["name"] for p in cur["top_cpu"][:3]],
                "memory": self.memory.context_for_ai()}

    def plan(self, text, monitor, history=None):
        if not self.available():
            return None
        catalog = json.dumps(self.registry.catalog(), separators=(",", ":"))
        ctx = json.dumps(self._context(monitor), separators=(",", ":"))
        user = f"ACTION CATALOG:\n{catalog}\n\nLIVE CONTEXT:\n{ctx}\n\nUSER SAID: {text}"
        try:
            if self.mode == "anthropic":
                msgs = [{"role": m["role"], "content": m["content"]} for m in (history or [])[-6:]]
                msgs.append({"role": "user", "content": user})
                r = self.client.messages.create(model=self.s["model"], max_tokens=1200,
                                                system=PLANNER_SYSTEM, messages=msgs)
                raw = "".join(b.text for b in r.content if b.type == "text")
            else:
                import httpx
                r = httpx.post(f"{self.s['openai_compatible_base_url']}/chat/completions",
                               json={"model": self.s["model"], "messages": [
                                   {"role": "system", "content": PLANNER_SYSTEM},
                                   {"role": "user", "content": user}], "temperature": 0.2},
                               timeout=60)
                raw = r.json()["choices"][0]["message"]["content"]
            m = re.search(r"\{.*\}", raw, re.S)
            return json.loads(m.group(0)) if m else None
        except Exception as e:
            print("[ai] planning failed:", e)
            return None

    def narrate(self, user_text, results):
        """Turn REAL results into natural language. Grounded strictly in the JSON."""
        if not self.available():
            return None
        sysmsg = ("You are ULTRON speaking to your user. Convert the execution results below into a calm, "
                  "natural reply of 1-4 sentences. Use plain human phrasing, not key=value dumps. "
                  "State failures honestly and never claim anything succeeded unless ok=true. "
                  "If a value is null or marked unavailable, say it is unavailable — never estimate. "
                  "No lists unless there are 3+ items worth listing. No emojis.")
        payload = json.dumps({"user_said": user_text, "results": results}, default=str)[:12000]
        try:
            if self.mode == "anthropic":
                r = self.client.messages.create(model=self.s["model"], max_tokens=700, system=sysmsg,
                                                messages=[{"role": "user", "content": payload}])
                return "".join(b.text for b in r.content if b.type == "text").strip()
            import httpx
            r = httpx.post(f"{self.s['openai_compatible_base_url']}/chat/completions",
                           json={"model": self.s["model"], "messages": [
                               {"role": "system", "content": sysmsg},
                               {"role": "user", "content": payload}], "temperature": 0.3}, timeout=45)
            return r.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            return None
