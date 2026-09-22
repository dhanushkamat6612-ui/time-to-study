import json, pathlib

LEVEL_NAMES = {1: "safe automation", 2: "confirmation required", 3: "high risk"}


class PermissionEngine:
    def __init__(self, config_path, settings):
        self.path = pathlib.Path(config_path)
        self.cfg = json.loads(self.path.read_text())
        self.settings = settings
        self.session_grants = set()      # "always allow this action this session"

    def level(self, action):
        return self.cfg["levels"].get(action, self.cfg["default_level"])

    def evaluate(self, action, params=None):
        if action in self.cfg.get("never_allowed", []):
            return {"decision": "deny", "level": 3,
                    "reason": "This action is permanently blocked by ULTRON's security policy."}
        lvl = self.level(action)
        if lvl == 1 and self.settings["security"].get("auto_approve_level1", True):
            return {"decision": "auto", "level": 1}
        if lvl == 3:
            if action == "win.run_powershell" and not self.settings["security"].get("enable_shell"):
                return {"decision": "deny", "level": 3,
                        "reason": "Arbitrary shell execution is disabled in settings.json."}
            return {"decision": "confirm", "level": 3,
                    "reason": "High-risk or irreversible action — explicit confirmation required."}
        if action in self.session_grants:
            return {"decision": "auto", "level": lvl, "reason": "Approved earlier this session."}
        return {"decision": "confirm", "level": lvl,
                "reason": "This changes your system, so I need your approval."}

    def grant_session(self, action):
        self.session_grants.add(action)

    def set_level(self, action, level):
        self.cfg["levels"][action] = int(level)
        self.path.write_text(json.dumps(self.cfg, indent=2))
