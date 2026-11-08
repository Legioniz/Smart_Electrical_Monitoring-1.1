from __future__ import annotations
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sme_launcher", ROOT / "launch.py")
launcher = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(launcher)


def test_launcher_requirement_parser_uses_exact_pins():
    requirements = launcher.parse_requirements()
    assert requirements
    assert all(name and version and spec.endswith("==" + version) for name, version, spec in requirements)
    assert any(name == "mysql-connector-python" for name, _version, _spec in requirements)


def test_mysql_url_parser_decodes_credentials():
    result = launcher.mysql_url_credentials("mysql+mysqlconnector://sme_app:p%40ss%23word@127.0.0.1:3306/smart_meter_explorer")
    assert result == {"host": "127.0.0.1", "port": 3306, "user": "sme_app", "password": "p@ss#word", "database": "smart_meter_explorer"}


def test_mysql_roles_have_separate_privileges():
    sql = launcher.mysql_user_sql("app-secret", "migration-secret", "%")
    assert "'sme_app'@'%'" in sql
    assert "'sme_migrator'@'%'" in sql
    app_grant = next(line for line in sql.splitlines() if line.startswith("GRANT") and "sme_app" in line)
    migration_grant = next(line for line in sql.splitlines() if line.startswith("GRANT") and "sme_migrator" in line)
    assert "CREATE" not in app_grant and "ALTER" not in app_grant and "DROP" not in app_grant
    assert "CREATE" in migration_grant and "ALTER" in migration_grant


def test_compose_binds_mysql_to_loopback_only():
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert '"127.0.0.1:3306:3306"' in compose
    assert "sme_mysql_data:/var/lib/mysql" in compose


def test_paths_resolver_rejects_project_escape():
    from sme.paths import project_file
    import pytest
    with pytest.raises(ValueError):
        project_file("../outside.env")
    assert project_file("README.md").is_file()


def test_path_registry_required_files_exist():
    required = ["launch.py", "compose.yaml", "sme/paths.py", "scripts/path_registry.py", "scripts/system_diagnostics.py", "scripts/train_synthetic_baseline.py", "learning/README.md"]
    assert all((ROOT / item).is_file() for item in required)


def test_mysql_version_gate_rejects_mariadb_and_old_versions():
    assert launcher.mysql_version_supported("8.0.16", "MySQL Community Server")
    assert launcher.mysql_version_supported("8.4.0", "MySQL Community Server")
    assert not launcher.mysql_version_supported("8.0.15", "MySQL Community Server")
    assert not launcher.mysql_version_supported("10.11.6-MariaDB", "MariaDB Server")


def test_launcher_updates_only_default_loopback_allowlists_for_custom_port():
    values = {"APP_PORT": "8012", "APP_ALLOWED_ORIGINS": "http://127.0.0.1:8000,http://localhost:8000", "APP_ALLOWED_HOSTS": "127.0.0.1:8000,localhost:8000"}
    launcher.align_default_loopback_allowlists(values)
    assert values["APP_ALLOWED_ORIGINS"] == "http://127.0.0.1:8012,http://localhost:8012"
    assert values["APP_ALLOWED_HOSTS"] == "127.0.0.1:8012,localhost:8012"
    custom = {"APP_PORT": "8012", "APP_ALLOWED_ORIGINS": "http://127.0.0.1:8000,http://example.invalid", "APP_ALLOWED_HOSTS": "127.0.0.1:8000,example.invalid"}
    launcher.align_default_loopback_allowlists(custom)
    assert custom["APP_ALLOWED_ORIGINS"].endswith("example.invalid")
