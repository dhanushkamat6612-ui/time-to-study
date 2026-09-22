import psutil, subprocess, time

_last_temp_try = 0
_temp_supported = True


def snapshot():
    return {
        "percent": psutil.cpu_percent(interval=None),
        "per_core": psutil.cpu_percent(interval=None, percpu=True),
        "cores_physical": psutil.cpu_count(logical=False),
        "cores_logical": psutil.cpu_count(logical=True),
        "freq_mhz": getattr(psutil.cpu_freq(), "current", None),
        "temperature_c": temperature(),
    }


def temperature():
    """Returns None when the machine exposes no readable sensor. Never guesses."""
    global _last_temp_try, _temp_supported
    if not _temp_supported or time.time() - _last_temp_try < 30:
        return None
    _last_temp_try = time.time()
    try:
        temps = psutil.sensors_temperatures()          # usually empty on Windows
        for key in ("coretemp", "k10temp", "acpitz"):
            if temps.get(key):
                return round(temps[key][0].current, 1)
    except Exception:
        pass
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature"
             " -ErrorAction Stop).CurrentTemperature"],
            capture_output=True, text=True, timeout=6, creationflags=0x08000000)
        val = out.stdout.strip().splitlines()[0]
        return round(int(val) / 10 - 273.15, 1)
    except Exception:
        _temp_supported = False
        return None
