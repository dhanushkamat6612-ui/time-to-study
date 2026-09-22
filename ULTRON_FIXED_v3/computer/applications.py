import os, shutil, subprocess, glob, psutil, pathlib

ALIASES = {
    "chrome": ["chrome.exe", "Google Chrome"], "google chrome": ["chrome.exe"],
    "edge": ["msedge.exe"], "firefox": ["firefox.exe"],
    "vscode": ["Code.exe", "Visual Studio Code"], "vs code": ["Code.exe"],
    "code": ["Code.exe"], "visual studio code": ["Code.exe"],
    "notepad": ["notepad.exe"], "notepad++": ["notepad++.exe"],
    "explorer": ["explorer.exe"], "file explorer": ["explorer.exe"],
    "terminal": ["wt.exe", "Windows Terminal"], "cmd": ["cmd.exe"],
    "powershell": ["powershell.exe"], "spotify": ["Spotify.exe"],
    "discord": ["Discord.exe"], "steam": ["steam.exe"], "word": ["WINWORD.EXE"],
    "excel": ["EXCEL.EXE"], "calculator": ["calc.exe"], "task manager": ["taskmgr.exe"],
    "obs": ["obs64.exe"], "figma": ["Figma.exe"], "slack": ["slack.exe"],
    "postman": ["Postman.exe"], "docker": ["Docker Desktop.exe"],
}

START_MENUS = [
    os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
    os.path.expandvars(r"%AppData%\Microsoft\Windows\Start Menu\Programs"),
]


def _app_paths_registry(exe):
    try:
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                k = winreg.OpenKey(hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}")
                return winreg.QueryValue(k, None)
            except OSError:
                continue
    except ImportError:
        pass
    return None


def _start_menu_shortcut(term):
    term = term.lower()
    for root in START_MENUS:
        for lnk in glob.glob(os.path.join(root, "**", "*.lnk"), recursive=True):
            if term in os.path.basename(lnk)[:-4].lower():
                return lnk
    return None


def resolve(name: str):
    """Returns (target, how) or (None, None). Only reports what it actually found."""
    key = name.strip().lower()
    candidates = ALIASES.get(key, []) + [name, f"{key}.exe"]
    for cand in candidates:
        if cand.lower().endswith(".exe"):
            p = shutil.which(cand)
            if p: return p, "PATH"
            p = _app_paths_registry(cand)
            if p and os.path.exists(p): return p, "registry"
    lnk = _start_menu_shortcut(key)
    if lnk: return lnk, "start menu"
    for cand in candidates:
        if not cand.lower().endswith(".exe"):
            lnk = _start_menu_shortcut(cand)
            if lnk: return lnk, "start menu"
    return None, None


def is_running(name):
    base = os.path.basename(name).lower().replace(".lnk", ".exe")
    return [p.info["pid"] for p in psutil.process_iter(["name", "pid"])
            if (p.info["name"] or "").lower() == base]


def open_app(name: str, args: str = ""):
    target, how = resolve(name)
    if not target:
        return {"ok": False,
                "detail": f"I couldn't find an application called '{name}' in PATH, the registry, "
                          f"or the Start Menu. You can add it to memory with its full path and I'll remember it."}
    already = is_running(target)
    try:
        if target.lower().endswith(".lnk"):
            os.startfile(target)
        else:
            subprocess.Popen([target] + (args.split() if args else ""),
                             creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
        return {"ok": True, "detail": f"Launched {os.path.basename(target)}",
                "data": {"path": target, "found_via": how, "was_already_running": bool(already)}}
    except Exception as e:
        return {"ok": False, "detail": f"Launch of '{name}' failed: {e}"}


def close_app(name: str, force: bool = False, protected=()):
    base = name.lower().replace(".exe", "")
    if f"{base}.exe" in [p.lower() for p in protected]:
        return {"ok": False, "detail": f"{name} is a protected system process. I won't close it."}
    killed, failed = [], []
    for p in psutil.process_iter(["name", "pid"]):
        n = (p.info["name"] or "").lower()
        if n == f"{base}.exe" or n == base:
            try:
                p.kill() if force else p.terminate()
                killed.append(p.info["pid"])
            except Exception as e:
                failed.append(f"pid {p.info['pid']}: {e}")
    psutil.wait_procs([psutil.Process(k) for k in killed if psutil.pid_exists(k)], timeout=3)
    if not killed and not failed:
        return {"ok": False, "detail": f"{name} does not appear to be running."}
    return {"ok": not failed, "detail": f"Closed {len(killed)} {name} process(es)."
            + (f" {len(failed)} could not be closed." if failed else ""),
            "data": {"killed": killed, "failed": failed}}
