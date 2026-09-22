import psutil, time

_prev_io, _prev_t = None, None


def snapshot():
    global _prev_io, _prev_t
    disks = []
    for part in psutil.disk_partitions(all=False):
        try:
            u = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        disks.append({"device": part.device, "mount": part.mountpoint,
                      "total_gb": round(u.total / 1e9, 1), "used_gb": round(u.used / 1e9, 1),
                      "free_gb": round(u.free / 1e9, 1), "percent": u.percent})
    read_mb = write_mb = None
    try:
        io, now = psutil.disk_io_counters(), time.time()
        if _prev_io and now > _prev_t:
            dt = now - _prev_t
            read_mb = round((io.read_bytes - _prev_io.read_bytes) / dt / 1e6, 2)
            write_mb = round((io.write_bytes - _prev_io.write_bytes) / dt / 1e6, 2)
        _prev_io, _prev_t = io, now
    except Exception:
        pass
    return {"disks": disks, "read_mb_s": read_mb, "write_mb_s": write_mb}
