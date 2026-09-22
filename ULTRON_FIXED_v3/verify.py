import ast, pathlib, sys
root=pathlib.Path(__file__).parent
errors=[]
for p in root.rglob("*.py"):
 try: ast.parse(p.read_text(encoding="utf-8"))
 except Exception as e: errors.append(f"{p}: {e}")
print("Python syntax: OK" if not errors else "Python syntax errors:")
for e in errors: print(e)
print("Project root:", root)
print("Config:", (root/"config/settings.json").exists())
print("HUD:", (root/"ui/index.html").exists())
