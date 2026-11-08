#!/usr/bin/env python3
"""Smart Meter Explorer one-file launcher.

Checks the host, creates/reuses a private venv, installs only missing or mismatched
Python packages, prepares local MySQL (native or Docker when approved), optionally
builds the React UI, runs migrations/demo bootstrap, and starts the local server.
No source files are self-modified at runtime; generated state stays under .local/.
"""
from __future__ import annotations

import argparse
import getpass
import os
import platform
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
LOCAL = ROOT / ".local"
LOG_DIR = LOCAL / "logs"
COMPOSE_FILE = ROOT / "compose.yaml"
MIN_PYTHON = (3, 11)
MIN_NODE = (22, 0)


def say(message: str) -> None:
    print(f"\n[SME] {message}", flush=True)


def ask_yes_no(question: str, default: bool = False, assume_yes: bool = False) -> bool:
    if assume_yes:
        say(f"{question} [yes: --yes]")
        return True
    if not sys.stdin.isatty():
        return default
    suffix = "Y/n" if default else "y/N"
    answer = input(f"{question} [{suffix}]: ").strip().casefold()
    return default if not answer else answer in {"y", "yes"}


def run(command: list[str], *, cwd: Path = ROOT, timeout: int = 900,
        env: dict[str, str] | None = None, check: bool = True,
        input_text: str | None = None) -> subprocess.CompletedProcess:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    printable = " ".join(command)
    say(f"Running: {printable}")
    result = subprocess.run(command, cwd=cwd, env=env, input=input_text,
                            text=True, capture_output=True, timeout=timeout)
    log_path = LOG_DIR / "launcher.log"
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n$ {printable}\n{result.stdout or ''}{result.stderr or ''}\n")
    if result.stdout:
        print(result.stdout[-5000:], end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr[-5000:], file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
    if check and result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {printable}. See .local/logs/launcher.log")
    return result


def python_version_ok(executable: str = sys.executable) -> bool:
    code = "import sys; print('%d.%d.%d' % sys.version_info[:3]); raise SystemExit(0 if sys.version_info >= (3,11) else 1)"
    return subprocess.run([executable, "-c", code], capture_output=True).returncode == 0


def venv_python() -> Path:
    return ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def select_supported_python() -> list[str]:
    candidates = [[sys.executable]]
    if os.name == "nt" and shutil.which("py"):
        candidates.append([shutil.which("py") or "py", "-3.11"])
    for name in ("python3.11", "python3", "python"):
        path = shutil.which(name)
        if path:
            candidates.append([path])
    for candidate in candidates:
        try:
            result = subprocess.run(candidate + ["-c", "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)"], capture_output=True, timeout=8)
            if result.returncode == 0:
                return candidate
        except Exception:
            continue
    raise RuntimeError("Python 3.11 or newer is required. Install Python 3.11+ and rerun launch.py.")


def ensure_venv() -> Path:
    base_python = select_supported_python()
    executable = venv_python()
    if not executable.is_file():
        say("Creating the project virtual environment (existing system Python packages are untouched).")
        run(base_python + ["-m", "venv", str(ROOT / ".venv")])
    if not python_version_ok(str(executable)):
        raise RuntimeError("The project virtual environment uses an unsupported Python version.")
    return executable


def parse_requirements() -> list[tuple[str, str, str]]:
    rows = []
    for raw in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)(?:\[[^]]+\])?==([^;\s]+)$", line)
        if not match:
            raise RuntimeError(f"Unsupported requirement format in requirements.txt: {line}")
        dist = re.match(r"^([A-Za-z0-9_.-]+)", line).group(1).replace("_", "-").lower()
        rows.append((dist, match.group(2), line))
    return rows


def ensure_python_dependencies(py: Path) -> None:
    missing = []
    for dist, wanted, spec in parse_requirements():
        probe = subprocess.run(
            [str(py), "-c", "import importlib.metadata as m,sys\ntry: print(m.version(sys.argv[1]))\nexcept m.PackageNotFoundError: raise SystemExit(3)", dist],
            capture_output=True, text=True, timeout=15,
        )
        installed = probe.stdout.strip() if probe.returncode == 0 else None
        if installed != wanted:
            missing.append(spec)
    if missing:
        say("Installing only missing or version-mismatched Python dependencies: " + ", ".join(missing))
        run([str(py), "-m", "pip", "install", "--disable-pip-version-check", *missing], timeout=1200)
    else:
        say("Python dependencies already match requirements.txt; no reinstall needed.")
    consistency = run([str(py), "-m", "pip", "check"], timeout=120, check=False)
    if consistency.returncode:
        say("The installed environment has a missing or conflicting transitive dependency. Reconciling the pinned requirements without clearing the environment.")
        run([str(py), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(ROOT / "requirements.txt")], timeout=1800)
        run([str(py), "-m", "pip", "check"], timeout=120)


def read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if ENV_FILE.exists():
        for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def write_env(values: dict[str, str]) -> None:
    existing_lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    updated = []
    seen = set()
    for line in existing_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in values:
                updated.append(f"{key}={values[key]}")
                seen.add(key)
                continue
        updated.append(line)
    for key, value in values.items():
        if key not in seen:
            updated.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(updated).rstrip() + "\n", encoding="utf-8")
    try:
        ENV_FILE.chmod(0o600)
    except OSError:
        pass


def align_default_loopback_allowlists(values: dict[str, str]) -> dict[str, str]:
    """Keep stock loopback allowlists aligned when the operator changes APP_PORT."""
    port = values.get("APP_PORT", "8000")
    if not port.isdigit() or not (1 <= int(port) <= 65535):
        raise RuntimeError("APP_PORT must be an integer between 1 and 65535.")
    default_origins = "http://127.0.0.1:8000,http://localhost:8000"
    default_hosts = "127.0.0.1:8000,localhost:8000"
    if values.get("APP_ALLOWED_ORIGINS", default_origins) == default_origins:
        values["APP_ALLOWED_ORIGINS"] = f"http://127.0.0.1:{port},http://localhost:{port}"
    if values.get("APP_ALLOWED_HOSTS", default_hosts) == default_hosts:
        values["APP_ALLOWED_HOSTS"] = f"127.0.0.1:{port},localhost:{port}"
    return values


def ensure_env(py: Path) -> dict[str, str]:
    if not ENV_FILE.exists():
        run([str(py), "scripts/create_env.py"])
    values = align_default_loopback_allowlists(read_env())
    if not values.get("APP_SECRET_KEY") or values.get("APP_SECRET_KEY") == "GENERATE_ME":
        values["APP_SECRET_KEY"] = secrets.token_urlsafe(48)
        write_env(values)
    return read_env()


def mysql_cli_path() -> str | None:
    found = shutil.which("mysql")
    if found:
        return found
    candidates: list[Path] = []
    if os.name == "nt":
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
            candidates.extend(Path(base).glob("MySQL/MySQL Server */bin/mysql.exe"))
    elif platform.system() == "Darwin":
        candidates.extend([Path("/opt/homebrew/opt/mysql@8.4/bin/mysql"), Path("/opt/homebrew/opt/mysql/bin/mysql"), Path("/usr/local/mysql/bin/mysql"), Path("/usr/local/opt/mysql/bin/mysql")])
    else:
        candidates.extend([Path("/usr/bin/mysql"), Path("/usr/local/bin/mysql"), Path("/usr/local/mysql/bin/mysql")])
    return str(next((candidate for candidate in candidates if candidate.is_file()), "")) or None


def start_existing_mysql_service(assume_yes: bool = False) -> bool:
    """Try to start a detected MySQL service; never reinstall an existing server."""
    system = platform.system()
    if system == "Windows" and shutil.which("sc"):
        query = subprocess.run(["sc", "query", "state=", "all"], capture_output=True, text=True, timeout=20)
        names = re.findall(r"SERVICE_NAME:\s*(MySQL[^\s]+)", query.stdout, re.IGNORECASE)
        for name in names:
            if ask_yes_no(f"MySQL service {name} is installed. Start it?", default=True, assume_yes=assume_yes):
                run(["sc", "start", name], check=False, timeout=60)
                if tcp_open(): return True
    elif system == "Darwin" and shutil.which("brew"):
        status = subprocess.run(["brew", "services", "list"], capture_output=True, text=True, timeout=20)
        service = next((line.split()[0] for line in status.stdout.splitlines() if line.split() and line.split()[0].startswith("mysql")), None)
        if service and ask_yes_no(f"Detected Homebrew MySQL service {service}. Start it?", default=True, assume_yes=assume_yes):
            run(["brew", "services", "start", service], check=False, timeout=120)
            return tcp_open()
    elif system == "Linux" and shutil.which("systemctl"):
        for service in ("mysql", "mysqld"):
            exists = subprocess.run(["systemctl", "list-unit-files", f"{service}.service"], capture_output=True, text=True, timeout=15)
            if f"{service}.service" in exists.stdout:
                if ask_yes_no(f"Detected installed MySQL service {service}. Start it?", default=True, assume_yes=assume_yes):
                    sudo = shutil.which("sudo")
                    command = ([sudo, "systemctl", "start", service] if sudo else ["systemctl", "start", service])
                    run(command, check=False, timeout=120)
                    return tcp_open()
    return tcp_open()


def tcp_open(host: str = "127.0.0.1", port: int = 3306, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def mysql_url_credentials(url: str) -> dict | None:
    try:
        parsed = urlsplit(url)
        if not parsed.scheme.startswith("mysql") or not parsed.hostname or not parsed.username:
            return None
        return {"host": parsed.hostname, "port": parsed.port or 3306,
                "user": unquote(parsed.username), "password": unquote(parsed.password or ""),
                "database": parsed.path.lstrip("/")}
    except Exception:
        return None


def mysql_connection_ok(py: Path, url: str) -> bool:
    creds = mysql_url_credentials(url)
    if not creds:
        return False
    code = ("import mysql.connector,sys; c=mysql.connector.connect(" +
            ",".join(f"{k}={v!r}" for k, v in creds.items()) +
            ",connection_timeout=3); c.close()")
    return subprocess.run([str(py), "-c", code], cwd=ROOT, capture_output=True, timeout=8).returncode == 0


def mysql_version_supported(version_text: str, version_comment: str = "") -> bool:
    combined = f"{version_text} {version_comment}".casefold()
    if "mariadb" in combined:
        return False
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", version_text or "")
    if not match:
        return False
    return tuple(map(int, match.groups())) >= (8, 0, 16)


def mysql_server_compatible(py: Path, url: str) -> bool:
    creds = mysql_url_credentials(url)
    if not creds:
        return False
    code = (
        "import mysql.connector,sys; c=mysql.connector.connect(" +
        ",".join(f"{k}={v!r}" for k, v in creds.items()) +
        ",connection_timeout=3); cur=c.cursor(); cur.execute('SELECT VERSION(), @@version_comment'); row=cur.fetchone(); c.close(); "
        "import re; v,comment=row; m=re.search(r'(\\d+)\\.(\\d+)\\.(\\d+)',v or ''); "
        "raise SystemExit(0 if m and 'mariadb' not in ((v+' '+str(comment)).lower()) and tuple(map(int,m.groups())) >= (8,0,16) else 4)"
    )
    return subprocess.run([str(py), "-c", code], cwd=ROOT, capture_output=True, timeout=8).returncode == 0


def sql_quote(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def configure_db_urls(values: dict[str, str], app_password: str, migration_password: str) -> dict[str, str]:
    host = values.get("SME_MYSQL_HOST", "127.0.0.1")
    port = values.get("SME_MYSQL_PORT", "3306")
    database = values.get("SME_MYSQL_DATABASE", "smart_meter_explorer")
    values["DATABASE_URL"] = f"mysql+mysqlconnector://sme_app:{quote(app_password, safe='')}@{host}:{port}/{database}"
    values["MIGRATION_DATABASE_URL"] = f"mysql+mysqlconnector://sme_migrator:{quote(migration_password, safe='')}@{host}:{port}/{database}"
    return values


def mysql_user_sql(app_password: str, migration_password: str, host_pattern: str) -> str:
    app = sql_quote(app_password)
    migrator = sql_quote(migration_password)
    return f"""CREATE DATABASE IF NOT EXISTS smart_meter_explorer CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER IF NOT EXISTS 'sme_app'@'{host_pattern}' IDENTIFIED BY {app};
ALTER USER 'sme_app'@'{host_pattern}' IDENTIFIED BY {app};
CREATE USER IF NOT EXISTS 'sme_migrator'@'{host_pattern}' IDENTIFIED BY {migrator};
ALTER USER 'sme_migrator'@'{host_pattern}' IDENTIFIED BY {migrator};
GRANT SELECT, INSERT, UPDATE, DELETE ON smart_meter_explorer.* TO 'sme_app'@'{host_pattern}';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, INDEX, REFERENCES ON smart_meter_explorer.* TO 'sme_migrator'@'{host_pattern}';
FLUSH PRIVILEGES;
"""


def compose_available() -> bool:
    docker = shutil.which("docker")
    if not docker:
        return False
    result = subprocess.run([docker, "compose", "version"], capture_output=True, text=True, timeout=10)
    return result.returncode == 0


def setup_docker_mysql(values: dict[str, str], assume_yes: bool) -> bool:
    if not compose_available():
        return False
    if not ask_yes_no("No MySQL server is responding. Start a private MySQL 8.4 Docker container bound only to 127.0.0.1?", default=False, assume_yes=assume_yes):
        return False
    root_password = values.get("SME_MYSQL_ROOT_PASSWORD") or secrets.token_urlsafe(32)
    app_password = secrets.token_urlsafe(32)
    migration_password = secrets.token_urlsafe(32)
    values.update({"SME_MYSQL_ROOT_PASSWORD": root_password,
                   "SME_MYSQL_APP_PASSWORD": app_password,
                   "SME_MYSQL_MIGRATOR_PASSWORD": migration_password,
                   "SME_MYSQL_HOST": "127.0.0.1", "SME_MYSQL_PORT": "3306",
                   "SME_MYSQL_DATABASE": "smart_meter_explorer"})
    configure_db_urls(values, app_password, migration_password)
    write_env(values)
    init_dir = LOCAL / "mysql-init"
    init_dir.mkdir(parents=True, exist_ok=True)
    try: init_dir.chmod(0o700)
    except OSError: pass
    init_sql = init_dir / "01-users.sql"
    init_sql.write_text(mysql_user_sql(app_password, migration_password, "%"), encoding="utf-8")
    try: init_sql.chmod(0o600)
    except OSError: pass
    run([shutil.which("docker") or "docker", "compose", "up", "-d", "mysql"], timeout=1200)
    say("Waiting for the local MySQL container to accept connections...")
    for _ in range(60):
        if tcp_open():
            break
        time.sleep(2)
    if not tcp_open():
        raise RuntimeError("Docker MySQL did not open 127.0.0.1:3306. Check `docker compose logs mysql`.")
    # Init scripts run only for a fresh volume. Re-apply idempotent grants so an
    # existing local volume can be reused without deleting any database data.
    docker = shutil.which("docker") or "docker"
    run([docker, "compose", "exec", "-T", "mysql", "sh", "-lc",
         'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot --protocol=socket'],
        input_text=mysql_user_sql(app_password, migration_password, "%"), timeout=90)
    return True


def setup_native_mysql(values: dict[str, str], assume_yes: bool) -> bool:
    mysql = mysql_cli_path()
    if not mysql:
        say("MySQL is listening, but the `mysql` admin CLI is not installed or not on PATH.")
        return False
    if not ask_yes_no("Configure the local database and least-privilege SME accounts using your MySQL administrator login?", default=False, assume_yes=assume_yes):
        return False
    admin_user = input("MySQL administrator username [root]: ").strip() or "root"
    admin_password = getpass.getpass("MySQL administrator password (not saved; press Enter for local socket authentication): ")
    app_password = secrets.token_urlsafe(32)
    migration_password = secrets.token_urlsafe(32)
    sql = mysql_user_sql(app_password, migration_password, "127.0.0.1")
    env = os.environ.copy()
    if admin_password:
        env["MYSQL_PWD"] = admin_password
        command = [mysql, "--protocol=TCP", "-h", "127.0.0.1", "-u", admin_user]
    elif os.name != "nt" and shutil.which("sudo"):
        command = [shutil.which("sudo") or "sudo", mysql, "-u", admin_user]
    else:
        command = [mysql, "-u", admin_user]
    result = run(command, env=env, input_text=sql, check=False, timeout=60)
    env.pop("MYSQL_PWD", None)
    if result.returncode:
        raise RuntimeError("Could not configure MySQL accounts. Check administrator privileges and .local/logs/launcher.log.")
    values.update({"SME_MYSQL_HOST": "127.0.0.1", "SME_MYSQL_PORT": "3306", "SME_MYSQL_DATABASE": "smart_meter_explorer"})
    configure_db_urls(values, app_password, migration_password)
    write_env(values)
    return True


def install_mysql_server_if_approved() -> bool:
    if not ask_yes_no("No MySQL or Docker database is available. Install MySQL Server using this computer's package manager? This changes system software and may require administrator approval.", default=False):
        return False
    system = platform.system()
    if system == "Windows" and shutil.which("winget"):
        run(["winget", "install", "--id", "Oracle.MySQL", "--exact", "--accept-package-agreements", "--accept-source-agreements"], timeout=2400)
        mysql_cli = shutil.which("mysql")
        if not mysql_cli:
            say("MySQL was installed. Open a new terminal or add the MySQL Server bin folder to PATH, then rerun launch.py.")
            return False
        run(["sc", "start", "MySQL80"], check=False, timeout=60)
    elif system == "Darwin" and shutil.which("brew"):
        run(["brew", "install", "mysql@8.4"], timeout=2400)
        run(["brew", "services", "start", "mysql@8.4"], check=False, timeout=120)
        say("If Homebrew installed MySQL outside PATH, add its mysql@8.4 bin directory and rerun the launcher.")
    elif system == "Linux" and shutil.which("apt-get") and shutil.which("sudo"):
        run(["sudo", "apt-get", "update"], timeout=1800)
        run(["sudo", "apt-get", "install", "-y", "mysql-server"], timeout=2400)
        run(["sudo", "systemctl", "enable", "--now", "mysql"], check=False, timeout=120)
    elif system == "Linux" and shutil.which("dnf") and shutil.which("sudo"):
        run(["sudo", "dnf", "install", "-y", "mysql-server"], timeout=2400)
        run(["sudo", "systemctl", "enable", "--now", "mysqld"], check=False, timeout=120)
    else:
        say("No supported MySQL package manager was found. Install MySQL Community Server 8.0.16+ manually and rerun.")
        return False
    say("Waiting for the MySQL service to start...")
    for _ in range(60):
        if tcp_open():
            return True
        time.sleep(2)
    say("MySQL installation was attempted, but the service is not responding on 127.0.0.1:3306. Start it and rerun launch.py.")
    return False


def ensure_database(py: Path, values: dict[str, str], assume_yes: bool, skip_db: bool) -> bool:
    if skip_db:
        say("Database setup skipped by command-line option; app cannot serve customer data until MySQL is configured.")
        return False
    database_url = values.get("DATABASE_URL", "")
    migration_url = values.get("MIGRATION_DATABASE_URL", "")
    if mysql_connection_ok(py, database_url) and mysql_connection_ok(py, migration_url) and mysql_server_compatible(py, database_url):
        say("Both MySQL application and migration accounts verified; server is MySQL 8.0.16+; existing database and credentials preserved.")
        return True
    if not tcp_open() and mysql_cli_path():
        start_existing_mysql_service(assume_yes=False)
    if tcp_open():
        say("A MySQL server is present on 127.0.0.1:3306, but the configured app credentials did not connect.")
        if setup_native_mysql(values, assume_yes):
            write_env(values)
            if mysql_connection_ok(py, values["DATABASE_URL"]) and mysql_connection_ok(py, values["MIGRATION_DATABASE_URL"]) and mysql_server_compatible(py, values["DATABASE_URL"]):
                return True
        raise RuntimeError("MySQL is installed but not configured. Run the launcher again after setting the database credentials, or use the setup instructions in README.md.")
    if not tcp_open() and mysql_cli_path():
        say("MySQL client files are already installed, but no server is responding. Attempted to start an existing service; no reinstall was performed.")
    if setup_docker_mysql(values, assume_yes):
        for _ in range(45):
            if mysql_connection_ok(py, values["DATABASE_URL"]) and mysql_connection_ok(py, values["MIGRATION_DATABASE_URL"]) and mysql_server_compatible(py, values["DATABASE_URL"]):
                say("Docker MySQL 8.4 is healthy and both least-privilege accounts work.")
                return True
            time.sleep(2)
        raise RuntimeError("MySQL container started, but app credentials did not connect. Inspect `docker compose logs mysql` and .local/logs/launcher.log.")
    if install_mysql_server_if_approved():
        if setup_native_mysql(values, assume_yes=False):
            write_env(values)
            if mysql_connection_ok(py, values["DATABASE_URL"]) and mysql_connection_ok(py, values["MIGRATION_DATABASE_URL"]):
                say("Native MySQL is ready and both least-privilege accounts work.")
                return True
    say("MySQL is not available. Install/start MySQL Community Server 8.0.16+, or install Docker Desktop and rerun to use the managed local container.")
    say("System database software is installed only after an explicit confirmation. Existing data is not deleted or reset.")
    return False


def node_version() -> tuple[int, int, int] | None:
    node = shutil.which("node")
    if not node:
        return None
    result = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=10)
    match = re.search(r"v?(\d+)\.(\d+)\.(\d+)", result.stdout)
    return tuple(map(int, match.groups())) if match else None


def install_node_if_approved(assume_yes: bool) -> None:
    if not ask_yes_no("Node.js is optional (the offline interface works without it). Install Node.js 22+ to build the React interface?", default=False, assume_yes=assume_yes):
        return
    system = platform.system()
    if system == "Windows" and shutil.which("winget"):
        run(["winget", "install", "--id", "OpenJS.NodeJS.LTS", "--exact", "--accept-package-agreements", "--accept-source-agreements"], timeout=1800)
    elif system == "Darwin" and shutil.which("brew"):
        run(["brew", "install", "node@22"], timeout=1800)
        say("If node is still not found, open a new terminal so Homebrew's PATH changes take effect.")
    elif system == "Linux" and shutil.which("apt-get"):
        say("The system package manager may provide an older Node.js than Vite requires; install Node.js 22 LTS from https://nodejs.org/ and rerun this launcher.")
        return
    else:
        say("No supported Node.js package manager was found. Install Node.js 22 LTS from https://nodejs.org/ and rerun.")


def maybe_configure_ollama(py: Path, values: dict[str, str]) -> None:
    if not shutil.which("ollama") or values.get("LOCAL_LLM_ENABLED", "false").lower() == "true":
        return
    if sys.stdin.isatty() and ask_yes_no("Ollama is installed. Configure an already-downloaded local model for energy stories and suggestions?", default=False):
        result = run([str(py), "scripts/configure_local_llm.py"], check=False, timeout=60)
        if result.returncode:
            say("Local LLM setup was not completed. Deterministic analytics and suggestions remain available.")


def build_react(assume_yes: bool, no_react: bool) -> str:
    if no_react:
        return "skipped by request; offline fallback remains active"
    version = node_version()
    if version is None or version < MIN_NODE:
        install_node_if_approved(False)
        version = node_version()
    if version is None or version < MIN_NODE:
        say("Node.js 22+ is unavailable. Keeping the already-runnable offline fallback interface; React is optional.")
        return "fallback active; Node.js 22+ not available"
    npm = shutil.which("npm")
    if not npm:
        say("Node.js exists but npm is missing; keeping the offline fallback interface.")
        return "fallback active; npm missing"
    frontend = ROOT / "frontend"
    modules = frontend / "node_modules"
    vite_bin = modules / ".bin" / ("vite.cmd" if os.name == "nt" else "vite")
    if not vite_bin.exists():
        run([npm, "install", "--no-audit", "--no-fund"], cwd=frontend, timeout=1800)
    else:
        check = run([npm, "ls", "--depth=0"], cwd=frontend, check=False, timeout=60)
        if check.returncode:
            run([npm, "install", "--no-audit", "--no-fund"], cwd=frontend, timeout=1800)
        else:
            say("React dependencies are already installed; no reinstall needed.")
    try:
        run([npm, "run", "build"], cwd=frontend, timeout=600)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        say(f"React build was unavailable ({exc}). The no-CDN fallback remains available.")
        return "fallback active; React build unavailable"
    if not (ROOT / "web" / "dist" / "index.html").is_file():
        say("React build did not produce web/dist/index.html; retaining the offline fallback.")
        return "fallback active; React output missing"
    return "React production bundle built successfully"


def run_diagnostics(py: Path | None = None) -> dict:
    checks = {
        "OS": f"{platform.system()} {platform.release()}",
        "Python": platform.python_version(),
        "Python supported": "yes" if sys.version_info >= MIN_PYTHON else "no (need 3.11+)",
        "Project venv": "present" if venv_python().exists() else "missing",
        "MySQL TCP 127.0.0.1:3306": "responding" if tcp_open() else "not responding",
        "MySQL CLI": mysql_cli_path() or "not found",
        "Docker Compose": "available" if compose_available() else "not found",
        "Node.js": ".".join(map(str, node_version())) if node_version() else "not found",
        "npm": shutil.which("npm") or "not found",
        "Ollama": shutil.which("ollama") or "not found (optional)",
        "React build": "present" if (ROOT / "web" / "dist" / "index.html").is_file() else "not built (fallback available)",
        ".env": "present" if ENV_FILE.exists() else "missing",
    }
    if py:
        values = read_env()
        checks["MySQL credentials"] = "connected" if mysql_connection_ok(py, values.get("DATABASE_URL", "")) else "not verified"
    for key, value in checks.items():
        print(f"{key:30} {value}")
    return checks


def bootstrap_and_serve(py: Path) -> int:
    values = read_env()
    port = int(values.get("APP_PORT", "8000"))
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as response:
            payload = response.read(4096).decode("utf-8", "replace")
            if response.status == 200 and '"database":"connected"' in payload:
                say("A healthy Smart Meter Explorer instance is already running. Opening it instead of starting a duplicate server.")
                import webbrowser
                webbrowser.open(f"http://127.0.0.1:{port}/")
                return 0
    except Exception:
        pass
    if tcp_open("127.0.0.1", port, timeout=0.5):
        raise RuntimeError(f"Port {port} is already occupied by another service. Change APP_PORT in .env and rerun the launcher.")
    run([str(py), "-m", "sme.cli", "bootstrap"], timeout=1800)
    command = [str(py), "-m", "sme.cli", "serve"]
    say(f"Starting Smart Meter Explorer at http://127.0.0.1:{port}/")
    process = subprocess.Popen(command, cwd=ROOT)
    try:
        for _ in range(30):
            if process.poll() is not None:
                raise RuntimeError(f"Application exited during startup (code {process.returncode}).")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                    if response.status < 500:
                        break
            except (urllib.error.URLError, TimeoutError, OSError):
                time.sleep(1)
        try:
            import webbrowser
            webbrowser.open(f"http://127.0.0.1:{port}/")
        except Exception:
            pass
        return process.wait()
    except KeyboardInterrupt:
        say("Stopping the local application...")
        process.terminate()
        try:
            return process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            return 130


def main() -> int:
    parser = argparse.ArgumentParser(description="One-file Smart Meter Explorer setup and launcher")
    parser.add_argument("--diagnose", action="store_true", help="inspect this computer without installing or changing anything")
    parser.add_argument("--setup-only", action="store_true", help="prepare dependencies and database but do not start the server")
    parser.add_argument("--skip-db", action="store_true", help="skip MySQL setup (application will not be fully usable)")
    parser.add_argument("--no-react", action="store_true", help="use the no-CDN offline fallback even if Node.js is available")
    parser.add_argument("--yes", action="store_true", help="accept optional local Docker MySQL setup; does not approve OS-level installs")
    args = parser.parse_args()
    try:
        say("Smart Meter Explorer — environment inspection")
        run_diagnostics()
        if args.diagnose:
            return 0
        py = ensure_venv()
        ensure_python_dependencies(py)
        values = ensure_env(py)
        maybe_configure_ollama(py, values)
        run([str(py), "scripts/path_registry.py"])
        run([str(py), "scripts/system_diagnostics.py"])
        db_ok = ensure_database(py, values, args.yes, args.skip_db)
        if not db_ok and not args.skip_db:
            return 2
        react_status = build_react(args.yes, args.no_react)
        say(f"Frontend: {react_status}")
        if args.setup_only:
            say("Setup phase completed. Run `python launch.py` to bootstrap and start the app.")
            return 0
        if not db_ok:
            say("Cannot start the full application without a verified MySQL database. Install/configure MySQL and rerun.")
            return 2
        return bootstrap_and_serve(py)
    except (RuntimeError, subprocess.TimeoutExpired, OSError, ValueError) as exc:
        print(f"\n[SME SETUP ERROR] {exc}", file=sys.stderr)
        print("See README.md and .local/logs/launcher.log for details.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
