[CmdletBinding()]
param(
    [string]$ServiceName = "sjAutoPrint",
    [string]$NssmPath = "$env:WINDIR\system32\nssm.exe"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdmin)) {
    throw "Please run this uninstaller from an elevated PowerShell window."
}
if (-not (Test-Path -LiteralPath $NssmPath)) {
    throw "nssm.exe was not found at $NssmPath"
}

$service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if (-not $service) {
    Write-Host "$ServiceName is not installed."
    return
}

& $NssmPath stop $ServiceName | Out-Host
& $NssmPath remove $ServiceName confirm | Out-Host
Write-Host "Removed $ServiceName"
