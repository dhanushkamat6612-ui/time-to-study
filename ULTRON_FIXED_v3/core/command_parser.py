import re

WEBSITES = {"youtube": "https://www.youtube.com", "github": "https://github.com",
            "gmail": "https://mail.google.com", "chatgpt": "https://chat.openai.com",
            "reddit": "https://reddit.com", "twitter": "https://x.com",
            "stackoverflow": "https://stackoverflow.com", "netflix": "https://netflix.com"}

APP_WORDS = ["chrome", "edge", "firefox", "vscode", "vs code", "code", "notepad", "spotify",
             "discord", "steam", "terminal", "powershell", "cmd", "word", "excel", "explorer",
             "calculator", "task manager", "slack", "obs", "postman", "figma"]


def _split_tasks(text):
    text = re.sub(r"\bthen\b", ",", text, flags=re.I)
    parts = re.split(r",| and then |;", text)
    return [p.strip() for p in parts if p.strip()]


def parse(text, workflows=None):
    """Returns (steps, reply_hint) or (None, None) if the LLM should handle it."""
    t = text.lower().strip()
    steps = []

    if workflows:
        for wname, wf in workflows.items():
            if wname in t or any(a in t for a in wf.get("aliases", [])):
                return [{"action": "workflow.run", "params": {"name": wname}}], None

    # watchers: "tell me when cpu reaches 90" / "let me know if ram goes above 85"
    m = re.search(r"(?:tell me|notify me|let me know|alert me|warn me).{0,20}"
                  r"(cpu|ram|memory|gpu|disk).{0,25}?(\d{1,3})\s*%?", t)
    if m:
        metric = {"memory": "ram"}.get(m.group(1), m.group(1))
        sustain = 300 if "stays" in t or "for" in t else 0
        return [{"action": "monitor.watch",
                 "params": {"metric": metric, "op": ">=", "threshold": int(m.group(2)),
                            "sustain_seconds": sustain}}], None

    for chunk in _split_tasks(t):
        c = chunk.strip()
        if not c:
            continue
        if re.search(r"\b(monitor|watch|keep an eye)\b.*\b(computer|system|performance|cpu|ram)\b", c):
            steps.append({"action": "monitor.session", "params": {"enable": True, "label": "session"}}); continue
        if re.search(r"\bwhy\b.*\b(slow|lagging|laggy|freezing|stutter)", c) or "what's slowing" in c:
            steps.append({"action": "system.why_slow", "params": {}}); continue
        if re.search(r"(what|which).*(using|eating|hogging).*(cpu|processor)", c):
            steps.append({"action": "system.top_cpu", "params": {}}); continue
        if re.search(r"(what|which).*(using|eating).*(ram|memory)", c) or "how much ram" in c:
            steps.append({"action": "system.top_ram", "params": {}}); continue
        if "background" in c and ("running" in c or "show" in c or "what" in c):
            steps.append({"action": "system.background", "params": {}}); continue
        if re.search(r"\b(highest|peak|busiest)\b.*(cpu|usage)", c) or "when was my cpu" in c:
            steps.append({"action": "system.peak", "params": {"metric": "cpu", "minutes": 60}}); continue
        if re.search(r"(storage|disk|drive).*(space|free|full)", c):
            steps.append({"action": "system.storage", "params": {}}); continue
        if "network" in c or "internet speed" in c:
            steps.append({"action": "system.network", "params": {}}); continue
        if "gpu" in c or "graphics" in c:
            steps.append({"action": "system.gpu", "params": {}}); continue
        if re.search(r"summar|what.?s happening|status report|overview", c):
            steps.append({"action": "system.summary", "params": {}}); continue
        if re.search(r"(virus|malware|infected|suspicious|antivirus|defender|security)", c):
            if "scan" in c:
                steps.append({"action": "security.scan", "params": {"scan_type": "QuickScan"}})
            else:
                steps.append({"action": "security.status", "params": {}})
            continue
        m = re.search(r"create (?:a )?folder (?:called |named )?['\"]?([\w \-\.]+)['\"]?"
                      r"(?: (?:in|on|under) ['\"]?([\w:\\\/~\- ]+)['\"]?)?", c)
        if m:
            base = m.group(2) or "~/Desktop"
            steps.append({"action": "file.create_folder",
                          "params": {"path": base, "name": m.group(1).strip()}}); continue
        m = re.search(r"(?:open|launch|start|show)(?: my| the)? ([\w \-]+?) folder", c)
        if m:
            steps.append({"action": "file.open_folder", "params": {"path": m.group(1).strip()}}); continue
        m = re.search(r"(?:search|look up|google)(?: for)? (.+?)(?: on (\w+))?$", c)
        if m and ("search" in c or "google" in c or "look up" in c):
            engine = m.group(2) or ("youtube" if "youtube" in c else "google")
            q = m.group(1).replace("on youtube", "").strip()
            steps.append({"action": "browser.search", "params": {"query": q, "engine": engine}}); continue
        if re.search(r"\b(close|quit|kill|stop)\b", c):
            for app in APP_WORDS:
                if app in c:
                    steps.append({"action": "app.close", "params": {"name": app}}); break
            else:
                if "unnecessary" in c or "don't need" in c or "distracting" in c:
                    steps.append({"action": "system.top_ram", "params": {}})
            continue
        if re.search(r"\b(open|launch|start|run)\b", c):
            hit = False
            for site, url in WEBSITES.items():
                if site in c:
                    steps.append({"action": "browser.open_url", "params": {"url": url}}); hit = True; break
            if hit: continue
            for app in sorted(APP_WORDS, key=len, reverse=True):
                if app in c:
                    steps.append({"action": "app.open", "params": {"name": app}}); hit = True; break
            if hit: continue
            m = re.search(r"(?:open|launch|start|run)\s+(?:my\s+|the\s+)?([\w\.\- ]+)", c)
            if m:
                target = m.group(1).strip()
                if "." in target and " " not in target:
                    steps.append({"action": "browser.open_url", "params": {"url": target}})
                else:
                    steps.append({"action": "app.open", "params": {"name": target}})
            continue

    return (steps, None) if steps else (None, None)
