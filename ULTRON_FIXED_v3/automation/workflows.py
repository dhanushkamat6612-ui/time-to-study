import json, pathlib


class WorkflowEngine:
    def __init__(self, path, task_manager):
        self.path = pathlib.Path(path)
        self.tm = task_manager
        self.workflows = json.loads(self.path.read_text()) if self.path.exists() else {}

    def save(self):
        self.path.write_text(json.dumps(self.workflows, indent=2))

    def match(self, text):
        t = text.lower()
        for name, wf in self.workflows.items():
            if name in t or any(a in t for a in wf.get("aliases", [])):
                return name
        return None

    def list(self):
        return {"ok": True, "detail": f"{len(self.workflows)} workflows available.",
                "data": {"workflows": [{"name": k, "description": v.get("description"),
                                        "steps": len(v["steps"])} for k, v in self.workflows.items()]}}

    def create(self, name, steps, description="", aliases=None):
        self.workflows[name.lower()] = {"description": description, "aliases": aliases or [],
                                        "steps": steps}
        self.save()
        return {"ok": True, "detail": f"Saved workflow '{name}' with {len(steps)} steps."}

    def delete(self, name):
        if self.workflows.pop(name.lower(), None) is None:
            return {"ok": False, "detail": f"No workflow called '{name}'."}
        self.save(); return {"ok": True, "detail": f"Deleted workflow '{name}'."}

    def steps_for(self, name):
        wf = self.workflows.get(name.lower())
        return wf["steps"] if wf else None
