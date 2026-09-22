import json, asyncio, pathlib, os, time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

ROOT = pathlib.Path(__file__).parent.parent
CONFIG = json.loads((ROOT / "config" / "settings.json").read_text())

from core.bus import EventBus
from core.memory import Memory
from core.notifications import Notifier
from core import narrator as narrator_mod
from core.ai_engine import AIEngine
from core.command_parser import parse as parse_command
from core.task_manager import TaskManager
from computer.registry import REGISTRY
from computer import applications, browser, windows
from computer.files import FileController
from computer import processes as proc_ctl
from monitoring.monitor import SystemMonitor
from monitoring import processes as pmon, analyzer
from security.permissions import PermissionEngine
from security.confirmation import ConfirmationBroker
from security import windows_security as winsec
from automation.watchers import WatcherEngine
from automation.workflows import WorkflowEngine

bus = EventBus()
memory = Memory(ROOT / "config" / "memory.json")
notifier = Notifier(bus)
monitor = SystemMonitor(bus, CONFIG["monitor"]["interval_seconds"], CONFIG["monitor"]["history_minutes"])
perm = PermissionEngine(ROOT / "config" / "permissions.json", CONFIG)
confirmations = ConfirmationBroker(bus)
files = FileController(CONFIG["security"]["allowed_roots"])
ai = AIEngine(CONFIG, REGISTRY, memory)
task_manager = TaskManager(REGISTRY, perm, confirmations, bus, notifier, narrator_mod, ai, memory)
watchers = WatcherEngine(monitor, notifier, CONFIG)
workflows = WorkflowEngine(ROOT / "config" / "workflows.json", task_manager)
PROTECTED = CONFIG["security"]["protected_processes"]

R = REGISTRY.register

# ---------------- applications / files / browser ----------------
@R("app.open", "Open/launch an application by name", {"name": "application name"})
def _app_open(name, args=""):
    res = applications.open_app(name, args)
    if res["ok"]:
        memory.note_app(name, res["data"]["path"])
    return res

@R("app.close", "Close a running application", {"name": "application name"})
def _app_close(name, force=False):
    return applications.close_app(name, force, PROTECTED)

@R("app.list_running", "List running applications and their resource use", {})
def _app_list(limit=15):
    return proc_ctl.list_running(limit)

@R("process.kill", "Terminate a process by PID", {"pid": "process id"})
def _kill(pid, force=False):
    return proc_ctl.kill_pid(int(pid), force, PROTECTED)

@R("file.create_folder", "Create a folder", {"path": "parent path", "name": "folder name"})
def _mkdir(path="~/Desktop", name=None):
    r = files.create_folder(path, name)
    if r["ok"]: memory.note_folder(r["data"]["path"])
    return r

@R("file.create_file", "Create a text file", {"path": "full path", "content": "text"})
def _mkfile(path, content=""):
    return files.create_file(path, content)

@R("file.open_folder", "Open a folder in File Explorer", {"path": "folder path or shortcut like 'downloads'"})
def _openfolder(path):
    shortcuts = {"downloads": "~/Downloads", "documents": "~/Documents", "desktop": "~/Desktop",
                 "project": "~/Projects", "projects": "~/Projects", "pictures": "~/Pictures"}
    key = str(path).strip().lower()
    resolved = shortcuts.get(key, path)
    if key in memory.data["folders"]:
        resolved = key
    r = files.open_folder(resolved)
    if r["ok"]: memory.note_folder(r["data"]["path"])
    return r

@R("file.list", "List the contents of a folder", {"path": "folder path"})
def _ls(path, limit=60): return files.list_dir(path, limit)

@R("file.search", "Search for files by name", {"pattern": "text", "root": "folder"})
def _find(pattern, root="~"): return files.search(pattern, root)

@R("file.move", "Move a file or folder", {"src": "source", "dst": "destination"})
def _mv(src, dst): return files.move(src, dst)

@R("file.organize", "Sort loose files in a folder into type folders", {"path": "folder"})
def _org(path): return files.organize(path)

@R("file.delete", "Send a file or folder to the Recycle Bin", {"path": "path"})
def _rm(path): return files.delete(path)

@R("browser.open_url", "Open a website", {"url": "url"})
def _url(url): return browser.open_url(url)

@R("browser.search", "Search the web", {"query": "text", "engine": "google|youtube|github|stackoverflow"})
def _search(query, engine="google"): return browser.search(query, engine)

@R("browser.open_tabs", "Open several websites at once", {"urls": "list of urls"})
def _tabs(urls): return browser.open_tabs(urls if isinstance(urls, list) else [urls])

@R("browser.list_tabs", "List open Chrome tabs (requires debug port)", {})
def _ltabs(): return browser.list_tabs()

@R("browser.close_tab", "Close a Chrome tab", {"tab_id": "tab id"})
def _ctab(tab_id): return browser.close_tab(tab_id)

# ---------------- system queries ----------------
@R("system.metrics", "Current CPU/RAM/GPU/disk/network snapshot", {})
def _metrics(): return {"ok": True, "detail": "Live metrics.", "data": monitor.current()}

@R("system.top_cpu", "What is using the CPU right now", {})
def _topcpu(n=5):
    cur = monitor.current()
    return {"ok": True, "detail": "Top CPU consumers.",
            "data": {"cpu_percent": cur["cpu"]["percent"], "top": pmon.top_cpu(n)}}

@R("system.top_ram", "What is using memory right now", {})
def _topram(n=5):
    r = monitor.current()["ram"]
    return {"ok": True, "detail": "Top memory consumers.", "data": {**r, "top": pmon.top_ram(n)}}

@R("system.why_slow", "Diagnose why the computer feels slow", {})
def _why(): return {"ok": True, "detail": "Diagnosis complete.", "data": analyzer.diagnose(monitor)}

@R("system.peak", "Highest recorded usage in the monitored window", {"metric": "cpu|ram", "minutes": "int"})
def _peak(metric="cpu", minutes=60):
    return {"ok": True, "detail": "Peak lookup.", "data": monitor.peak(metric, int(minutes))}

@R("system.background", "List background processes consuming resources", {})
def _bg(): return {"ok": True, "detail": "Background processes.", "data": {"processes": pmon.background()}}

@R("system.storage", "Disk space and activity", {})
def _st(): return {"ok": True, "detail": "Storage status.", "data": monitor.current()["storage"]}

@R("system.network", "Network speed and connectivity", {})
def _net(): return {"ok": True, "detail": "Network status.", "data": monitor.current()["network"]}

@R("system.gpu", "GPU usage, memory and temperature if available", {})
def _gpu(): return {"ok": True, "detail": "GPU status.", "data": monitor.current()["gpu"]}

@R("system.info", "OS, hardware and uptime information", {})
def _info(): return windows.system_info()

@R("system.summary", "Overall summary of what the computer is doing", {})
def _sum():
    cur = monitor.current(); diag = analyzer.diagnose(monitor)
    return {"ok": True, "detail": "System summary.",
            "data": {"cpu": cur["cpu"]["percent"], "ram": cur["ram"], "top_cpu": cur["top_cpu"][:3],
                     "top_ram": cur["top_ram"][:3], "process_count": cur["process_count"],
                     "storage": cur["storage"]["disks"], "network": cur["network"],
                     "gpu": cur["gpu"], "findings": diag["findings"],
                     "monitored_minutes": round(monitor.uptime_minutes(), 1),
                     "active_watchers": watchers.list()}}

# ---------------- monitoring / watchers ----------------
@R("monitor.watch", "Watch a metric and notify when it crosses a threshold",
   {"metric": "cpu|ram|gpu|disk_free|download", "op": ">=|<=", "threshold": "number",
    "sustain_seconds": "seconds it must stay there", "message": "optional custom message"})
def _watch(metric="cpu", op=">=", threshold=90, sustain_seconds=0, message=None):
    w = watchers.add(metric=metric, op=op, threshold=threshold,
                     sustain_seconds=int(sustain_seconds or 0), message=message)
    return {"ok": True, "detail": f"Watching {metric} {op} {threshold}.", "data": w.as_dict() |
            {"metric": metric, "threshold": float(threshold), "sustain_seconds": int(sustain_seconds or 0)}}

@R("monitor.list", "List active monitors", {})
def _wl(): return {"ok": True, "detail": f"{len(watchers.list())} active monitors.",
                   "data": {"watchers": watchers.list()}}

@R("monitor.cancel", "Stop a monitor", {"id": "watcher id, omit for all"})
def _wc(id=None):
    n = watchers.cancel(id); return {"ok": n > 0, "detail": f"Stopped {n} monitor(s)."}

@R("monitor.session", "Start or stop proactive supervision of the whole machine",
   {"enable": "bool", "label": "session name"})
def _sess(enable=True, label="session"):
    CONFIG["proactive"]["enabled"] = bool(enable)
    watchers.session = {"label": label, "started": time.time()} if enable else None
    return {"ok": True, "data": {"label": label, "enabled": bool(enable)},
            "detail": (f"Supervising your system ({label}). I'll speak up if something looks wrong."
                       if enable else "Stopped proactive supervision.")}

# ---------------- memory ----------------
@R("memory.remember", "Remember something the user asked you to remember", {"text": "fact", "tag": "category"})
def _rem(text, tag="general"): return memory.remember_fact(text, tag)

@R("memory.recall", "Recall what is remembered", {})
def _recall(): return {"ok": True, "detail": "Memory contents.", "data": memory.context_for_ai()}

@R("memory.list", "List all stored memory", {})
def _mlist(): return {"ok": True, "detail": "Full memory.", "data": memory.export()}

@R("memory.forget", "Delete a remembered item", {"text": "text to match", "fact_id": "id"})
def _forget(text=None, fact_id=None): return memory.forget(fact_id, text)

# ---------------- workflows ----------------
@R("workflow.list", "List saved workflows", {})
def _wfl(): return workflows.list()

@R("workflow.create", "Save a new reusable workflow", {"name": "name", "steps": "list of steps"})
def _wfc(name, steps, description="", aliases=None):
    return workflows.create(name, steps, description, aliases)

@R("workflow.delete", "Delete a workflow", {"name": "name"})
def _wfd(name): return workflows.delete(name)

# workflow.run is handled specially in handle_command (it expands into sub-steps)
@R("workflow.run", "Run a saved workflow", {"name": "workflow name"})
def _wfr(name):
    return {"ok": False, "detail": "internal: expanded before execution"}

# ---------------- security ----------------
@R("security.status", "Check Windows Security / antivirus status", {})
def _secstat(): return winsec.defender_status()

@R("security.threats", "List recent Defender threat detections", {})
def _secthreat(): return winsec.threats()

@R("security.scan", "Run a Windows Defender scan", {"scan_type": "QuickScan|FullScan"})
def _secscan(scan_type="QuickScan"): return winsec.start_scan(scan_type)

@R("security.inspect_process", "Investigate whether a process looks suspicious",
   {"name": "process name", "pid": "process id"})
def _secinspect(name=None, pid=None):
    return winsec.inspect_process(int(pid) if pid else None, name,
                                  os.environ.get(CONFIG.get("virustotal_api_key_env", ""), ""))

@R("security.quarantine", "Ask Windows Defender to remove detected threats", {})
def _secq(): return winsec.remove_threats()

@R("win.open_settings", "Open a Windows Settings page", {"page": "e.g. windowsdefender"})
def _wset(page="windowsdefender"): return windows.open_settings(page)

@R("win.empty_recycle_bin", "Empty the Recycle Bin", {})
def _werb(): return windows.empty_recycle_bin()

@R("notify.send", "Show a notification", {"text": "message"})
def _notif(text):
    notifier.push("info", text); return {"ok": True, "detail": "Notification shown."}

for name, spec in REGISTRY.actions.items():
    spec.level = perm.level(name)


# ---------------- command pipeline ----------------
async def handle_command(text):
    wf = workflows.match(text)
    steps, reply = (None, None)
    if wf:
        steps = [{"action": "workflow.run", "params": {"name": wf}}]
    else:
        plan = ai.plan(text, monitor, history=None) if ai.available() else None
        if plan and plan.get("clarify"):
            return plan["clarify"], []
        if plan and plan.get("steps") is not None:
            steps, reply = plan["steps"], plan.get("reply")
        else:
            steps, reply = parse_command(text, workflows.workflows)

    if not steps:
        if reply:
            return reply, []
        return ("I understood the words but I don't have a capability that matches that yet. "
                "I can open and close applications, inspect what's using your CPU, memory, GPU, disk "
                "and network, manage folders, run workflows, watch thresholds and check Windows Security."), []

    expanded = []
    for s in steps:
        if s.get("action") == "workflow.run":
            wname = s["params"].get("name", "")
            sub = workflows.steps_for(wname)
            if sub:
                notifier.event(f"Running workflow '{wname}' ({len(sub)} steps)")
                expanded.extend(sub)
            else:
                expanded.append({"action": "notify.send",
                                 "params": {"text": f"No workflow named '{wname}'."}})
        else:
            expanded.append(s)

    return await task_manager.run_plan(expanded, text)


# ---------------- FastAPI ----------------
def build_app():
    app = FastAPI(title="ULTRON")

    @app.on_event("startup")
    async def _start():
        bus.bind_loop(asyncio.get_running_loop())
        monitor.start()
        notifier.event("ULTRON core online. Monitoring layer active.")
        asyncio.create_task(_broadcast_metrics())

    async def _broadcast_metrics():
        while True:
            try:
                cur = monitor.current()
                await bus.publish({"type": "metrics", "data": {
                    "cpu": cur["cpu"], "ram": cur["ram"], "gpu": cur["gpu"],
                    "storage": cur["storage"], "network": cur["network"],
                    "process_count": cur["process_count"], "top_cpu": cur["top_cpu"][:4],
                    "top_ram": cur["top_ram"][:4],
                    "cpu_series": monitor.series("cpu", 5)[-40:],
                    "watchers": watchers.list(),
                    "proactive": CONFIG["proactive"]["enabled"],
                    "ai_mode": ai.mode}})
            except Exception as e:
                print("[broadcast]", e)
            await asyncio.sleep(1.5)

    @app.get("/")
    def index():
        return FileResponse(ROOT / "ui" / "index.html")

    app.mount("/static", StaticFiles(directory=ROOT / "ui"), name="static")

    @app.get("/api/memory")
    def get_mem(): return memory.export()

    @app.delete("/api/memory/{fact_id}")
    def del_mem(fact_id: str): return memory.forget(fact_id=fact_id)

    @app.get("/api/history")
    def get_hist():
        return JSONResponse([{"ts": h["ts"], "user": h["user"], "reply": h["reply"],
                              "actions": [r["action"] for r in h["results"]]}
                             for h in task_manager.history[-40:]])

    @app.get("/api/capabilities")
    def caps(): return REGISTRY.catalog()

    @app.websocket("/ws")
    async def ws(sock: WebSocket):
        await sock.accept()
        q = asyncio.Queue(maxsize=400)
        bus.subscribe(q)
        await sock.send_json({"type": "hello", "ai_mode": ai.mode,
                              "workflows": list(workflows.workflows.keys()),
                              "capabilities": len(REGISTRY.actions)})
        for item in list(bus.history)[-15:]:
            await sock.send_json(item)

        async def pump():
            while True:
                await sock.send_json(await q.get())

        pumper = asyncio.create_task(pump())
        try:
            while True:
                msg = await sock.receive_json()
                kind = msg.get("type")
                if kind == "command":
                    text = msg.get("text", "").strip()
                    if not text:
                        continue
                    await bus.publish({"type": "message", "role": "user", "text": text})
                    await bus.publish({"type": "thinking", "state": True})
                    try:
                        reply, _ = await handle_command(text)
                    except Exception as e:
                        reply = f"Something went wrong while handling that: {e}"
                    await bus.publish({"type": "thinking", "state": False})
                    await bus.publish({"type": "message", "role": "ultron", "text": reply})
                elif kind == "confirm":
                    confirmations.resolve(msg["id"], bool(msg.get("approved")), bool(msg.get("always")))
                elif kind == "quick":
                    await bus.publish({"type": "message", "role": "user", "text": msg["text"]})
                    reply, _ = await handle_command(msg["text"])
                    await bus.publish({"type": "message", "role": "ultron", "text": reply})
        except WebSocketDisconnect:
            pass
        finally:
            pumper.cancel(); bus.unsubscribe(q)

    return app
