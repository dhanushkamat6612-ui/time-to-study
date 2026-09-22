import subprocess, time

_mode = None          # "nvml" | "smi" | "counter" | "none"
_cache, _cache_at = None, 0
_nvml = None


def _init():
    global _mode, _nvml
    try:
        import pynvml
        pynvml.nvmlInit(); _nvml = pynvml; _mode = "nvml"; return
    except Exception:
        pass
    try:
        subprocess.run(["nvidia-smi"], capture_output=True, timeout=5, creationflags=0x08000000)
        _mode = "smi"; return
    except Exception:
        _mode = "counter"


def snapshot():
    """Returns available=False rather than fabricating values."""
    global _cache, _cache_at
    if _mode is None:
        _init()
    if _cache and time.time() - _cache_at < 3:
        return _cache
    data = {"available": False, "reason": "No supported GPU telemetry source found."}
    try:
        if _mode == "nvml":
            h = _nvml.nvmlDeviceGetHandleByIndex(0)
            u = _nvml.nvmlDeviceGetUtilizationRates(h); m = _nvml.nvmlDeviceGetMemoryInfo(h)
            try: temp = _nvml.nvmlDeviceGetTemperature(h, 0)
            except Exception: temp = None
            data = {"available": True, "name": _nvml.nvmlDeviceGetName(h),
                    "usage_percent": u.gpu, "memory_used_gb": round(m.used / 1e9, 2),
                    "memory_total_gb": round(m.total / 1e9, 2), "temperature_c": temp}
        elif _mode == "smi":
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                 "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=6,
                creationflags=0x08000000).stdout.strip().split(", ")
            data = {"available": True, "name": out[0], "usage_percent": float(out[1]),
                    "memory_used_gb": round(float(out[2]) / 1024, 2),
                    "memory_total_gb": round(float(out[3]) / 1024, 2),
                    "temperature_c": float(out[4])}
        else:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "((Get-Counter '\\GPU Engine(*engtype_3D)\\Utilization Percentage'"
                 ").CounterSamples | Measure-Object CookedValue -Sum).Sum"],
                capture_output=True, text=True, timeout=10, creationflags=0x08000000)
            val = float(out.stdout.strip())
            data = {"available": True, "name": "Integrated/Generic GPU",
                    "usage_percent": round(min(val, 100.0), 1),
                    "memory_used_gb": None, "memory_total_gb": None, "temperature_c": None,
                    "note": "Windows performance counters: utilisation only."}
    except Exception as e:
        data = {"available": False, "reason": f"GPU telemetry unavailable ({type(e).__name__})."}
    _cache, _cache_at = data, time.time()
    return data
