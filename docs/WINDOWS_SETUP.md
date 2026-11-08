# Windows 10 setup and dependency installer

For the inspected computer (Windows 10, Python 3.13.3, existing MySQL 8.4 CLI, no Node/npm, no MySQL TCP listener), use the included `START-SME-WINDOWS.bat`.

## What it does

1. Requests Administrator approval only because machine-level installers and Windows service startup may require it.
2. Checks for the Microsoft Visual C++ x64 runtime required by MySQL Server 8.4; downloads it from Microsoft and validates its Authenticode signature only if missing.
3. Checks the existing MySQL Windows services and starts the installed service. It does **not** reinstall MySQL, initialize a new data directory, reset passwords, or delete/replace databases. If the MySQL binaries exist but no service is configured, it opens MySQL Configurator or directs the operator to it.
4. Checks Node.js and npm. If Node.js 22+ and npm are already present, it skips installation. Otherwise it downloads the Node.js 26.13.0 LTS x64 MSI from nodejs.org, obtains the SHA-256 from the official `SHASUMS256.txt`, verifies the MSI, then installs it. npm is included in the official Windows MSI.
5. Installs only the missing frontend dependencies using npm and builds React into `web/dist`.
6. Calls `launch.py` to check Python dependencies, database credentials, migrations, diagnostics, and application startup.
7. Keeps downloaded installers and logs in `.local/downloads` and `.local/logs`.

## Start

Double-click `START-SME-WINDOWS.bat`, or from PowerShell in the project folder:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1
```

Useful options:

```powershell
# Read-only environment report; no install or service changes
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1 -DiagnoseOnly

# Prepare dependencies and DB, but do not start the web server
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1 -SetupOnly

# Keep the no-CDN fallback; skip React install/build
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1 -SkipReact

# Also install optional Ollama; model weights are NOT downloaded automatically
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1 -InstallOllama
```

## MySQL note for this machine

The diagnostic shows `mysql.exe` exists at `C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe`, but `127.0.0.1:3306` does not respond. This indicates a stopped/unconfigured service or a server startup problem, not a missing MySQL client. The setup first searches for and starts an existing MySQL service. If no service exists, use **MySQL Configurator** from the Start menu to configure the existing Server 8.4 installation. Do not install another server over the existing data directory.

After MySQL starts, `launch.py` verifies the configured app and migration accounts. If `.env` credentials are not valid, it asks for the existing MySQL administrator credentials and creates the project's least-privilege accounts. Keep `.env` private; it contains secrets.

## Optional Ollama

Ollama is not required for the application to start; deterministic analytics and recommendations remain available. `-InstallOllama` downloads the official Windows installer and validates its signature. It does not automatically pull a model because model downloads can consume several GB and suitability depends on RAM/VRAM. Choose and pull a model separately after checking hardware capacity.

## Safety and limitations

- The script does not reinstall programs that are already detected.
- Node MSI is SHA-256 verified against the official Node.js release manifest.
- Microsoft VC++ and Ollama installers are checked for valid publisher signatures.
- The script never downloads or executes a remote PowerShell script.
- npm dependencies are installed from the frontend's pinned `package.json`; npm creates/uses the lockfile.
- Internet access is required for missing installers and npm packages.
- MySQL service startup and MSI installation may trigger Windows UAC.
- If Windows blocks the download, inspect `.local/logs/windows-setup.log` and rerun after restoring network access.
