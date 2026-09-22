import psutil, time, os
from collections import defaultdict

NCPU = psutil.cpu_count() or 1
_last_full, _cache = 0, []


def sample(force=False):
    """Per-process CPU normalised to whole-machine percentage."""
    global _last_full, _cache
    if not force and time.time() - _last_full < 1.5:
        return _cache
    rows = []
    for p in psutil.process_iter(["pid", "name", "memory_info", "username", "create_time", "exe"]):
        try:
            cpu = p.cpu_percent(None) / NCPU
            info = p.info
            rows.append({"pid": info["pid"], "name": info["name"] or "unknown",
                         "cpu": round(cpu, 1),
                         "ram_mb": round((info["memory_info"].rss if info["memory_info"] else 0) / 1e6, 1),
                         "exe": info.get("exe"), "user": info.get("username"),
                         "started": info.get("create_time")})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    _cache, _last_full = rows, time.time()
    return rows


def grouped(rows=None):
    """Chrome has 30 processes; a human cares about 'Chrome'."""
    rows = rows if rows is not None else sample()
    agg = defaultdict(lambda: {"cpu": 0.0, "ram_mb": 0.0, "count": 0, "pids": []})
    for r in rows:
        g = agg[r["name"].lower()]
        g["cpu"] += r["cpu"]; g["ram_mb"] += r["ram_mb"]; g["count"] += 1; g["pids"].append(r["pid"])
    out = [{"name": k, "cpu": round(v["cpu"], 1), "ram_mb": round(v["ram_mb"], 1),
            "instances": v["count"], "pids": v["pids"]} for k, v in agg.items()]
    return sorted(out, key=lambda x: x["cpu"], reverse=True)


def top_cpu(n=5):
    return grouped()[:n]


def top_ram(n=5):
    return sorted(grouped(), key=lambda x: x["ram_mb"], reverse=True)[:n]


def background(n=15):
    """Processes with no visible window that still consume resources."""
    rows = [r for r in sample() if r["cpu"] > 0.3 or r["ram_mb"] > 80]
    return sorted(rows, key=lambda r: r["ram_mb"], reverse=True)[:n]


def unresponsive():
    """Real 'Not Responding' detection via Win32. Empty list on non-Windows."""
    if os.name != "nt":
        return []
    try:
        import win32gui, win32process, win32con, win32api
        hung = []

        def cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd) or not win32gui.GetWindowText(hwnd):
                return
            try:
                ok = win32gui.SendMessageTimeout(hwnd, win32con.WM_NULL, 0, 0,
                                                 win32con.SMTO_ABORTIFHUNG, 500)
            except Exception:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                try: name = psutil.Process(pid).name()
                except Exception: name = "unknown"
                hung.append({"pid": pid, "name": name, "title": win32gui.GetWindowText(hwnd)})
        win32gui.EnumWindows(cb, None)
        return hung
    except Exception:
        return []
