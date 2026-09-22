import os, hashlib, psutil, time, httpx
from computer.windows import ps_json, powershell

SUSPECT_DIRS = [os.path.expandvars(x).lower() for x in
                (r"%TEMP%", r"%APPDATA%", r"%LOCALAPPDATA%\Temp", r"%PUBLIC%", r"%USERPROFILE%\Downloads")]
SYSTEM_NAMES = {"svchost.exe": r"c:\windows\system32", "lsass.exe": r"c:\windows\system32",
                "csrss.exe": r"c:\windows\system32", "services.exe": r"c:\windows\system32",
                "winlogon.exe": r"c:\windows\system32", "explorer.exe": r"c:\windows"}


def defender_status():
    data, err = ps_json("Get-MpComputerStatus | Select-Object AMServiceEnabled,AntivirusEnabled,"
                        "RealTimeProtectionEnabled,AntivirusSignatureLastUpdated,"
                        "QuickScanEndTime,FullScanEndTime,AMProductVersion")
    if not data:
        return {"ok": False, "detail": f"Could not read Windows Security status ({err}). "
                                       "You may have third-party antivirus managing protection."}
    return {"ok": True, "detail": "Windows Security status retrieved.", "data": data}


def threats():
    data, err = ps_json("Get-MpThreatDetection | Select-Object -Last 10 ThreatID,InitialDetectionTime,"
                        "ActionSuccess,Resources")
    names, _ = ps_json("Get-MpThreat | Select-Object -Last 10 ThreatName,SeverityID,IsActive")
    if data is None and names is None:
        return {"ok": True, "detail": "Windows Defender reports no recorded threat detections."}
    return {"ok": True, "detail": "Recent Defender detections retrieved.",
            "data": {"detections": data, "threats": names}}


def start_scan(scan_type="QuickScan"):
    if scan_type not in ("QuickScan", "FullScan"):
        return {"ok": False, "detail": "Only QuickScan or FullScan are supported."}
    code, out, err = powershell(f"Start-MpScan -ScanType {scan_type}", timeout=60 * 60)
    return {"ok": code == 0,
            "detail": f"{scan_type} completed." if code == 0 else f"Scan could not be started: {err}"}


def remove_threats():
    """Removal is delegated to Defender — ULTRON never deletes files itself."""
    code, out, err = powershell("Remove-MpThreat", timeout=600)
    return {"ok": code == 0,
            "detail": "Asked Windows Defender to remove the detected threats."
                      if code == 0 else f"Defender removal failed: {err}"}


def _signature(path):
    data, _ = ps_json(f"Get-AuthenticodeSignature -FilePath '{path}' | "
                      "Select-Object Status,@{n='Signer';e={$_.SignerCertificate.Subject}}")
    return data or {}


def inspect_process(pid=None, name=None, vt_key=None):
    """Heuristic triage. Explicitly labelled as suspicion, never as a verdict."""
    procs = []
    for p in psutil.process_iter(["pid", "name", "exe", "username", "create_time", "cmdline"]):
        if (pid and p.info["pid"] == pid) or (name and (p.info["name"] or "").lower() == name.lower()):
            procs.append(p)
    if not procs:
        return {"ok": False, "detail": "No matching running process found."}

    results = []
    for p in procs[:3]:
        exe = p.info.get("exe")
        flags, notes = [], []
        if not exe:
            flags.append("Executable path is hidden from ULTRON (may need administrator rights).")
        else:
            low = exe.lower()
            if any(low.startswith(d) for d in SUSPECT_DIRS if d):
                flags.append(f"Runs from a temporary/user directory: {exe}")
            expected = SYSTEM_NAMES.get((p.info["name"] or "").lower())
            if expected and not low.startswith(expected):
                flags.append(f"Uses a Windows system process name but lives in {os.path.dirname(exe)} "
                             f"instead of {expected} — a classic masquerading pattern.")
            sig = _signature(exe)
            status = sig.get("Status")
            if status and status != "Valid":
                flags.append(f"Digital signature status: {status} (unsigned or untrusted publisher).")
            elif status == "Valid":
                notes.append(f"Validly signed by {sig.get('Signer','unknown publisher')}.")
            sha = None
            try:
                h = hashlib.sha256()
                with open(exe, "rb") as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        h.update(chunk)
                sha = h.hexdigest()
            except Exception:
                notes.append("Could not hash the file (locked or access denied).")
            vt = None
            if sha and vt_key:
                try:
                    r = httpx.get(f"https://www.virustotal.com/api/v3/files/{sha}",
                                  headers={"x-apikey": vt_key}, timeout=15)
                    if r.status_code == 200:
                        st = r.json()["data"]["attributes"]["last_analysis_stats"]
                        vt = st
                        if st.get("malicious", 0) > 0:
                            flags.append(f"VirusTotal: {st['malicious']} engines flag this file as malicious.")
                        else:
                            notes.append("VirusTotal: no engine currently flags this file.")
                    elif r.status_code == 404:
                        notes.append("VirusTotal has never seen this file before (uncommon for legitimate software).")
                except Exception:
                    notes.append("VirusTotal lookup failed.")
        try:
            conns = len(p.connections(kind="inet"))
            if conns > 15:
                flags.append(f"Holds {conns} network connections.")
        except Exception:
            pass

        results.append({"pid": p.info["pid"], "name": p.info["name"], "exe": exe,
                        "cmdline": " ".join(p.info.get("cmdline") or [])[:300],
                        "user": p.info.get("username"), "flags": flags, "notes": notes,
                        "confidence": "suspicious" if len(flags) >= 2 else
                                      ("worth checking" if flags else "nothing unusual found"),
                        "disclaimer": "These are heuristics, not a malware verdict. "
                                      "Confirmation should come from Windows Defender or another AV engine."})
    return {"ok": True, "detail": "Process inspection complete.", "data": {"results": results}}
