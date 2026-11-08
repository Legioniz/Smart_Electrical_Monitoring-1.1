#!/usr/bin/env python3
"""Build a local inventory of project assets and installed support tools.

The registry is diagnostic metadata, not executable configuration. It never
redirects Python imports or allows external manifests to replace source files.
"""
from __future__ import annotations
import hashlib, json, platform, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
REQUIRED = ["launch.py", "README.md", "requirements.txt", "compose.yaml", "sme/main.py", "sme/paths.py", "sme/config.py", "migrations/env.py", "frontend/package.json", "frontend/src/App.jsx", "web/index.html", "web/app.js", "web/styles.css", "database/create_users.sql", "scripts/run_verification.py", "scripts/train_synthetic_baseline.py", "scripts/system_diagnostics.py", "scripts/path_registry.py", "scripts/configure_local_llm.py", "docs/DATA_STORAGE_DECISIONS.md", "learning/README.md"]
TOOLS = ["python", "pip", "node", "npm", "mysql", "mysqladmin", "docker", "ollama"]
def version(path: str | None, args: list[str]) -> str | None:
    if not path: return None
    try:
        result = subprocess.run([path, *args], capture_output=True, text=True, timeout=8)
        return (result.stdout or result.stderr).strip().splitlines()[0][:200] if result.returncode == 0 else None
    except Exception: return None
def find_tool(name: str) -> str | None:
    found = shutil.which(name)
    if found: return found
    if name == "mysql":
        candidates = []
        if platform.system() == "Windows":
            import os
            for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
                candidates.extend(Path(base).glob("MySQL/MySQL Server */bin/mysql.exe"))
        elif platform.system() == "Darwin":
            candidates.extend([Path("/opt/homebrew/opt/mysql@8.4/bin/mysql"), Path("/opt/homebrew/opt/mysql/bin/mysql"), Path("/usr/local/mysql/bin/mysql")])
        else:
            candidates.extend([Path("/usr/bin/mysql"), Path("/usr/local/bin/mysql"), Path("/usr/local/mysql/bin/mysql")])
        return str(next((path for path in candidates if path.is_file()), "")) or None
    return None

def main() -> int:
    missing = [item for item in REQUIRED if not (ROOT / item).is_file()]
    files = {}
    for item in REQUIRED:
        path = ROOT / item
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            files[item] = {"path": str(path.resolve()), "sha256": digest, "exists": True}
        else: files[item] = {"path": str(path.resolve()), "exists": False}
    tools = {}
    for name in TOOLS:
        if name == "python":
            path = sys.executable
            tool_version = sys.version.split()[0]
        elif name == "pip":
            path = sys.executable + " -m pip"
            tool_version = version(sys.executable, ["-m", "pip", "--version"])
        else:
            path = find_tool(name)
            tool_version = version(path, ["--version"])
        tools[name] = {"path": path, "version": tool_version}
    manifest = {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(), "project_root": str(ROOT.resolve()), "required_files": files, "tools": tools, "missing_required_files": missing, "note": "Diagnostic inventory only; source and executable paths are never rewritten from this file."}
    LOCAL.mkdir(parents=True, exist_ok=True)
    output = LOCAL / "path-registry.json"
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Path registry: {output}")
    print(f"Required project files: {len(REQUIRED) - len(missing)}/{len(REQUIRED)}")
    for name, item in tools.items(): print(f"{name:12} {item['path'] or 'not found'}")
    if missing:
        print("Missing files: " + ", ".join(missing)); return 1
    return 0
if __name__ == "__main__": raise SystemExit(main())
