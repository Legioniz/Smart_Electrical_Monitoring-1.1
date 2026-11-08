[CmdletBinding()]
param(
    [switch]$InstallOllama,
    [switch]$SetupOnly,
    [switch]$SkipReact,
    [switch]$DiagnoseOnly,
    [switch]$NoElevation
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Downloads = Join-Path $ProjectRoot '.local\downloads'
$Logs = Join-Path $ProjectRoot '.local\logs'
New-Item -ItemType Directory -Force -Path $Downloads, $Logs | Out-Null
$LogFile = Join-Path $Logs 'windows-setup.log'
# Elevate only for machine-level installers and Windows service startup.
if (-not $DiagnoseOnly -and -not $NoElevation) {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        $forward = @('-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File',('"' + $PSCommandPath + '"'))
        if ($InstallOllama) { $forward += '-InstallOllama' }
        if ($SetupOnly) { $forward += '-SetupOnly' }
        if ($SkipReact) { $forward += '-SkipReact' }
        $child = Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList ($forward -join ' ') -Wait -PassThru
        exit $child.ExitCode
    }
}
Start-Transcript -Path $LogFile -Append | Out-Null

function Write-Step([string]$Message) { Write-Host "`n[SME SETUP] $Message" -ForegroundColor Cyan }
function Test-Command([string]$Name) { return [bool](Get-Command $Name -ErrorAction SilentlyContinue) }
function Invoke-Checked([string]$File, [string[]]$Arguments, [int]$TimeoutSeconds = 1800, [int[]]$AllowedExitCodes = @(0)) {
    Write-Host "> $File $($Arguments -join ' ')"
    $quoted = $Arguments | ForEach-Object { if ($_ -match '[\s&()]') { '"' + ($_ -replace '"','\"') + '"' } else { $_ } }
    $p = Start-Process -FilePath $File -ArgumentList ($quoted -join ' ') -PassThru -NoNewWindow
    if (-not $p.WaitForExit($TimeoutSeconds * 1000)) { try { $p.Kill() } catch {}; throw "Command timed out after $TimeoutSeconds seconds: $File" }
    if ($AllowedExitCodes -notcontains $p.ExitCode) { throw "Command failed ($($p.ExitCode)): $File $($Arguments -join ' ')" }
}
function Get-NodeVersion {
    if (-not (Test-Command 'node')) { return $null }
    $v = (& node --version 2>$null | Select-Object -First 1)
    if ($v -match 'v?(\d+)\.(\d+)\.(\d+)') { return [version]::new([int]$Matches[1],[int]$Matches[2],[int]$Matches[3]) }
    return $null
}
function Get-MySqlCli {
    $cmd = Get-Command mysql.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $roots = @($env:ProgramFiles, ${env:ProgramFiles(x86)}) | Where-Object { $_ }
    foreach ($root in $roots) {
        $candidate = Join-Path $root 'MySQL\MySQL Server 8.4\bin\mysql.exe'
        if (Test-Path $candidate) { return $candidate }
        $matches = Get-ChildItem (Join-Path $root 'MySQL') -Filter mysql.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($matches) { return $matches.FullName }
    }
    return $null
}
function Test-Tcp([string]$HostName='127.0.0.1',[int]$Port=3306) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try { $task = $client.ConnectAsync($HostName,$Port); return $task.Wait(1200) -and $client.Connected }
    catch { return $false }
    finally { $client.Dispose() }
}
function Get-Sha256([string]$Path) { return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Download-Verified([string]$Url,[string]$Destination,[string]$ExpectedSha256) {
    if (Test-Path $Destination) {
        if ((Get-Sha256 $Destination) -eq $ExpectedSha256.ToLowerInvariant()) { Write-Host "Already downloaded and verified: $Destination"; return }
        Remove-Item -LiteralPath $Destination -Force
    }
    Write-Step "Downloading $([IO.Path]::GetFileName($Destination)) from the official publisher"
    Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing
    $actual = Get-Sha256 $Destination
    if ($actual -ne $ExpectedSha256.ToLowerInvariant()) { Remove-Item $Destination -Force; throw "SHA-256 mismatch for $Destination. Download deleted." }
    Write-Host "SHA-256 verified: $actual" -ForegroundColor Green
}
function Ensure-Node {
    $version = Get-NodeVersion
    if ($version -and $version.Major -ge 22 -and (Test-Command 'npm')) {
        Write-Host "Node.js $version and npm already installed; skipping installation." -ForegroundColor Green
        return
    }
    # Current Node.js LTS at package preparation: 26.13.0 (Windows x64).
    # Verify the installer against the official Node.js SHASUMS256 file before execution.
    $nodeVersion = '26.13.0'
    $file = "node-v$nodeVersion-x64.msi"
    $base = "https://nodejs.org/dist/v$nodeVersion"
    $sums = Join-Path $Downloads 'SHASUMS256-node.txt'
    Invoke-WebRequest -Uri "$base/SHASUMS256.txt" -OutFile $sums -UseBasicParsing
    $line = Get-Content $sums | Where-Object { $_ -match "\s\*?$([regex]::Escape($file))$" } | Select-Object -First 1
    if (-not $line -or $line -notmatch '^([a-fA-F0-9]{64})\s+\*?') { throw "Could not obtain official SHA-256 for $file" }
    $hash = $Matches[1]
    $msi = Join-Path $Downloads $file
    Download-Verified "$base/$file" $msi $hash
    Write-Step "Installing Node.js LTS (npm is bundled with the official Windows MSI)"
    Invoke-Checked 'msiexec.exe' @('/i', $msi, '/passive', '/norestart', 'ADDLOCAL=ALL') 1200 @(0,3010,1641)
    $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
    if (-not (Get-NodeVersion) -or -not (Test-Command 'npm')) {
        $nodeDir = Join-Path $env:ProgramFiles 'nodejs'
        if (Test-Path (Join-Path $nodeDir 'node.exe')) { $env:Path = "$nodeDir;$env:Path" }
    }
    if (-not (Get-NodeVersion) -or -not (Test-Command 'npm')) { throw 'Node.js installation finished but node/npm are not visible. Open a new terminal and rerun this setup.' }
}
function Ensure-VCRuntime {
    $key = 'HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64'
    $installed = $false
    try { $installed = (Get-ItemProperty $key -ErrorAction Stop).Installed -eq 1 } catch {}
    if ($installed) { Write-Host 'Microsoft Visual C++ x64 runtime already present; skipping.'; return }
    $url = 'https://aka.ms/vs/17/release/vc_redist.x64.exe'
    $file = Join-Path $Downloads 'vc_redist.x64.exe'
    Invoke-WebRequest -Uri $url -OutFile $file -UseBasicParsing
    $signature = Get-AuthenticodeSignature -FilePath $file
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Microsoft') { Remove-Item $file -Force; throw 'VC++ redistributable signature validation failed; installer deleted.' }
    Write-Step 'Installing Microsoft Visual C++ x64 runtime required by MySQL Server 8.4'
    Invoke-Checked $file @('/install','/quiet','/norestart') 900 @(0,3010,1638)
}
function Ensure-MySqlService {
    if (Test-Tcp) { Write-Host 'MySQL is already listening on 127.0.0.1:3306; no service changes needed.' -ForegroundColor Green; return $true }
    $services = @(Get-Service -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'mysql' -or $_.DisplayName -match 'mysql' })
    if ($services.Count -gt 0) {
        foreach ($svc in $services) {
            if ($svc.Status -ne 'Running') {
                Write-Step "Starting existing MySQL service: $($svc.Name)"
                try { Start-Service -Name $svc.Name -ErrorAction Stop }
                catch { throw "MySQL service '$($svc.Name)' exists but could not start: $($_.Exception.Message). Open Services or MySQL Configurator and inspect its error log. No reinstall was attempted." }
            }
        }
        for ($i=0; $i -lt 30; $i++) { if (Test-Tcp) { Write-Host 'Existing MySQL service is responding.' -ForegroundColor Green; return $true }; Start-Sleep -Seconds 2 }
        throw 'Existing MySQL service started but TCP 127.0.0.1:3306 is still unavailable. Check MySQL Configurator, my.ini, and the server error log. No reinstall was attempted.'
    }
    $cli = Get-MySqlCli
    if ($cli) {
        $server = Join-Path (Split-Path $cli -Parent) 'mysqld.exe'
        $configuratorCandidates = @(
            (Join-Path (Split-Path $cli -Parent) 'MySQLConfigurator.exe'),
            (Join-Path $env:ProgramFiles 'MySQL\MySQL Server 8.4\bin\MySQLConfigurator.exe'),
            (Join-Path $env:ProgramFiles 'MySQL\MySQL Server 8.4\MySQLConfigurator.exe')
        )
        $configurator = $configuratorCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
        if ($configurator) { Start-Process -FilePath $configurator; throw 'MySQL is installed but has no registered service. MySQL Configurator was opened; finish its configuration, then rerun this launcher.' }
        if (Test-Path $server) { throw 'MySQL Server binaries exist but no Windows service is configured. Open MySQL Configurator from the Start menu, configure/start the existing server, then rerun. The setup intentionally will not initialize or overwrite a data directory.' }
        throw "MySQL CLI found at $cli, but mysqld.exe and a service were not found. Repair the existing MySQL installation rather than installing over it."
    }
    Write-Step 'MySQL Server is not installed. Opening the official MySQL 8.4 LTS download page.'
    Start-Process 'https://dev.mysql.com/downloads/mysql/8.4.html'
    throw 'Install MySQL Community Server 8.4 LTS using the official MSI and MySQL Configurator. Then rerun this setup. No database files will be overwritten.'
}
function Ensure-React {
    if ($SkipReact) { Write-Host 'React build skipped by request; offline fallback will be used.'; return }
    Ensure-Node
    $frontend = Join-Path $ProjectRoot 'frontend'
    Push-Location $frontend
    try {
        if (-not (Test-Path 'package-lock.json')) {
            Write-Step 'No npm lockfile found; creating a deterministic lockfile from package.json.'
            Invoke-Checked 'npm.cmd' @('install','--package-lock-only','--no-audit','--no-fund') 1800
        }
        if (-not (Test-Path 'node_modules\vite\bin\vite.js')) {
            Write-Step 'Installing missing React/Vite dependencies (existing node_modules is reused).'
            Invoke-Checked 'npm.cmd' @('ci','--no-audit','--no-fund') 2400
        } else {
            Write-Host 'React/Vite dependencies already present; verifying package tree.'
            $npmCheck = Start-Process 'npm.cmd' -ArgumentList @('ls','--depth=0') -Wait -PassThru -NoNewWindow
            if ($npmCheck.ExitCode -ne 0) { Invoke-Checked 'npm.cmd' @('install','--no-audit','--no-fund') 2400 }
        }
        Invoke-Checked 'npm.cmd' @('run','build') 900
        $dist = Join-Path $ProjectRoot 'web\dist\index.html'
        if (-not (Test-Path $dist)) { throw 'React build command completed but web/dist/index.html was not produced.' }
    } finally { Pop-Location }
}
function Install-OllamaOptional {
    if (-not $InstallOllama) { Write-Host 'Ollama is optional and was not requested; deterministic analytics remain available.'; return }
    if (Test-Command 'ollama') { Write-Host 'Ollama already installed; skipping.'; return }
    $installer = Join-Path $Downloads 'OllamaSetup.exe'
    Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile $installer -UseBasicParsing
    $signature = Get-AuthenticodeSignature -FilePath $installer
    if ($signature.Status -ne 'Valid') { Remove-Item $installer -Force; throw 'Ollama installer signature validation failed; installer deleted.' }
    Write-Step 'Launching official Ollama installer (model downloads are not automatic).'
    Start-Process -FilePath $installer -Wait
    Write-Host 'Ollama installer finished. Choose a model only after checking available RAM/VRAM and disk space.'
}

try {
    Write-Step 'Windows 10 environment check'
    Get-ComputerInfo -Property WindowsProductName,WindowsVersion,OsArchitecture | Format-List
    Write-Host "Project: $ProjectRoot"
    Write-Host "Python: $(& python --version 2>&1)"
    Write-Host "MySQL CLI: $(Get-MySqlCli)"
    Write-Host "Node: $(Get-NodeVersion)"
    Write-Host "npm: $(if (Test-Command 'npm') { (npm --version) } else { 'missing' })"
    Write-Host "MySQL TCP: $(Test-Tcp)"
    if ($DiagnoseOnly) { return }

    # MySQL 8.4 on Windows depends on the Microsoft VC++ 2019+ runtime.
    Ensure-VCRuntime
    Ensure-MySqlService
    Ensure-Node
    Ensure-React
    Install-OllamaOptional

    Write-Step 'Running the project launcher: Python dependencies, database credentials, migrations, diagnostics, and app startup'
    $launcherArgs = @('launch.py')
    if ($SetupOnly) { $launcherArgs += '--setup-only' }
    & python @launcherArgs
    if ($LASTEXITCODE -ne 0) { throw "launch.py exited with code $LASTEXITCODE. See .local\logs\launcher.log" }
    Write-Host "`n[SME] Setup completed successfully." -ForegroundColor Green
}
catch {
    Write-Host "`n[SME SETUP FAILED] $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Log: $LogFile"
    exit 1
}
finally { Stop-Transcript | Out-Null }
