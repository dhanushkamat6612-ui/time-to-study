import psutil, time
from monitoring import processes


def diagnose(monitor):
    cur = monitor.current()
    findings, evidence = [], {}
    cpu_p = cur["cpu"]["percent"]; ram = cur["ram"]
    top = cur["top_cpu"]; topr = cur["top_ram"]

    avg5 = monitor.series("cpu", 5)
    avg = round(sum(avg5) / len(avg5), 1) if avg5 else cpu_p
    evidence["cpu_now"] = cpu_p; evidence["cpu_avg_5min"] = avg

    if avg >= 85:
        findings.append({"severity": "high", "area": "cpu",
                         "text": f"CPU has averaged {avg}% over the last 5 minutes",
                         "culprit": top[0]["name"] if top else None,
                         "culprit_usage": top[0]["cpu"] if top else None})
    elif cpu_p >= 85:
        findings.append({"severity": "medium", "area": "cpu",
                         "text": f"CPU is spiking at {cpu_p}% right now",
                         "culprit": top[0]["name"] if top else None})

    if ram["percent"] >= 88:
        findings.append({"severity": "high", "area": "ram",
                         "text": f"Memory is {ram['percent']}% full ({ram['used_gb']}GB of {ram['total_gb']}GB)",
                         "culprit": topr[0]["name"] if topr else None,
                         "culprit_usage": topr[0]["ram_mb"] if topr else None})
    if ram["swap_percent"] >= 60:
        findings.append({"severity": "medium", "area": "ram",
                         "text": f"Windows is paging heavily to disk (swap {ram['swap_percent']}% used)"})

    for d in cur["storage"]["disks"]:
        if d["free_gb"] < 10:
            findings.append({"severity": "high", "area": "storage",
                             "text": f"Drive {d['mount']} has only {d['free_gb']}GB free"})
        elif d["percent"] > 92:
            findings.append({"severity": "medium", "area": "storage",
                             "text": f"Drive {d['mount']} is {d['percent']}% full"})

    rw = (cur["storage"].get("read_mb_s") or 0) + (cur["storage"].get("write_mb_s") or 0)
    if rw > 120:
        findings.append({"severity": "medium", "area": "disk_io",
                         "text": f"Disk activity is high ({rw:.0f} MB/s combined)"})

    hung = processes.unresponsive()
    for h in hung:
        findings.append({"severity": "high", "area": "app",
                         "text": f"{h['name']} ('{h['title']}') is not responding", "pid": h["pid"]})

    heavy = [p for p in top if p["cpu"] > 15]
    if len(heavy) >= 3:
        findings.append({"severity": "low", "area": "load",
                         "text": f"{len(heavy)} applications are each using significant CPU simultaneously"})

    return {"findings": findings, "evidence": evidence,
            "top_cpu": top[:3], "top_ram": topr[:3],
            "monitor_uptime_min": round(monitor.uptime_minutes(), 1),
            "healthy": len(findings) == 0}
