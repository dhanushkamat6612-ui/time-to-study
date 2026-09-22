"""ULTRON entry point."""
import os, sys, threading, time, webbrowser, json, pathlib

ROOT = pathlib.Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))

from server.app import build_app, CONFIG  # noqa: E402
import uvicorn  # noqa: E402


def open_ui(url: str):
    time.sleep(1.5)
    for browser in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"):
        if os.path.exists(browser):
            os.spawnv(os.P_NOWAIT, browser, [browser, f"--app={url}", "--window-size=1280,860"])
            return
    webbrowser.open(url)


if __name__ == "__main__":
    host = CONFIG["server"]["host"]; port = CONFIG["server"]["port"]
    url = f"http://{host}:{port}/"
    print(f"ULTRON online -> {url}")
    threading.Thread(target=open_ui, args=(url,), daemon=True).start()
    uvicorn.run(build_app(), host=host, port=port, log_level="warning")
