import psutil, time

_prev = _prev_t = None

def snapshot():
    global _prev, _prev_t
    now = time.time()
    c = psutil.net_io_counters()
    down = up = 0.0
    if _prev is not None and _prev_t is not None and now > _prev_t:
        dt = now - _prev_t
        down = max(0.0, (c.bytes_recv - _prev.bytes_recv) / dt / 1e6)
        up = max(0.0, (c.bytes_sent - _prev.bytes_sent) / dt / 1e6)
    _prev, _prev_t = c, now

    # psutil.net_if_addrs() returns {interface_name: [address, ...]},
    # so each value is a list, not an object with an .addresses attribute.
    interfaces = psutil.net_if_addrs()
    connected = any(bool(addresses) for addresses in interfaces.values())

    return {
        "connected": connected,
        "download_mb_s": round(down, 2),
        "upload_mb_s": round(up, 2),
        "bytes_recv": c.bytes_recv,
        "bytes_sent": c.bytes_sent,
    }
