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
    [string]$ChromiumPath = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
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

if (-not (Test-IsAdmin)) {
    throw "Please run this installer from an elevated PowerShell window."
}
if (-not (Test-Path -LiteralPath $NssmPath)) {
    throw "nssm.exe was not found at $NssmPath"
}
if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "Python was not found at $PythonPath"
}

$ServiceScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ScriptsDir = Split-Path -Parent $ServiceScriptDir
$ConfigPath = Join-Path $InstallDir "config.json"

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir "logs") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir "pdf_output") | Out-Null

Copy-Item -LiteralPath (Join-Path $ScriptsDir "local_print_agent.py") -Destination (Join-Path $InstallDir "local_print_agent.py") -Force
Copy-Item -LiteralPath (Join-Path $ScriptsDir "local_print_render_pdf.js") -Destination (Join-Path $InstallDir "local_print_render_pdf.js") -Force
Copy-Item -LiteralPath (Join-Path $ServiceScriptDir "auto_print.py") -Destination (Join-Path $InstallDir "auto_print.py") -Force

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

Write-Host ""
Write-Host "Installed $ServiceName"
Write-Host "Config: $ConfigPath"
Get-Service -Name $ServiceName | Format-List Name,DisplayName,Status,StartType
