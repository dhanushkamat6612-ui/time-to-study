import json, pathlib, time, threading

DEFAULT = {"apps": {}, "folders": {}, "preferences": {}, "facts": [], "workflow_usage": {}}


class Memory:
    def __init__(self, path="config/memory.json"):
        self.path = pathlib.Path(path)
        self.lock = threading.Lock()
        self.data = json.loads(self.path.read_text()) if self.path.exists() else dict(DEFAULT)
        for k, v in DEFAULT.items():
            self.data.setdefault(k, v if not isinstance(v, (dict, list)) else type(v)())
        self._save()

    def _save(self):
        self.path.parent.mkdir(exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2))

    def note_app(self, name, path=None):
        with self.lock:
            e = self.data["apps"].setdefault(name.lower(), {"count": 0, "path": path})
            e["count"] += 1; e["last_used"] = time.time()
            if path: e["path"] = path
            self._save()

    def note_folder(self, path):
        with self.lock:
            e = self.data["folders"].setdefault(path, {"count": 0})
            e["count"] += 1; e["last_used"] = time.time(); self._save()

    def remember_fact(self, text, tag="general"):
        with self.lock:
            self.data["facts"].append({"id": str(int(time.time() * 1000))[-8:], "text": text,
                                       "tag": tag, "ts": time.time()})
            self._save()
        return {"ok": True, "detail": f"Remembered: {text}"}

    def forget(self, fact_id=None, text=None):
        with self.lock:
            before = len(self.data["facts"])
            self.data["facts"] = [f for f in self.data["facts"]
                                  if f["id"] != fact_id and (not text or text.lower() not in f["text"].lower())]
            self._save()
        n = before - len(self.data["facts"])
        return {"ok": n > 0, "detail": f"Removed {n} memory entr{'y' if n == 1 else 'ies'}."
                if n else "I didn't find that in memory."}

    def set_preference(self, key, value):
        with self.lock:
            self.data["preferences"][key] = value; self._save()
        return {"ok": True, "detail": f"Preference '{key}' set to {value}."}

    def favourites(self, n=5):
        apps = sorted(self.data["apps"].items(), key=lambda kv: -kv[1]["count"])[:n]
        folders = sorted(self.data["folders"].items(), key=lambda kv: -kv[1]["count"])[:n]
        return {"apps": [a for a, _ in apps], "folders": [f for f, _ in folders]}

    def context_for_ai(self):
        fav = self.favourites()
        return {"frequent_apps": fav["apps"], "frequent_folders": fav["folders"],
                "preferences": self.data["preferences"],
                "remembered_facts": [f["text"] for f in self.data["facts"][-15:]]}

    def export(self):
        return self.data
