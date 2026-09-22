import psutil


def snapshot():
    vm = psutil.virtual_memory(); sw = psutil.swap_memory()
    return {
        "total_gb": round(vm.total / 1e9, 2),
        "used_gb": round(vm.used / 1e9, 2),
        "available_gb": round(vm.available / 1e9, 2),
        "percent": vm.percent,
        "swap_used_gb": round(sw.used / 1e9, 2),
        "swap_percent": sw.percent,
    }
