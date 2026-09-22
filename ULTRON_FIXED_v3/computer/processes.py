# computer/processes.py
import psutil
from monitoring import processes as pmon


def kill_pid(pid, force=False, protected=()):
    try:
        p = psutil.Process(pid)
        if p.name().lower() in [x.lower() for x in protected]:
            return {"ok": False, "detail": f"{p.name()} is protected. I won't terminate it."}
        name = p.name()
        p.kill() if force else p.terminate()
        p.wait(timeout=5)
        return {"ok": True, "detail": f"Terminated {name} (pid {pid})."}
    except psutil.NoSuchProcess:
        return {"ok": False, "detail": f"No process with pid {pid} is running."}
    except psutil.AccessDenied:
        return {"ok": False, "detail": f"Access denied for pid {pid}. Run ULTRON as administrator to do that."}
    except Exception as e:
        return {"ok": False, "detail": str(e)}


def list_running(limit=20):
    return {"ok": True, "detail": "Current process list.",
            "data": {"processes": pmon.grouped()[:limit], "unresponsive": pmon.unresponsive()}}
