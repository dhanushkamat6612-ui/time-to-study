import time, uuid


class Watcher:
    def __init__(self, metric, op, threshold, sustain_seconds=0, message=None, once=True, label=None):
        self.id = uuid.uuid4().hex[:8]
        self.metric, self.op, self.threshold = metric, op, float(threshold)
        self.sustain = sustain_seconds
        self.message = message
        self.once = once
        self.label = label or f"{metric} {op} {threshold}"
        self.created = time.time()
        self.since = None
        self.fired_at = None
        self.active = True

    def value(self, sample):
        m = self.metric
        if m == "cpu": return sample["cpu"]["percent"]
        if m == "ram": return sample["ram"]["percent"]
        if m == "gpu": return sample["gpu"].get("usage_percent") if sample["gpu"]["available"] else None
        if m == "disk_free":
            return min((d["free_gb"] for d in sample["storage"]["disks"]), default=None)
        if m == "download": return sample["network"]["download_mb_s"]
        return None

    def check(self, sample):
        v = self.value(sample)
        if v is None or not self.active:
            return None
        hit = v >= self.threshold if self.op == ">=" else v <= self.threshold
        if not hit:
            self.since = None
            return None
        self.since = self.since or time.time()
        if time.time() - self.since < self.sustain:
            return None
        if self.once:
            self.active = False
        self.fired_at = time.time()
        return {"watcher": self.label, "value": round(v, 1), "metric": self.metric,
                "threshold": self.threshold, "sustained_seconds": int(time.time() - self.since),
                "message": self.message, "top": sample["top_cpu"][:2] if self.metric == "cpu"
                           else sample["top_ram"][:2]}

    def as_dict(self):
        return {"id": self.id, "label": self.label, "metric": self.metric, "op": self.op,
                "threshold": self.threshold, "sustain": self.sustain, "active": self.active,
                "fired_at": self.fired_at}


class WatcherEngine:
    """Also owns the built-in proactive rules."""
    def __init__(self, monitor, notifier, settings):
        self.monitor, self.notifier, self.settings = monitor, notifier, settings
        self.watchers = []
        self._builtin_state = {}
        self.session = None
        monitor.on_sample(self._on_sample)

    def add(self, **kw):
        w = Watcher(**kw); self.watchers.append(w); return w

    def cancel(self, wid=None):
        if wid is None:
            n = len(self.watchers); self.watchers.clear(); return n
        before = len(self.watchers)
        self.watchers = [w for w in self.watchers if w.id != wid]
        return before - len(self.watchers)

    def list(self):
        return [w.as_dict() for w in self.watchers]

    def _on_sample(self, sample):
        for w in list(self.watchers):
            hit = w.check(sample)
            if hit:
                text = w.message or self._phrase(hit)
                self.notifier.push("alert", text, data=hit)
        if self.settings["proactive"].get("enabled", True):
            self._builtin(sample)

    def _phrase(self, hit):
        who = f" {hit['top'][0]['name']} is using the most." if hit.get("top") else ""
        return (f"{hit['metric'].upper()} reached {hit['value']}% "
                f"(you asked me to watch for {hit['op'] if 'op' in hit else ''}{hit['threshold']}%).{who}")

    def _fire_once(self, key, cooldown, text, data=None, level="warning"):
        last = self._builtin_state.get(key, 0)
        if time.time() - last < cooldown:
            return
        self._builtin_state[key] = time.time()
        self.notifier.push(level, text, data=data)

    def _builtin(self, s):
        p = self.settings["proactive"]
        if self.monitor.sustained("cpu", p["cpu_threshold"], p["cpu_sustain_seconds"]):
            top = s["top_cpu"][0] if s["top_cpu"] else None
            self._fire_once("cpu", 900,
                f"Your CPU has stayed above {p['cpu_threshold']}% for the last "
                f"{p['cpu_sustain_seconds']//60} minutes."
                + (f" {top['name']} is using {top['cpu']}% of it. Would you like me to investigate?"
                   if top else ""), data={"top": s["top_cpu"][:3]})
        if self.monitor.sustained("ram", p["ram_threshold"], p["ram_sustain_seconds"]):
            top = s["top_ram"][0] if s["top_ram"] else None
            self._fire_once("ram", 900,
                f"Memory has been above {p['ram_threshold']}% for several minutes."
                + (f" {top['name']} is holding {top['ram_mb']/1024:.1f}GB." if top else ""))
        for d in s["storage"]["disks"]:
            if d["free_gb"] < p["disk_free_warn_gb"]:
                self._fire_once(f"disk{d['mount']}", 3600 * 6,
                    f"Drive {d['mount']} is running low — {d['free_gb']}GB free of {d['total_gb']}GB. "
                    f"I can show you the largest folders if that helps.")
        if p.get("check_unresponsive"):
            from monitoring.processes import unresponsive
            for h in unresponsive():
                self._fire_once(f"hang{h['pid']}", 600,
                    f"{h['name']} has stopped responding. I can close it if you want — that would "
                    f"lose anything unsaved.", data=h, level="warning")
