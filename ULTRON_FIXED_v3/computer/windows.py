# computer/windows.py
import subprocess, os, platform, psutil, time, json

CREATE_NO_WINDOW = 0x08000000


def powershell(cmd, timeout=25):
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                       capture_output=True, text=True, timeout=timeout, creationflags=CREATE_NO_WINDOW)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def ps_json(cmd, timeout=25):
    code, out, err = powershell(f"{cmd} | ConvertTo-Json -Depth 4 -Compress", timeout)
    if code != 0 or not out:
        return None, err or "No output"
    try:
        return json.loads(out), None
    except json.JSONDecodeError:
        return None, "Unparseable output"


def system_info():
    boot = psutil.boot_time()
    return {"ok": True, "detail": "System information.",
            "data": {"os": platform.platform(), "machine": platform.node(),
                     "cpu_model": platform.processor(),
                     "uptime_hours": round((time.time() - boot) / 3600, 1),
                     "boot_time": boot, "python": platform.python_version()}}


def toast(title, message):
    """Native Windows toast; falls back to UI-only notification."""
    ps = f'''
$ErrorActionPreference='Stop'
[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime]|Out-Null
$t=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(
   [Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$x=$t.GetElementsByTagName("text");$x[0].AppendChild($t.CreateTextNode("{title}"))|Out-Null
$x[1].AppendChild($t.CreateTextNode("{message}"))|Out-Null
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("ULTRON").Show(
   [Windows.UI.Notifications.ToastNotification]::new($t))'''
    try:
        code, _, _ = powershell(ps, timeout=10)
        return code == 0
    except Exception:
        return False


def open_settings(page="windowsdefender"):
    os.startfile(f"ms-settings:{page}")
    return {"ok": True, "detail": f"Opened Windows Settings ({page})."}


def empty_recycle_bin():
    code, _, err = powershell("Clear-RecycleBin -Force -ErrorAction Stop")
    return {"ok": code == 0, "detail": "Recycle Bin emptied." if code == 0 else f"Failed: {err}"}
