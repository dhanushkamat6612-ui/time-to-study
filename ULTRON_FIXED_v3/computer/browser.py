import webbrowser, urllib.parse, subprocess, os, httpx, shutil

CDP_PORT = 9222
SEARCH = {"google": "https://www.google.com/search?q={}",
          "youtube": "https://www.youtube.com/results?search_query={}",
          "github": "https://github.com/search?q={}",
          "stackoverflow": "https://stackoverflow.com/search?q={}",
          "wikipedia": "https://en.wikipedia.org/w/index.php?search={}"}


def open_url(url):
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    webbrowser.open(url)
    return {"ok": True, "detail": f"Opened {url}", "data": {"url": url}}


def search(query, engine="google"):
    tpl = SEARCH.get(engine.lower(), SEARCH["google"])
    url = tpl.format(urllib.parse.quote_plus(query))
    webbrowser.open(url)
    return {"ok": True, "detail": f"Searched {engine} for '{query}'.", "data": {"url": url}}


def open_tabs(urls):
    opened = []
    for u in urls:
        open_url(u); opened.append(u)
    return {"ok": True, "detail": f"Opened {len(opened)} tabs.", "data": {"urls": opened}}


def _cdp(path="/json"):
    return httpx.get(f"http://127.0.0.1:{CDP_PORT}{path}", timeout=2).json()


def list_tabs():
    try:
        tabs = [{"id": t["id"], "title": t.get("title"), "url": t.get("url")}
                for t in _cdp() if t.get("type") == "page"]
        return {"ok": True, "detail": f"{len(tabs)} open tabs.", "data": {"tabs": tabs}}
    except Exception:
        return {"ok": False,
                "detail": "I can't read your browser tabs. Tab control needs Chrome started with "
                          f"--remote-debugging-port={CDP_PORT}. I can relaunch Chrome that way if you want."}


def close_tab(tab_id):
    try:
        httpx.get(f"http://127.0.0.1:{CDP_PORT}/json/close/{tab_id}", timeout=2)
        return {"ok": True, "detail": "Closed the tab."}
    except Exception as e:
        return {"ok": False, "detail": f"Could not close that tab: {e}"}


def launch_debug_chrome():
    for path in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                 r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"):
        if os.path.exists(path):
            subprocess.Popen([path, f"--remote-debugging-port={CDP_PORT}",
                              r"--user-data-dir=" + os.path.expandvars(r"%LOCALAPPDATA%\UltronChrome")])
            return {"ok": True, "detail": "Started Chrome with tab control enabled."}
    return {"ok": False, "detail": "Chrome executable not found."}
