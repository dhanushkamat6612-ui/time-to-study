import time


class Notifier:
    def __init__(self, bus, use_toast=True):
        self.bus, self.use_toast = bus, use_toast
        self.log = []

    def push(self, level, text, data=None, toast=None):
        item = {"type": "notification", "level": level, "text": text, "data": data, "ts": time.time()}
        self.log.append(item); self.log = self.log[-200:]
        self.bus.publish_threadsafe(item)
        if (toast if toast is not None else self.use_toast) and level in ("alert", "warning", "critical"):
            try:
                from computer.windows import toast as win_toast
                win_toast("ULTRON", text[:160])
            except Exception:
                pass
        return item

    def event(self, text, kind="info"):
        self.bus.publish_threadsafe({"type": "log", "level": kind, "text": text, "ts": time.time()})
