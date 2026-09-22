import threading, time
from collections import deque
from monitoring import cpu, ram, gpu, storage, network, processes


class SystemMonitor:
    def __init__(self, bus, interval=2, history_minutes=60):
        self.bus = bus
        self.interval = interval
        self.samples = deque(maxlen=int(history_minutes * 60 / max(interval, 1)))
        self._latest = {}
        self._subscribers = []          # callables receiving each sample (watchers)
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        processes.sample(force=True)    # prime cpu_percent counters
        cpu.snapshot()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="ultron-monitor")
        self._thread.start()

    def stop(self):
        self._stop.set()

    def on_sample(self, fn):
        self._subscribers.append(fn)

    def _loop(self):
        while not self._stop.is_set():
            try:
                s = self._collect()
                self.samples.append(s)
                self._latest = s
                for fn in list(self._subscribers):
                    try: fn(s)
                    except Exception: pass
            except Exception as e:
                print("[monitor]", e)
            self._stop.wait(self.interval)

    def _collect(self):
        c = cpu.snapshot(); r = ram.snapshot()
        top = processes.grouped()
        return {"ts": time.time(), "cpu": c, "ram": r, "gpu": gpu.snapshot(),
                "storage": storage.snapshot(), "network": network.snapshot(),
                "process_count": len(processes.sample()),
                "top_cpu": top[:5],
                "top_ram": sorted(top, key=lambda x: x["ram_mb"], reverse=True)[:5]}

    # ---- query API used by actions -------------------------------------
    def current(self):
        return self._latest or self._collect()

    def window(self, minutes):
        cutoff = time.time() - minutes * 60
        return [s for s in self.samples if s["ts"] >= cutoff]

    def series(self, metric="cpu", minutes=10):
        pick = (lambda s: s["cpu"]["percent"]) if metric == "cpu" else (lambda s: s["ram"]["percent"])
        return [round(pick(s), 1) for s in self.window(minutes)]

    def peak(self, metric="cpu", minutes=60):
        w = self.window(minutes)
        if not w:
            return {"available": False,
                    "reason": f"I have only been monitoring for {self.uptime_minutes():.0f} minutes."}
        pick = (lambda s: s["cpu"]["percent"]) if metric == "cpu" else (lambda s: s["ram"]["percent"])
        best = max(w, key=pick)
        return {"available": True, "value": round(pick(best), 1), "ts": best["ts"],
                "minutes_ago": round((time.time() - best["ts"]) / 60, 1),
                "top_at_peak": best["top_cpu"][:3] if metric == "cpu" else best["top_ram"][:3],
                "average": round(sum(pick(s) for s in w) / len(w), 1)}

    def sustained(self, metric, threshold, seconds):
        w = self.window(seconds / 60)
        if not w or (w[-1]["ts"] - w[0]["ts"]) < seconds * 0.8:
            return False
        pick = (lambda s: s["cpu"]["percent"]) if metric == "cpu" else (lambda s: s["ram"]["percent"])
        return all(pick(s) >= threshold for s in w)

    def uptime_minutes(self):
        return (self.samples[-1]["ts"] - self.samples[0]["ts"]) / 60 if len(self.samples) > 1 else 0
