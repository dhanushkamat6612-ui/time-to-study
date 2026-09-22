import os, shutil, pathlib, subprocess, fnmatch

class FileController:
    def __init__(self, allowed_roots):
        self.roots = [pathlib.Path(os.path.expanduser(r)).resolve() for r in allowed_roots]

    def _check(self, path):
        p = pathlib.Path(os.path.expanduser(str(path))).resolve()
        if not any(str(p).lower().startswith(str(r).lower()) for r in self.roots):
            raise PermissionError(
                f"'{p}' is outside the folders I'm allowed to touch. "
                f"Allowed: {', '.join(str(r) for r in self.roots)}")
        return p

    def create_folder(self, path, name=None):
        p = self._check(pathlib.Path(os.path.expanduser(str(path))) / name if name else path)
        if p.exists():
            return {"ok": True, "detail": f"{p} already exists.", "data": {"path": str(p)}}
        p.mkdir(parents=True)
        return {"ok": True, "detail": f"Created folder {p}", "data": {"path": str(p)}}

    def create_file(self, path, content=""):
        p = self._check(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"ok": True, "detail": f"Created file {p}", "data": {"path": str(p)}}

    def open_folder(self, path):
        p = self._check(path)
        if not p.exists():
            return {"ok": False, "detail": f"{p} does not exist, so I did not open anything."}
        subprocess.Popen(["explorer", str(p)])
        return {"ok": True, "detail": f"Opened {p} in File Explorer.", "data": {"path": str(p)}}

    def list_dir(self, path, limit=60):
        p = self._check(path)
        items = [{"name": e.name, "dir": e.is_dir(),
                  "size_mb": round(e.stat().st_size / 1e6, 2) if e.is_file() else None}
                 for e in list(p.iterdir())[:limit]]
        return {"ok": True, "detail": f"{len(items)} items in {p}", "data": {"path": str(p), "items": items}}

    def search(self, pattern, root="~", limit=40):
        r = self._check(root); hits = []
        for dirpath, dirs, files in os.walk(r):
            dirs[:] = [d for d in dirs if not d.startswith((".", "$"))]
            for f in files:
                if fnmatch.fnmatch(f.lower(), f"*{pattern.lower()}*"):
                    hits.append(os.path.join(dirpath, f))
                    if len(hits) >= limit:
                        return {"ok": True, "detail": f"Found {len(hits)} matches (stopped at limit).",
                                "data": {"matches": hits}}
        return {"ok": True, "detail": f"Found {len(hits)} matches.", "data": {"matches": hits}}

    def move(self, src, dst):
        s, d = self._check(src), self._check(dst)
        shutil.move(str(s), str(d))
        return {"ok": True, "detail": f"Moved {s.name} to {d}"}

    def organize(self, path):
        """Sorts loose files into type folders. Reports exactly what moved."""
        p = self._check(path)
        buckets = {"Images": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"],
                   "Documents": [".pdf", ".docx", ".doc", ".txt", ".xlsx", ".pptx", ".md"],
                   "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
                   "Installers": [".exe", ".msi"], "Media": [".mp4", ".mp3", ".mkv", ".wav", ".mov"],
                   "Code": [".py", ".js", ".ts", ".html", ".css", ".json", ".java", ".cpp"]}
        moved = {}
        for entry in p.iterdir():
            if entry.is_file():
                for folder, exts in buckets.items():
                    if entry.suffix.lower() in exts:
                        target = p / folder; target.mkdir(exist_ok=True)
                        shutil.move(str(entry), str(target / entry.name))
                        moved.setdefault(folder, []).append(entry.name)
                        break
        total = sum(len(v) for v in moved.values())
        return {"ok": True, "detail": f"Organised {total} files into {len(moved)} folders.",
                "data": {"moved": moved}}

    def delete(self, path):
        p = self._check(path)
        try:
            from send2trash import send2trash
            send2trash(str(p))
            return {"ok": True, "detail": f"Sent {p.name} to the Recycle Bin (recoverable)."}
        except ImportError:
            return {"ok": False, "detail": "send2trash isn't installed, and I won't permanently "
                                           "delete files without it. Install it and I'll retry."}
