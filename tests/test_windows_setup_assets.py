from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_windows_setup_entrypoints_exist():
    assert (ROOT / "scripts" / "setup_windows.ps1").is_file()
    assert (ROOT / "START-SME-WINDOWS.bat").is_file()
    assert (ROOT / "DOWNLOAD-REQUIREMENTS-WINDOWS.bat").is_file()


def test_windows_setup_uses_official_verified_node_installer():
    script = (ROOT / "scripts" / "setup_windows.ps1").read_text(encoding="utf-8")
    assert "https://nodejs.org/dist/v$nodeVersion" in script
    assert "SHASUMS256.txt" in script
    assert "Get-FileHash" in script
    assert "node-v$nodeVersion-x64.msi" in script


def test_existing_mysql_is_reused_not_reinstalled():
    script = (ROOT / "scripts" / "setup_windows.ps1").read_text(encoding="utf-8")
    assert "Get-Service" in script
    assert "Start-Service" in script
    assert "No reinstall was attempted" in script
    assert "MySQLConfigurator" in script
    assert "mysql.exe" in script


def test_react_install_and_build_are_included():
    script = (ROOT / "scripts" / "setup_windows.ps1").read_text(encoding="utf-8")
    assert "npm.cmd" in script
    assert "npm.cmd' @('ci'" in script
    assert "npm.cmd' @('run','build'" in script
    assert "web\\dist\\index.html" in script


def test_ollama_is_explicitly_optional():
    script = (ROOT / "scripts" / "setup_windows.ps1").read_text(encoding="utf-8")
    assert "[switch]$InstallOllama" in script
    assert "https://ollama.com/download/OllamaSetup.exe" in script
    assert "model downloads are not automatic" in script


def test_windows_guide_matches_entrypoints():
    guide = (ROOT / "docs" / "WINDOWS_SETUP.md").read_text(encoding="utf-8")
    assert "START-SME-WINDOWS.bat" in guide
    assert "-DiagnoseOnly" in guide
    assert "does not" in guide.lower()
