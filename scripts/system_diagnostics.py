#!/usr/bin/env python3
"""Read-only system and project dependency diagnostics; safe to run before setup."""
from __future__ import annotations
import importlib.util, json, platform, shutil, socket, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def port(host, port):
    try:
        with socket.create_connection((host, port), timeout=1): return True
    except OSError: return False
def module_exists(name):
    try: return bool(importlib.util.find_spec(name))
    except (ImportError, ModuleNotFoundError): return False
def mysql_cli():
    found = shutil.which("mysql")
    if found: return found
    candidates = []
    if platform.system() == "Windows":
        import os
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
            candidates.extend(Path(base).glob("MySQL/MySQL Server */bin/mysql.exe"))
    elif platform.system() == "Darwin":
        candidates.extend([Path("/opt/homebrew/opt/mysql@8.4/bin/mysql"), Path("/opt/homebrew/opt/mysql/bin/mysql"), Path("/usr/local/mysql/bin/mysql")])
    else:
        candidates.extend([Path("/usr/bin/mysql"), Path("/usr/local/bin/mysql"), Path("/usr/local/mysql/bin/mysql")])
    return str(next((p for p in candidates if p.is_file()), "")) or None
def main():
    modules = {name: module_exists(name) for name in ("fastapi", "sqlalchemy", "mysql.connector", "sklearn", "pytest", "playwright")}
    result = {"platform": platform.platform(), "python": sys.version.split()[0], "python_supported": sys.version_info >= (3,11), "node": shutil.which("node"), "npm": shutil.which("npm"), "mysql_cli": mysql_cli(), "docker": shutil.which("docker"), "mysql_tcp": port("127.0.0.1",3306), "ollama_cli": shutil.which("ollama"), "modules": modules, "react_built": (ROOT/"web"/"dist"/"index.html").is_file(), "env_exists": (ROOT/".env").is_file()}
    if (ROOT/".env").is_file():
        try:
            from sme.config import settings
            from sme.services.narrative import verified_local_model_hash
            result["ollama_enabled"] = settings.local_llm_enabled
            result["ollama_model_verified"] = bool(verified_local_model_hash()) if settings.local_llm_enabled else False
        except Exception:
            result["ollama_model_verified"] = False
    print(json.dumps(result, indent=2)); return 0
if __name__ == "__main__": raise SystemExit(main())
