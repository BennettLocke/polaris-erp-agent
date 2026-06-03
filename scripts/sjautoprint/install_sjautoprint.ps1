[CmdletBinding()]
param(
    [string]$ServiceName = "sjAutoPrint",
    [string]$OldServiceName = "ShopXOAutoPrint",
    [string]$InstallDir = "C:\printer",
    [string]$PythonPath = "C:\Python314\python.exe",
    [string]$NssmPath = "$env:WINDIR\system32\nssm.exe",
    [string]$BaseUrl = "https://ai.513sjbz.com",
    [string]$PrinterName = "Kyocera TASKalfa 1800",
    [int]$CheckInterval = 3,
    [string]$PrintToken = "",
    [string]$ChromiumPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-ServiceOrNull([string]$Name) {
    return Get-Service -Name $Name -ErrorAction SilentlyContinue
}

function Remove-NssmService([string]$Name) {
    if (Get-ServiceOrNull $Name) {
        Write-Host "Stopping service $Name ..."
        & $NssmPath stop $Name | Out-Host
        Write-Host "Removing service $Name ..."
        & $NssmPath remove $Name confirm | Out-Host
    }
}

function Stop-ExistingPrintAgents {
    $agents = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -and $_.CommandLine -like "*auto_print.py*" }

    foreach ($agent in $agents) {
        Write-Host "Stopping existing auto_print.py process $($agent.ProcessId) ..."
        Stop-Process -Id $agent.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

function Get-LocalBrowserPath([string]$CacheDir) {
    if (-not (Test-Path -LiteralPath $CacheDir)) {
        return ""
    }

    $patterns = @(
        "chrome\win64-*\chrome-win64\chrome.exe",
        "chrome-headless-shell\win64-*\chrome-headless-shell-win64\chrome-headless-shell.exe"
    )
    foreach ($pattern in $patterns) {
        $searchPath = Join-Path $CacheDir $pattern
        $match = Get-ChildItem -Path $searchPath -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending |
            Select-Object -First 1
        if ($match) {
            return $match.FullName
        }
    }
    return ""
}

function Install-NodeDependencies([string]$TargetDir, [string]$CacheDir, [string]$NodePath, [string]$NpmPath) {
    $packageSource = Join-Path $ServiceScriptDir "package.json"
    $packageTarget = Join-Path $TargetDir "package.json"
    if (Test-Path -LiteralPath $packageSource) {
        Copy-Item -LiteralPath $packageSource -Destination $packageTarget -Force
    }

    $puppeteerPackage = Join-Path $TargetDir "node_modules\puppeteer\package.json"
    if (-not (Test-Path -LiteralPath $puppeteerPackage)) {
        Write-Host "Installing sjAutoPrint Node dependencies ..."
        Push-Location $TargetDir
        try {
            & $NpmPath install --omit=dev --no-audit --no-fund | Out-Host
        } finally {
            Pop-Location
        }
    }

    $installScript = Join-Path $TargetDir "node_modules\puppeteer\install.mjs"
    if (Test-Path -LiteralPath $installScript) {
        Write-Host "Installing local Chromium for sjAutoPrint ..."
        $previousCache = $env:PUPPETEER_CACHE_DIR
        $env:PUPPETEER_CACHE_DIR = $CacheDir
        try {
            & $NodePath $installScript | Out-Host
        } finally {
            if ($null -eq $previousCache) {
                Remove-Item Env:\PUPPETEER_CACHE_DIR -ErrorAction SilentlyContinue
            } else {
                $env:PUPPETEER_CACHE_DIR = $previousCache
            }
        }
    }
}

function Set-DesktopStartShortcut([string]$TargetDir) {
    try {
        $desktop = [Environment]::GetFolderPath("Desktop")
        if (-not $desktop) {
            return
        }
        $shortcutPath = Join-Path $desktop "启动或重启 sjAutoPrint.lnk"
        $scriptPath = Join-Path $TargetDir "start_sjautoprint.ps1"
        $powershellPath = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"
        $wsh = New-Object -ComObject WScript.Shell
        $shortcut = $wsh.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = $powershellPath
        $shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""
        $shortcut.WorkingDirectory = $TargetDir
        $shortcut.WindowStyle = 1
        $shortcut.Description = "Start or restart the sjAutoPrint local print service"
        $shortcut.IconLocation = "$env:WINDIR\System32\shell32.dll,16"
        $shortcut.Save()
        Write-Host "Desktop shortcut: $shortcutPath"
    } catch {
        Write-Warning "Could not create desktop shortcut: $($_.Exception.Message)"
    }
}

if (-not (Test-IsAdmin)) {
    throw "Please run this installer from an elevated PowerShell window."
}
if (-not (Test-Path -LiteralPath $NssmPath)) {
    throw "nssm.exe was not found at $NssmPath"
}
if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "Python was not found at $PythonPath"
}
$NodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
if (-not $NodeCommand) {
    throw "Node.js was not found in PATH"
}
$NpmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $NpmCommand) {
    throw "npm was not found in PATH"
}

$ServiceScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ScriptsDir = Split-Path -Parent $ServiceScriptDir
$ConfigPath = Join-Path $InstallDir "config.json"
$PuppeteerCacheDir = Join-Path $InstallDir ".cache\puppeteer"

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir "logs") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir "pdf_output") | Out-Null
New-Item -ItemType Directory -Force -Path $PuppeteerCacheDir | Out-Null

Copy-Item -LiteralPath (Join-Path $ScriptsDir "local_print_agent.py") -Destination (Join-Path $InstallDir "local_print_agent.py") -Force
Copy-Item -LiteralPath (Join-Path $ScriptsDir "local_print_render_pdf.js") -Destination (Join-Path $InstallDir "local_print_render_pdf.js") -Force
Copy-Item -LiteralPath (Join-Path $ServiceScriptDir "auto_print.py") -Destination (Join-Path $InstallDir "auto_print.py") -Force
Copy-Item -LiteralPath (Join-Path $ServiceScriptDir "start_sjautoprint.ps1") -Destination (Join-Path $InstallDir "start_sjautoprint.ps1") -Force
Install-NodeDependencies $InstallDir $PuppeteerCacheDir $NodeCommand.Source $NpmCommand.Source

if (-not $ChromiumPath) {
    $ChromiumPath = Get-LocalBrowserPath $PuppeteerCacheDir
}

if (Test-Path -LiteralPath $ConfigPath) {
    try {
        $ConfigObject = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        $ConfigObject = [pscustomobject]@{}
    }
} else {
    $ConfigObject = Get-Content -LiteralPath (Join-Path $ServiceScriptDir "config.example.json") -Raw -Encoding UTF8 | ConvertFrom-Json
}

$Config = [ordered]@{}
foreach ($Property in $ConfigObject.PSObject.Properties) {
    $Config[$Property.Name] = $Property.Value
}
$Config["base_url"] = $BaseUrl.TrimEnd("/")
$Config["print_token"] = $PrintToken
$Config["check_interval"] = [Math]::Max(1, $CheckInterval)
$Config["printer_name"] = $PrinterName
$Config["chromium_path"] = $ChromiumPath
$Config["agent_name"] = $ServiceName
$Config["service_name"] = $ServiceName
$Config | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ConfigPath -Encoding UTF8

if ($OldServiceName -and $OldServiceName -ne $ServiceName) {
    Remove-NssmService $OldServiceName
}
Remove-NssmService $ServiceName
Stop-ExistingPrintAgents

& $NssmPath install $ServiceName $PythonPath (Join-Path $InstallDir "auto_print.py") | Out-Host
& $NssmPath set $ServiceName AppDirectory $InstallDir | Out-Host
& $NssmPath set $ServiceName DisplayName "sjAutoPrint" | Out-Host
& $NssmPath set $ServiceName Description "sjagent local print agent" | Out-Host
& $NssmPath set $ServiceName Start SERVICE_AUTO_START | Out-Host
& $NssmPath set $ServiceName AppStdout (Join-Path $InstallDir "logs\sjAutoPrint.out.log") | Out-Host
& $NssmPath set $ServiceName AppStderr (Join-Path $InstallDir "logs\sjAutoPrint.err.log") | Out-Host
& $NssmPath set $ServiceName AppRotateFiles 1 | Out-Host
& $NssmPath set $ServiceName AppRotateOnline 1 | Out-Host
& $NssmPath set $ServiceName AppEnvironmentExtra "SJAGENT_PRINT_CONFIG=$ConfigPath" | Out-Host
& $NssmPath start $ServiceName | Out-Host
Set-DesktopStartShortcut $InstallDir

Write-Host ""
Write-Host "Installed $ServiceName"
Write-Host "Config: $ConfigPath"
Get-Service -Name $ServiceName | Format-List Name,DisplayName,Status,StartType
