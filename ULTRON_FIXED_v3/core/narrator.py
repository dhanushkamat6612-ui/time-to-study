def _fmt_gb(mb):
    return f"{mb/1024:.1f}GB" if mb >= 1024 else f"{int(mb)}MB"


def describe(action, res):
    d = res.get("data") or {}
    ok = res.get("ok")
    if not ok:
        return res.get("detail", "That didn't work.")
    if action == "system.top_cpu":
        t = d.get("top", [])
        if not t: return "Nothing is using a meaningful amount of CPU right now."
        lead = t[0]
        rest = ", ".join(f"{p['name']} at {p['cpu']}%" for p in t[1:3])
        s = f"CPU is at {d['cpu_percent']}% overall. {lead['name']} is the biggest consumer at {lead['cpu']}%"
        s += f" across {lead['instances']} processes" if lead["instances"] > 1 else ""
        return s + (f". Behind it: {rest}." if rest else ".")
    if action == "system.top_ram":
        t = d.get("top", [])
        lead = t[0] if t else None
        s = (f"You're using {d['used_gb']}GB of {d['total_gb']}GB ({d['percent']}%). ")
        return s + (f"{lead['name']} is holding the most at {_fmt_gb(lead['ram_mb'])}." if lead else "")
    if action == "system.why_slow":
        f = d.get("findings", [])
        if not f:
            return ("I don't see anything obviously wrong. CPU, memory and disk are all in normal ranges, "
                    "and no application is unresponsive.")
        first = f[0]
        extra = f" I also noticed: {f[1]['text'].lower()}." if len(f) > 1 else ""
        who = (f" {first['culprit']} is the main contributor."
               if first.get("culprit") else "")
        return f"{first['text']}.{who}{extra}"
    if action == "system.peak":
        if not d.get("available"):
            return d.get("reason", "I don't have enough history yet.")
        who = d["top_at_peak"][0]["name"] if d.get("top_at_peak") else None
        return (f"Highest CPU was {d['value']}% about {d['minutes_ago']:.0f} minutes ago"
                + (f", mostly {who}." if who else ".")
                + f" The average over that window was {d['average']}%.")
    if action == "system.storage":
        parts = [f"{x['mount']} has {x['free_gb']}GB free of {x['total_gb']}GB" for x in d.get("disks", [])]
        return "Storage: " + "; ".join(parts) + "."
    if action == "system.network":
        st = "online" if d.get("connected") else "offline"
        return (f"You're {st}. Currently downloading at {d['download_mb_s']:.2f} MB/s and uploading at "
                f"{d['upload_mb_s']:.2f} MB/s.")
    if action == "system.gpu":
        if not d.get("available"):
            return d.get("reason", "GPU telemetry isn't available on this machine.")
        mem = (f", using {d['memory_used_gb']}GB of {d['memory_total_gb']}GB video memory"
               if d.get("memory_total_gb") else "")
        temp = f" at {d['temperature_c']}°C" if d.get("temperature_c") else ""
        return f"{d['name']} is at {d['usage_percent']}%{mem}{temp}."
    if action == "system.background":
        items = d.get("processes", [])[:5]
        return ("Running quietly in the background: "
                + ", ".join(f"{p['name']} ({_fmt_gb(p['ram_mb'])})" for p in items) + ".")
    if action == "monitor.watch":
        return (f"I'm watching {d['metric'].upper()} now and I'll tell you when it "
                f"{'stays' if d['sustain_seconds'] else 'goes'} at or above {d['threshold']}%"
                + (f" for {d['sustain_seconds']//60} minutes." if d["sustain_seconds"] else "."))
    if action == "security.status":
        return ("Windows Security reports real-time protection "
                + ("on" if d.get("RealTimeProtectionEnabled") else "OFF")
                + f", signatures last updated {str(d.get('AntivirusSignatureLastUpdated'))[:16]}.")
    return res.get("detail", "Done.")


def summarize(user_text, results):
    """Fallback narration when no LLM is configured. Never invents success."""
    done = [r for r in results if r["result"].get("ok")]
    failed = [r for r in results if not r["result"].get("ok")]
    skipped = [r for r in results if r.get("status") == "denied"]
    if len(results) == 1:
        return describe(results[0]["action"], results[0]["result"])
    lines = []
    if done:
        lines.append(" ".join(describe(r["action"], r["result"]) for r in done[:4]))
    for r in failed:
        lines.append(f"I couldn't complete '{r['action']}': {r['result'].get('detail','unknown reason')}")
    for r in skipped:
        lines.append(f"I skipped '{r['action']}' because you didn't approve it.")
    return " ".join(lines) if lines else "Nothing to do."
